"""Promote an experiment to artifacts/ (only if it beats the current one AND the app smoke test passes).
python src/promote.py --id B1 [--force]
Builds into artifacts_new/, runs app/smoke_test.py against it, then swaps into artifacts/.
"""
import argparse, gzip, json, os, pickle, shutil, subprocess, sys, warnings
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path
from eval import benchmark_zestimate, load_truth, metrics, score
from exp import LGB, SEGMENTS, run_cv, segment_oof, target_offset
from featurize_new import Featurizer

warnings.filterwarnings("ignore")
QA = (0.1, 0.9)


def width_scale(y, pred, lo_w, hi_w, target=0.8):
    """Smallest s with coverage of [pred - s*lo_w, pred + s*hi_w] >= target."""
    for s in np.arange(0.5, 4.0, 0.01):
        if np.mean((y >= pred - s * lo_w) & (y <= pred + s * hi_w)) >= target:
            return float(s)
    return 4.0


def deal_label(price, pred, p10, p90):
    gap = (price - pred) / pred
    lab = np.where((price < p10) & (gap <= -0.10), "UNDERPRICED", np.where((price > p90) & (gap >= 0.10), "OVERPRICED", "FAIR"))
    return gap * 100, lab


def shap_long(models, d, folds):
    """Per-house top-10 contributions from the fold model that never saw the house (sums to its OOF pred)."""
    rows, mats, Xs = [], [], []
    for k, (m, fz, Xva, ova) in zip(sorted(set(folds)), models):
        phi = m.predict(Xva, pred_contrib=True)  # log(price) or log(price/sqft); ova = log-size offset (ppsf target)
        idx = np.where(folds == k)[0]
        mats.append((idx, phi))
        Xs.append(Xva)
        pred = np.expm1(phi.sum(1) + ova)
        f = phi[:, :-1]
        top = np.argsort(-np.abs(f), 1)[:, :10]
        cols = np.array(Xva.columns)
        vals = Xva.astype(object).values
        other = f.sum(1) - np.take_along_axis(f, top, 1).sum(1)
        for r in range(len(idx)):
            rid = d.row_id.iat[idx[r]]
            rows.append((rid, 0, "_base", "", float(phi[r, -1]), np.nan, np.nan))  # model's average log price (or $/sqft)
            if ova[r]:
                rows.append((rid, 0, "_size", f"{np.exp(ova[r]):.0f}", float(ova[r]), np.nan, np.nan))
            for rank, j in enumerate(top[r]):
                p = f[r, j]
                rows.append((rid, rank + 1, cols[j], str(vals[r, j]), float(p),
                             float((np.exp(p) - 1) * 100), float(pred[r] * (1 - np.exp(-p)))))
            rows.append((rid, 11, "_other", "", float(other[r]), float((np.exp(other[r]) - 1) * 100),
                         float(pred[r] * (1 - np.exp(-other[r])))))
    long = pd.DataFrame(rows, columns=["row_id", "rank", "feature", "value", "phi_log", "pct", "usd_approx"])
    full = np.zeros((len(d), mats[0][1].shape[1]))
    for idx, phi in mats:
        full[idx] = phi
    X = pd.concat(Xs).loc[d.index]
    return long, full, X


def shap_plot(phi, X, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap
    Xn = X.apply(lambda c: c if pd.api.types.is_numeric_dtype(c) else
                 pd.Series(pd.factorize(c.astype(str))[0], index=c.index).where(c.notna())).astype(float)
    shap.summary_plot(phi[:, :-1], Xn, max_display=15, show=False)
    plt.title("SHAP: what drives predicted log price (OOF fold models)")
    plt.tight_layout()
    plt.savefig(out, dpi=110)
    plt.close()


def build_segment(seg, id_, d_all, folds_all, out):
    """Score `seg` rows with run `id_` (trained on its own segment's rows). Returns parts for the artifacts."""
    meta = json.load(open(path("oof", f"meta_{id_}.json")))
    assert meta["model"] == "lgbm", "app model must be LightGBM (blend only if > 2% MAE better)"
    feats, params, drop = meta["feats"], meta["params"], meta["drop"]
    tmask = SEGMENTS[meta.get("segment", "all")](d_all)
    d, folds = d_all[tmask], folds_all[tmask]
    keep_rows = SEGMENTS[seg](d)  # rows of d scored by this segment
    print(f"[{seg}] {id_}: point CV on {len(d)} training rows, scoring {keep_rows.sum()}", flush=True)
    target = meta.get("target", "price")
    oof, info, models = run_cv(feats, "lgbm", params, folds, d, meta["trim"], meta["seed"], drop, keep_models=True, target=target)
    q = {}
    for al in QA:
        q[al], qinfo, _ = run_cv(feats, "lgbm", {**params, "objective": "quantile", "alpha": al}, folds, d,
                                 meta["trim"], meta["seed"], drop, target=target)
        q[f"iter{al}"] = int(np.mean([i["best_iter"] for i in qinfo]) * 1.1)
    long, phi, X = shap_long(models, d, folds)
    # restrict to this segment's rows
    rid = set(d.row_id[keep_rows])
    long = long[long.row_id.isin(rid)]
    d, folds, oof, phi, X = d[keep_rows], folds[keep_rows], oof[keep_rows], phi[keep_rows], X[keep_rows]
    lo_w, hi_w = np.maximum(oof - q[0.1][keep_rows], 0), np.maximum(q[0.9][keep_rows] - oof, 0)
    # conformal-style width scale, cross-fitted: fold k's scale is fit on the OTHER folds' OOF (target 80% coverage)
    scale = np.zeros(len(d))
    for k in sorted(set(folds)):
        o = folds != k
        scale[folds == k] = width_scale(d.y.values[o], oof[o], lo_w[o], hi_w[o])
    s_full = width_scale(d.y.values, oof, lo_w, hi_w)
    p10, p90 = oof - scale * lo_w, oof + scale * hi_w

    pred = np.expm1(oof)
    gap, lab = deal_label(d.price.values, pred, np.expm1(p10), np.expm1(p90))
    scored = d[["row_id", "zpid", "address", "url", "img", "lat", "lon", "zip", "city", "home_type", "beds", "baths",
                "living_area", "lot_sqft", "year_built", "price", "zestimate"]].copy()
    scored["pred"], scored["p10"], scored["p90"] = pred.round(), np.expm1(p10).round(), np.expm1(p90).round()
    scored["gap_pct"], scored["deal"], scored["fold"], scored["segment"] = gap.round(2), lab, folds, seg

    print(f"[{seg}] full-data refit", flush=True)
    import lightgbm as lgb
    dt = d_all[tmask]
    fz = Featurizer(feats).fit(dt)
    Xf = fz.transform(dt, train=True).drop(columns=drop)
    full = {}
    for name, extra, it in (("point", {}, int(np.mean([i["best_iter"] for i in info]) * 1.1)),
                            ("p10", {"objective": "quantile", "alpha": 0.1}, q["iter0.1"]),
                            ("p90", {"objective": "quantile", "alpha": 0.9}, q["iter0.9"])):
        full[name] = lgb.LGBMRegressor(**{**LGB, **params, **extra, "n_estimators": it}, random_state=meta["seed"]).fit(Xf, dt.y.values - target_offset(dt, target))
    model = {"id": id_, "target": target, "feats": feats, "drop": drop, "columns": list(Xf.columns), "models": full, "interval_scale": s_full}
    cv, std, per = score(oof, d.price.values, folds)
    imp = pd.Series(full["point"].booster_.feature_importance("gain"), index=Xf.columns).sort_values(ascending=False)
    seg_m = {"id": id_, "trained_on": meta.get("segment", "all"), "feats": feats, "rows": int(len(d)),
             "cv": {**cv, "rmse_log_std": std, "per_fold_rmse_log": per}, "interval_scale": s_full,
             "interval_coverage_p10_p90": float(np.mean((d.price.values >= np.expm1(p10)) & (d.price.values <= np.expm1(p90)))),
             "deal_counts": pd.Series(lab).value_counts().to_dict(),
             "feature_importance_gain": (imp / imp.sum()).round(4).head(20).to_dict()}
    seg_m["_widths"] = (lo_w, hi_w)  # popped before metrics.json; used to re-centre the range on a blend
    return scored, long, phi, X, model, fz, seg_m, oof


def apply_blend(part, blend_id, d_all, folds_all):
    """Replace the homes OOF centre with an honest blend OOF; re-calibrate the 80% range around it (cross-fitted)."""
    scored, long, phi, X, model, fz, seg_m, oof = part
    mask = SEGMENTS["homes"](d_all)
    d, folds = d_all[mask], folds_all[mask]
    b = segment_oof(blend_id, "homes")[0]
    lo_w, hi_w = seg_m["_widths"]
    scale = np.zeros(len(d))
    for k in sorted(set(folds)):
        o = folds != k
        scale[folds == k] = width_scale(d.y.values[o], b[o], lo_w[o], hi_w[o])
    p10, p90 = b - scale * lo_w, b + scale * hi_w
    gap, lab = deal_label(d.price.values, np.expm1(b), np.expm1(p10), np.expm1(p90))
    scored = scored.copy()
    scored["pred"], scored["p10"], scored["p90"] = np.expm1(b).round(), np.expm1(p10).round(), np.expm1(p90).round()
    scored["gap_pct"], scored["deal"] = gap.round(2), lab
    cv, std, per = score(b, d.price.values, folds)
    seg_m = {**seg_m, "app_model_cv": seg_m["cv"], "cv": {**cv, "rmse_log_std": std, "per_fold_rmse_log": per},
             "blend": json.load(open(path("oof", f"meta_{blend_id}_raw.json"))) | {"id": blend_id},
             "interval_coverage_p10_p90": float(np.mean((d.price.values >= np.expm1(p10)) & (d.price.values <= np.expm1(p90)))),
             "deal_counts": pd.Series(lab).value_counts().to_dict(),
             "note": "fair price/range/deal labels = blend OOF; 'What's it worth' + SHAP = LightGBM (app_model_cv)"}
    return scored, long, phi, X, model, fz, seg_m, b


APP_SETS = {"base", "hubs", "rot", "struct", "comps", "tcomps", "tight", "zip", "flags"}  # what a user can type


def build_app_model(id_, d_all, folds_all):
    """'What's it worth?' model: same target/params but ONLY user-typeable feature sets (no text/photos/history/schools),
    so a typed-in home is in-distribution. Own OOF check + calibrated 80% range."""
    import lightgbm as lgb
    meta = json.load(open(path("oof", f"meta_{id_}.json")))
    sets = [s for s in meta["feats"].split("+") if s in APP_SETS]
    feats, params, target = "+".join(sets), meta["params"], meta.get("target", "price")
    m = SEGMENTS["homes"](d_all)
    d, folds = d_all[m], folds_all[m]
    print(f"[app] {feats}", flush=True)
    oof, info, _ = run_cv(feats, "lgbm", params, folds, d, False, meta["seed"], (), target=target)
    q = {al: run_cv(feats, "lgbm", {**params, "objective": "quantile", "alpha": al}, folds, d, False, meta["seed"], (),
                    target=target) for al in QA}
    lo_w, hi_w = np.maximum(oof - q[0.1][0], 0), np.maximum(q[0.9][0] - oof, 0)
    s_full = width_scale(d.y.values, oof, lo_w, hi_w)
    fz = Featurizer(feats).fit(d)
    Xf = fz.transform(d, train=True)
    yt = d.y.values - target_offset(d, target)
    full = {}
    for name, extra, inf in (("point", {}, info), ("p10", {"objective": "quantile", "alpha": 0.1}, q[0.1][1]),
                             ("p90", {"objective": "quantile", "alpha": 0.9}, q[0.9][1])):
        it = int(np.mean([i["best_iter"] for i in inf]) * 1.1)
        full[name] = lgb.LGBMRegressor(**{**LGB, **params, **extra, "n_estimators": it}, random_state=meta["seed"]).fit(Xf, yt)
    cv = score(oof, d.price.values, folds)[0]
    print(f"[app] OOF homes MdAPE {cv['mdape']:.2f}%", flush=True)
    return {"id": f"{id_}-app", "target": target, "feats": feats, "drop": [], "columns": list(Xf.columns), "models": full,
            "interval_scale": s_full, "fz": fz}, {"feats": feats, **cv}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--homes", required=True, help="run id scoring homes (non-LOT)")
    ap.add_argument("--land", required=True, help="run id scoring vacant land (LOT); may be an all-listings run")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--blend", default=None, help="blend id (BLx) whose homes OOF drives fair price / range / deals")
    a = ap.parse_args()
    d, folds = load_truth()

    cur = path("artifacts", "metrics.json")
    if os.path.exists(cur) and not a.force:
        cm = json.load(open(cur))
        hm = SEGMENTS["homes"](d)
        new = score(segment_oof(a.blend or a.homes, "homes")[0], d.price.values[hm], folds[hm])[0]
        old = cm.get("segments", {}).get("homes", {}).get("cv", {}).get("rmse_log", -1)
        if new["rmse_log"] >= old:
            raise SystemExit(f"NOT PROMOTED: homes rmse_log {new['rmse_log']:.4f} >= current {old:.4f}")

    out = path("artifacts_new")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    parts = {seg: build_segment(seg, id_, d, folds, out) for seg, id_ in (("homes", a.homes), ("land", a.land))}
    if a.blend:
        parts["homes"] = apply_blend(parts["homes"], a.blend, d, folds)
    for p in parts.values():
        p[6].pop("_widths", None)
    app_model, app_cv = build_app_model(a.homes, d, folds)
    parts["homes"][4]["app"] = app_model
    parts["homes"][6]["app_form_model_cv"] = app_cv
    scored = pd.concat([p[0] for p in parts.values()]).sort_values("row_id").reset_index(drop=True)
    pd.concat([p[1] for p in parts.values()]).astype({c: "float32" for c in ["phi_log", "pct", "usd_approx"]}).to_parquet(
        f"{out}/shap_values.parquet", index=False, compression="zstd")
    scored.to_parquet(f"{out}/houses_scored.parquet", index=False)
    shap_plot(parts["homes"][2], parts["homes"][3], f"{out}/shap_summary.png")
    with gzip.open(f"{out}/model.pkl", "wb") as f:  # gzip-compressed pickle (LightGBM trees compress ~4x)
        pickle.dump({"segments": {s: p[4] for s, p in parts.items()}}, f)
    pickle.dump({s: p[5] for s, p in parts.items()}, open(f"{out}/featurizer.pkl", "wb"))

    # combined OOF over all listings (homes model on homes + land model on land), same frozen folds
    comb = np.zeros(len(d))
    for seg, p in parts.items():
        comb[SEGMENTS[seg](d)] = p[7]
    cv_all, std_all, per_all = score(comb, d.price.values, folds)
    hm = SEGMENTS["homes"](d)
    dh, hs = d[hm], scored.set_index("row_id").loc[d.row_id[hm]]
    zm = dh.zestimate.notna().values
    ours_z = metrics(dh.price.values[zm], hs.pred.values[zm])
    res = pd.read_csv(path("results.tsv"), sep="\t")
    sp = res[(res.folds == "folds_zip.csv")]
    ba = res[res.folds == "folds.csv"][["id", "step", "change", "segment", "mdape", "rmse_log", "std", "mae", "r2", "kept", "model"]]
    m = {"id": f"{a.blend + ':' if a.blend else ''}{a.homes}+{a.land}", "rows": int(len(d)), "headline": "MdAPE (median absolute % error)",
         "segments": {s: p[6] for s, p in parts.items()},
         "all_listings": {**cv_all, "rmse_log_std": std_all},
         "cv_scheme": "GroupKFold(5, shuffle, seed 42) on address/lat-lon groups; target features fold-only",
         "zestimate_benchmark": {**benchmark_zestimate(dh), "segment": "homes",
                                 "note": "reference, not apples-to-apples (Zillow sees the listing)"},
         "ours_on_zestimate_rows": {"mae": ours_z["mae"], "mdape": ours_z["mdape"], "rmse_log": ours_z["rmse_log"]},
         "spatial_cv": {s: sp[sp.segment == s].iloc[-1][["id", "mdape", "rmse_log", "mae", "r2"]].to_dict()
                        for s in ("homes", "land", "all") if (sp.segment == s).any()} or None,
         "before_after": ba.to_dict("records"),
         "leakage_firewall": ["Never features: zestimate, rentZestimate, price per sqft, tax assessed value, price changes/reductions, daysOnZillow",
                              "Zestimate kept aside as a benchmark only",
                              "|Spearman| > 0.95 vs price auto-flag on every feature set",
                              "GroupKFold on address / lat-lon groups (duplicate listings never split across folds)",
                              "KNN comps + ZIP encodings fit on training-fold rows only; training rows exclude their own group",
                              "Prior list price: only the last asking price of a PREVIOUS listing that ended (sold/removed) >= 12 months before the current listing, ZHVI-adjusted; no current-listing event ever used",
                              "Text/photo embeddings: PCA fitted on training-fold rows only"]}
    json.dump(m, open(f"{out}/metrics.json", "w"), indent=1, default=float)

    r = subprocess.run([sys.executable, path("app", "smoke_test.py")], env={**os.environ, "ARTIFACTS_DIR": out},
                       capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    if r.returncode != 0:
        raise SystemExit("SMOKE TEST FAILED -> artifacts/ unchanged")
    shutil.rmtree(path("artifacts"), ignore_errors=True)
    shutil.move(out, path("artifacts"))
    sz = sum(os.path.getsize(os.path.join(path("artifacts"), f)) for f in os.listdir(path("artifacts"))) / 1e6
    subprocess.run([sys.executable, path("src", "pitch.py")], check=False)
    h, l = m["segments"]["homes"], m["segments"]["land"]
    print(f"PROMOTED {m['id']}: homes MdAPE {h['cv']['mdape']:.2f}% (RMSE_log {h['cv']['rmse_log']:.4f}, cov {h['interval_coverage_p10_p90']:.3f}) | "
          f"land MdAPE {l['cv']['mdape']:.2f}% | all MdAPE {cv_all['mdape']:.2f}% | size {sz:.1f}MB")

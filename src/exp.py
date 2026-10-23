"""One logged experiment: fold-only features -> CV -> eval.py -> results.tsv + pitch/before_after.md.
python src/exp.py --id B1 --step B1 --change "LightGBM raw features" --feats base
python src/exp.py --id B0 --step B0 --change "median price by ZIP" --model b0
--trim: drop top/bottom 0.5% prices from TRAINING folds only (validation untouched).
--folds folds_zip.csv: spatial CV (logged, never compared for keep).
"""
import argparse, json, os, sys, time, warnings
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import GroupShuffleSplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path
from eval import keep, load_truth, score
from featurize_new import Featurizer

warnings.filterwarnings("ignore")

LGB = dict(learning_rate=0.03, n_estimators=10000, num_leaves=63, min_child_samples=20, subsample=0.8,
           subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0, n_jobs=12, verbose=-1)
RESULTS = path("results.tsv")
# homes model and land model are trained and scored separately (vacant land = 12% of rows, most of the error)
SEGMENTS = {"all": lambda d: np.ones(len(d), bool), "homes": lambda d: (d.home_type != "LOT").values,
            "land": lambda d: (d.home_type == "LOT").values}


def segment_oof(id_, segment):
    """OOF of any experiment restricted to `segment` (an 'all' run is masked) -> (oof, mask on full data)."""
    seg = json.load(open(path("oof", f"meta_{id_}.json"))).get("segment", "all")
    d, _ = load_truth()
    mask = SEGMENTS[segment](d)
    oof = np.load(path("oof", f"{id_}.npy"))
    if seg == "all" and segment != "all":
        oof = oof[mask]
    return oof, mask
COLS = ["id", "step", "change", "segment", "feats", "model", "rmse_log", "std", "mae", "mdape", "r2", "wins", "kept", "folds", "time"]


def fit_predict(model, Xtr, ytr, Xva_list, params=None, seed=42, groups=None):
    """Fit with early stopping on an inner 10% group holdout of the training fold. Returns model, preds."""
    params = params or {}
    a, b = next(GroupShuffleSplit(1, test_size=0.1, random_state=seed).split(Xtr, groups=groups))
    if model == "lgbm":
        import lightgbm as lgb
        m = lgb.LGBMRegressor(**{**LGB, **params}, random_state=seed)
        m.fit(Xtr.iloc[a], ytr[a], eval_set=[(Xtr.iloc[b], ytr[b])], callbacks=[lgb.early_stopping(200, verbose=False)])
        info = {"best_iter": int(m.best_iteration_)}
    elif model == "xgb":
        import xgboost as xgb
        p = dict(n_estimators=10000, learning_rate=0.03, max_depth=7, subsample=0.8, colsample_bytree=0.7,
                 min_child_weight=3, device="cuda", tree_method="hist", enable_categorical=True,
                 max_cat_to_onehot=1, early_stopping_rounds=200)
        m = xgb.XGBRegressor(**{**p, **params}, random_state=seed)
        m.fit(Xtr.iloc[a], ytr[a], eval_set=[(Xtr.iloc[b], ytr[b])], verbose=False)
        info = {"best_iter": int(m.best_iteration)}
    elif model == "cat":
        from catboost import CatBoostRegressor, Pool
        cats = [c for c in Xtr.columns if str(Xtr[c].dtype) == "category"]
        prep = lambda X: X.assign(**{c: X[c].astype(str) for c in cats})
        p = dict(iterations=10000, learning_rate=0.05, depth=8, od_type="Iter", od_wait=200, verbose=0, thread_count=12)
        m = CatBoostRegressor(**{**p, **params}, random_seed=seed)
        m.fit(Pool(prep(Xtr.iloc[a]), ytr[a], cat_features=cats), eval_set=Pool(prep(Xtr.iloc[b]), ytr[b], cat_features=cats))
        info = {"best_iter": int(m.get_best_iteration())}
        return m, [m.predict(prep(X)) for X in Xva_list], info
    elif model in ("tabpfn", "tabicl"):
        # foundation models: numeric matrix, train context subsampled to 10k rows, predictions chunked (VRAM)
        num = lambda X: X.apply(lambda c: c.cat.codes.where(c.cat.codes >= 0) if str(c.dtype) == "category" else c).astype(np.float32).values
        rs = np.random.default_rng(seed)
        idx = rs.choice(len(Xtr), min(len(Xtr), params.get("max_train", 10000)), replace=False)
        if model == "tabpfn":
            from tabpfn import TabPFNRegressor
            m = TabPFNRegressor(device="cuda", random_state=seed, ignore_pretraining_limits=True)
        else:
            from tabicl import TabICLRegressor
            m = TabICLRegressor(device="cuda", random_state=seed)
        m.fit(num(Xtr.iloc[idx]), ytr[idx])
        preds = [np.concatenate([m.predict(num(X.iloc[i:i + 2000])) for i in range(0, len(X), 2000)]) for X in Xva_list]
        return m, preds, {"n_train": int(len(idx))}
    else:
        raise ValueError(model)
    return m, [m.predict(X) for X in Xva_list], info


def leakage_check(X, price, allow=()):
    """|Spearman| > 0.95 vs price on unseen-row features -> flagged (dropped unless allowed)."""
    flags = {}
    for c in X.columns:
        if str(X[c].dtype) == "category" or X[c].notna().sum() < 3 or X[c].nunique() < 2:
            continue
        r = spearmanr(X[c], price, nan_policy="omit")[0]
        if abs(r) > 0.95 and c not in allow:
            flags[c] = round(float(r), 4)
    return flags


def current_best(segment="all"):
    """Latest kept run in this segment; if none yet, the latest kept 'all' run (scored on the segment)."""
    if not os.path.exists(RESULTS):
        return None
    r = pd.read_csv(RESULTS, sep="\t")
    r = r[(r.kept == 1) & (r.folds == "folds.csv") & (r.step != "BLEND")]  # blends are compared separately
    rs = r[r.segment == segment]
    if rs.empty:
        rs = r[(r.segment == "all") & (r.model != "b0")]
    return None if rs.empty else rs.iloc[-1]["id"]


def write_before_after():
    r = pd.read_csv(RESULTS, sep="\t")
    r = r[r.folds == "folds.csv"]
    os.makedirs(path("pitch"), exist_ok=True)
    lines = ["# Before → After (5-fold GroupKFold CV, out-of-fold, scored by src/eval.py)", "",
             "Headline metric: **MdAPE** (median absolute % error). MAE is pulled up by a few multi-million-dollar listings.", ""]
    for seg, name in (("homes", "Homes (persona model)"), ("land", "Vacant land (separate model)"), ("all", "All listings")):
        rs = r[r.segment == seg]
        if rs.empty or not (rs.kept == 1).any():
            continue
        b0 = rs[rs.model == "b0"].iloc[0] if (rs.model == "b0").any() else rs.iloc[0]
        best = rs[(rs.kept == 1) & (rs.model != "b0")].sort_values("rmse_log").iloc[0] if ((rs.kept == 1) & (rs.model != "b0")).any() else b0
        lines += [f"## {name}", "",
                  f"Best **{best.step}**: MdAPE **{best.mdape:.2f}%** vs B0 {b0.mdape:.2f}% "
                  f"({(1 - best.mdape / b0.mdape) * 100:.0f}% lower); RMSE_log {best.rmse_log:.4f} vs {b0.rmse_log:.4f}; "
                  f"MAE ${best.mae:,.0f} vs ${b0.mae:,.0f}.", "",
                  "| step | change | MdAPE % | RMSE_log | MAE $ | R² | kept |", "|---|---|---|---|---|---|---|"]
        for _, x in rs.iterrows():
            lines.append(f"| {x.step} | {x.change} | {x.mdape:.2f} | {x.rmse_log:.4f} ± {x['std']:.4f} | {x.mae:,.0f} | {x.r2:.3f} | {'yes' if x.kept else 'no'} |")
        lines.append("")
    open(path("pitch", "before_after.md"), "w").write("\n".join(lines) + "\n")


def target_offset(df, target):
    """log-space offset: 'ppsf' models log(price/livingArea) (missing area -> median area of the home type)."""
    if target == "price":
        return np.zeros(len(df))
    a = df.living_area.fillna(df.groupby("home_type").living_area.transform("median")).fillna(1500)
    return np.log(a.values)


def run_cv(feats, model, params, folds, d, trim=False, seed=42, drop=(), keep_models=False, target="price"):
    oof = np.zeros(len(d))
    info, models = [], []
    for k in sorted(set(folds)):
        tr, va = d[folds != k], d[folds == k]
        if trim:
            lo, hi = tr.price.quantile([0.005, 0.995])
            tr = tr[(tr.price >= lo) & (tr.price <= hi)]
        fz = Featurizer(feats).fit(tr)
        Xtr, Xva = fz.transform(tr, train=True).drop(columns=list(drop)), fz.transform(va).drop(columns=list(drop))
        otr, ova = target_offset(tr, target), target_offset(va, target)
        m, (p,), i = fit_predict(model, Xtr, tr.y.values - otr, [Xva], params, seed, tr.group.values)
        p = p + ova
        oof[folds == k] = p
        info.append(i)
        if keep_models:
            models.append((m, fz, Xva, ova))
        print(f"fold {k}: {i} rmse_log {np.sqrt(np.mean((p - va.y.values) ** 2)):.4f}", flush=True)
    return oof, info, models


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--change", required=True)
    ap.add_argument("--feats", default="base")
    ap.add_argument("--model", default="lgbm")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--folds", default="folds.csv")
    ap.add_argument("--allow", default="", help="comma list of features approved despite |rho|>0.95")
    ap.add_argument("--baseline", action="store_true", help="force kept=1 (B0 / rebase rows)")
    ap.add_argument("--segment", default="all", choices=list(SEGMENTS))
    ap.add_argument("--target", default="price", choices=["price", "ppsf"])
    ap.add_argument("--ref", default=None, help="--model ref: score an existing run's OOF on --segment (no training)")
    a = ap.parse_args()
    t0 = time.time()
    d, folds = load_truth()
    folds = pd.read_csv(path(a.folds)).fold.values
    mask = SEGMENTS[a.segment](d)
    d, folds = d[mask], folds[mask]
    params = json.loads(a.params)
    drop, info = [], []

    if a.model == "b0":
        oof = np.zeros(len(d))
        for k in sorted(set(folds)):
            tr, va = d[folds != k], d[folds == k]
            med = tr.groupby("zip").price.median()
            oof[folds == k] = np.log1p(va.zip.map(med).fillna(tr.price.median()).values)
    elif a.model == "ref":
        oof = segment_oof(a.ref, a.segment)[0]
        meta = json.load(open(path("oof", f"meta_{a.ref}.json")))
        a.feats, drop, info = meta["feats"], meta["drop"], meta["info"]
    else:
        # leakage firewall: check unseen-row features of fold 0 against price
        tr0, va0 = d[folds != 0], d[folds == 0]
        X0 = Featurizer(a.feats).fit(tr0).transform(va0)
        flags = leakage_check(X0, va0.price.values, [s for s in a.allow.split(",") if s])
        drop = list(flags)
        print(f"features={X0.shape[1]} leakage flags (|rho|>0.95, dropped): {flags or 'none'}", flush=True)
        oof, info, _ = run_cv(a.feats, a.model, params, folds, d, a.trim, a.seed, drop, target=a.target)

    os.makedirs(path("oof"), exist_ok=True)
    np.save(path("oof", f"{a.id}.npy"), oof)
    json.dump({"feats": a.feats, "model": a.model, "params": params, "trim": a.trim, "seed": a.seed, "segment": a.segment, "target": a.target,
               "drop": drop, "folds": a.folds, "info": info, "ref": a.ref}, open(path("oof", f"meta_{a.id}.json"), "w"))
    m, s, per = score(oof, d.price.values, folds)
    best = current_best(a.segment)
    if a.folds != "folds.csv":
        kept, wins, verdict = 0, -1, "spatial-CV (not compared)"
    elif best is None or a.baseline:
        kept, wins, verdict = 1, -1, "baseline"
    else:
        bper = score(segment_oof(best, a.segment)[0], d.price.values, folds)[2]
        k, gain, wins = keep(per, bper)
        kept, verdict = int(k), f"{'KEEP' if k else 'REVERT'} vs {best}: gain {gain:+.4f} wins {wins}/5"
    row = dict(id=a.id, step=a.step, change=a.change, segment=a.segment, feats=a.feats, model=a.model,
               rmse_log=round(m["rmse_log"], 5), std=round(s, 5), mae=round(m["mae"]), mdape=round(m["mdape"], 3),
               r2=round(m["r2"], 4), wins=wins, kept=kept, folds=a.folds, time=round(time.time() - t0))
    pd.DataFrame([row])[COLS].to_csv(RESULTS, sep="\t", index=False, mode="a", header=not os.path.exists(RESULTS))
    write_before_after()
    print(f"RESULT {a.id} [{a.segment}]: MdAPE {m['mdape']:.2f}% | RMSE_log {m['rmse_log']:.4f} ± {s:.4f} | "
          f"MAE ${m['mae']:,.0f} | R2 {m['r2']:.3f} | {verdict} | {row['time']}s")

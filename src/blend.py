"""Blend OOFs: hill climbing (with repeats) AND positive Ridge stack (fit per fold on our folds). Keeps the best CV.
python src/blend.py --id blend1 [--ids a,b,c]   (default ids: results.tsv rows with kept=1, else all full tab OOFs)
Writes <id>_hc, <id>_ridge (results rows) and <id> = the better of the two."""
import argparse, json, os, shutil, time
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
import common
from common import cfg, finish, load_folds, load_y, path
from eval import better, score_folds


def default_ids():
    r = pd.read_csv(path("results.tsv"), sep="\t", dtype={"kept": str})
    r = r[(r.track == "tab") & ~r.id.str.startswith("blend")]
    kept = r[r.kept.fillna("").str.lower().isin(["1", "yes", "y", "true"])]
    ids = (kept if len(kept) else r).id.drop_duplicates().tolist()
    return [i for i in ids if not np.isnan(np.load(path("oof", f"oof_{i}.npy"))).any()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--ids", default="")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--change", default="")
    a = ap.parse_args()
    t0 = time.time()
    name = cfg()["METRIC"]
    ids = a.ids.split(",") if a.ids else default_ids()
    y, folds = load_y("tab"), load_folds("tab")
    O = np.column_stack([np.load(path("oof", f"oof_{i}.npy")) for i in ids])
    T = np.column_stack([np.load(path("test_preds", f"test_{i}.npy")) for i in ids])
    # blend in log space for rmsle
    fwd, inv = (np.log1p, np.expm1) if name == "rmsle" else (lambda v: v, lambda v: v)
    if name == "rmsle":
        O, T = np.clip(O, 0, None), np.clip(T, 0, None)
    Os, Ts = fwd(O), fwd(T)
    use = folds >= 0
    sc = lambda p: score_folds(inv(p), y, folds, name)[0]
    singles = [sc(Os[:, j]) for j in range(len(ids))]
    for i, s in zip(ids, singles):
        print(f"single {i}: {s:.5f}")

    # --- hill climbing with repeats ---
    b = int(np.argmax(singles) if name in ("r2",) else np.argmin(singles))
    counts = np.zeros(len(ids)); counts[b] = 1
    cur = singles[b]
    for _ in range(a.iters):
        tot = Os @ counts
        cand = [sc((tot + Os[:, j]) / (counts.sum() + 1)) for j in range(len(ids))]
        j = int(np.argmax(cand) if name == "r2" else np.argmin(cand))
        if not better(cand[j], cur, name):
            break
        counts[j] += 1; cur = cand[j]
    w = counts / counts.sum()
    hc_oof, hc_te = inv(Os @ w), inv(Ts @ w)
    print("hc weights:", {i: round(float(x), 3) for i, x in zip(ids, w) if x > 0})

    # --- positive Ridge stack, out-of-fold on our folds ---
    st_oof = np.full(len(y), np.nan)
    ys = fwd(np.clip(y, 0, None)) if name == "rmsle" else y
    for k in sorted(set(folds[use])):
        tr, va = use & (folds != k), folds == k
        st_oof[va] = Ridge(alpha=a.alpha, positive=True).fit(Os[tr], ys[tr]).predict(Os[va])
    rm = Ridge(alpha=a.alpha, positive=True).fit(Os[use], ys[use])
    st_oof, st_te = inv(st_oof), inv(rm.predict(Ts))
    print("ridge coefs:", {i: round(float(x), 3) for i, x in zip(ids, rm.coef_)}, "intercept", round(float(rm.intercept_), 4))

    res = {}
    for tag, oo, tt in (("hc", hc_oof, hc_te), ("ridge", st_oof, st_te)):
        m, s, _ = score_folds(oo, y, folds, name)
        ns = argparse.Namespace(id=f"{a.id}_{tag}", ids=ids, change=a.change or f"blend {tag} of {len(ids)}")
        finish(ns, f"blend_{tag}", oo, tt, m, s, t0, "tab")
        res[tag] = m
    best = "hc" if better(res["hc"], res["ridge"], name) or res["hc"] == res["ridge"] else "ridge"
    for kind, pre in (("oof", "oof"), ("test_preds", "test")):
        shutil.copy(path(kind, f"{pre}_{a.id}_{best}.npy"), path(kind, f"{pre}_{a.id}.npy"))
    shutil.copy(path("oof", f"meta_{a.id}_{best}.json"), path("oof", f"meta_{a.id}.json"))
    print(f"BEST {a.id} = {best} cv={res[best]:.5f} (hc {res['hc']:.5f}, ridge {res['ridge']:.5f})")

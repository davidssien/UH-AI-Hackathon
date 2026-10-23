"""Blend OOF predictions of several runs (same segment): hill climbing (with repeats) vs cross-fitted Ridge stacking vs level-2 LightGBM.
Picks by CV RMSE_log, writes oof/<id>.npy + meta, then log it with:
python src/exp.py --id <id> --step BLEND --change ... --model ref --ref <id>_raw --segment homes
python src/blend_hou.py --id BL1 --ids A B C --segment homes
"""
import argparse, json, os, sys
import numpy as np
from sklearn.linear_model import Ridge

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path
from eval import load_truth, score
from exp import SEGMENTS, segment_oof

ap = argparse.ArgumentParser()
ap.add_argument("--id", required=True)
ap.add_argument("--ids", nargs="+", required=True)
ap.add_argument("--segment", default="homes")
ap.add_argument("--steps", type=int, default=40)
a = ap.parse_args()
d, folds = load_truth()
m = SEGMENTS[a.segment](d)
y, price, folds = d.y.values[m], d.price.values[m], folds[m]
P = np.column_stack([segment_oof(i, a.segment)[0] for i in a.ids])
rmse = lambda p: score(p, price, folds)[0]["rmse_log"]

# hill climbing: start from best single, add (with repeats) the model that lowers CV RMSE most
counts = np.zeros(P.shape[1])
counts[np.argmin([rmse(P[:, j]) for j in range(P.shape[1])])] = 1
for _ in range(a.steps):
    cur = rmse(P @ counts / counts.sum())
    cand = [rmse(P @ (counts + np.eye(P.shape[1])[j]) / (counts.sum() + 1)) for j in range(P.shape[1])]
    if min(cand) >= cur - 1e-6:
        break
    counts[int(np.argmin(cand))] += 1
w = counts / counts.sum()
hill = P @ w

# Ridge stacking, cross-fitted: fold k's weights fit on the other folds' OOF
ridge = np.zeros(len(y))
for k in sorted(set(folds)):
    o = folds != k
    ridge[folds == k] = Ridge(alpha=1.0).fit(P[o], y[o]).predict(P[folds == k])

# level-2 LightGBM on the OOF matrix (shallow, cross-fitted the same way)
import lightgbm as lgb
l2 = np.zeros(len(y))
for k in sorted(set(folds)):
    o = folds != k
    m2 = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=50, subsample=0.8,
                           subsample_freq=1, verbose=-1, n_jobs=12, random_state=42).fit(P[o], y[o])
    l2[folds == k] = m2.predict(P[folds == k])

res = {"hill": rmse(hill), "ridge": rmse(ridge), "lgbm-l2": rmse(l2)}
best = min(res, key=res.get)
out = {"hill": hill, "ridge": ridge, "lgbm-l2": l2}[best]
np.save(path("oof", f"{a.id}_raw.npy"), out)
json.dump({"feats": "blend", "model": f"blend-{best}", "segment": a.segment, "drop": [], "info": [],
           "ids": a.ids, "weights": dict(zip(a.ids, w.round(4).tolist()))},
          open(path("oof", f"meta_{a.id}_raw.json"), "w"))
md = {k: score(v, price, folds)[0]["mdape"] for k, v in (("hill", hill), ("ridge", ridge), ("lgbm-l2", l2))}
print(f"hill {res['hill']:.5f} (MdAPE {md['hill']:.2f}%) weights {dict(zip(a.ids, w.round(3).tolist()))} | "
      f"ridge {res['ridge']:.5f} ({md['ridge']:.2f}%) | lgbm-l2 {res['lgbm-l2']:.5f} ({md['lgbm-l2']:.2f}%) -> {best}")

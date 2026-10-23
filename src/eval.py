"""The ONLY scorer (FROZEN after 2026-10-23 MVP). Houston housing.
Primary: RMSE on log1p(price). Dollar scale (expm1): MAE $, MdAPE %, R2.
python src/eval.py ID [ID ...] [--vs BEST_ID]
Keep rule: mean RMSE_log improves by > 1 fold-std OR wins >= 4/5 folds.
"""
import argparse, json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import cfg, path


def load_truth():
    d = pd.read_parquet(path(cfg()["HOU"]["CLEAN"]))
    f = pd.read_csv(path("folds.csv"))
    assert (f.row_id.values == d.row_id.values).all(), "folds.csv out of sync with data -> rebuild on source switch"
    return d, f.fold.values


def metrics(price, pred_price):
    price, pred_price = np.asarray(price, float), np.asarray(pred_price, float)
    yl, pl = np.log1p(price), np.log1p(pred_price)
    ss = ((price - price.mean()) ** 2).sum()
    return {"rmse_log": float(np.sqrt(np.mean((yl - pl) ** 2))),
            "mae": float(np.mean(np.abs(price - pred_price))),
            "mdape": float(np.median(np.abs(pred_price - price) / price) * 100),
            "r2": float(1 - ((price - pred_price) ** 2).sum() / ss)}


def score(pred_log, price, folds):
    """pred_log: OOF predictions of log1p(price). Returns mean metrics, std of rmse_log, per-fold rmse_log."""
    pred_price = np.expm1(np.asarray(pred_log, float))
    per = [metrics(price[folds == k], pred_price[folds == k]) for k in sorted(set(folds))]
    mean = {m: float(np.mean([p[m] for p in per])) for m in per[0]}
    return mean, float(np.std([p["rmse_log"] for p in per])), [p["rmse_log"] for p in per]


def keep(per_new, per_best):
    gain = np.mean(per_best) - np.mean(per_new)
    wins = int(sum(a < b for a, b in zip(per_new, per_best)))
    return bool(gain > np.std(per_new) or wins >= 4), gain, wins


def benchmark_zestimate(d):
    """Zestimate vs list price on rows that have a real Zestimate. Reference, not apples-to-apples."""
    m = d.zestimate.notna()
    r = metrics(d.price[m], d.zestimate[m])
    return {"rows": int(m.sum()), "mae": r["mae"], "mdape": r["mdape"], "rmse_log": r["rmse_log"]}


def score_id(id_):
    d, folds = load_truth()
    return score(np.load(path("oof", f"{id_}.npy")), d.price.values, folds)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--vs", default=None)
    a = ap.parse_args()
    for i in a.ids:
        m, s, per = score_id(i)
        print(f"{i}: RMSE_log {m['rmse_log']:.4f} ± {s:.4f} | MAE ${m['mae']:,.0f} | MdAPE {m['mdape']:.2f}% | R2 {m['r2']:.3f}")
    if a.vs:
        k, gain, wins = keep(score_id(a.ids[0])[2], score_id(a.vs)[2])
        print(f"{'KEEP' if k else 'REVERT'} {a.ids[0]} vs {a.vs}: gain {gain:+.4f}, wins {wins}/5")
    d, _ = load_truth()
    print("Zestimate benchmark (reference, not apples-to-apples):", json.dumps(benchmark_zestimate(d)))

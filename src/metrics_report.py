"""Homes metrics 'every common way' for our OOF model and for Zestimate vs list price -> pitch/metrics_all_ways.md.
python src/metrics_report.py --id N4_img
Same rows for both where compared. 'Clean subset' = homes only, top/bottom 1% list prices dropped (LABELED).
"""
import argparse, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path
from eval import load_truth
from exp import SEGMENTS, segment_oof


def all_ways(price, pred):
    price, pred = np.asarray(price, float), np.asarray(pred, float)
    ape = np.abs(pred - price) / price * 100
    lp, lq = np.log(price), np.log(pred)
    return {
        "n": len(price),
        "MdAPE %": np.median(ape),
        "MAPE %": ape.mean(),
        "within 5 %": (ape <= 5).mean() * 100,
        "within 10 %": (ape <= 10).mean() * 100,
        "R² ($)": 1 - ((price - pred) ** 2).sum() / ((price - price.mean()) ** 2).sum(),
        "R² (log)": 1 - ((lp - lq) ** 2).sum() / ((lp - lp.mean()) ** 2).sum(),
        "MAPE on log scale %": (np.abs(lq - lp) / lp).mean() * 100,
        "mean |log error| x100": np.abs(lq - lp).mean() * 100,
        "MAE $": np.abs(pred - price).mean(),
        "median AE $": np.median(np.abs(pred - price)),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    a = ap.parse_args()
    d, folds = load_truth()
    m = SEGMENTS["homes"](d)
    h = d[m].copy()
    h["pred"] = np.expm1(segment_oof(a.id, "homes")[0])
    lo, hi = h.price.quantile([0.01, 0.99])
    clean = h.price.between(lo, hi)
    hz = h.zestimate.notna()
    rows = {
        "Ours — all homes": all_ways(h.price, h.pred),
        "Ours — CLEAN subset (homes, top/bottom 1% price dropped)": all_ways(h.price[clean], h.pred[clean]),
        "Ours — homes with a real Zestimate": all_ways(h.price[hz], h.pred[hz]),
        "Zestimate vs list — homes with a real Zestimate": all_ways(h.price[hz], h.zestimate[hz]),
        "Ours — CLEAN subset ∩ Zestimate rows": all_ways(h.price[clean & hz], h.pred[clean & hz]),
        "Zestimate vs list — CLEAN subset ∩ Zestimate rows": all_ways(h.price[clean & hz], h.zestimate[clean & hz]),
    }
    t = pd.DataFrame(rows).T
    fmt = {c: ("{:.3f}" if "R²" in c else "{:,.0f}" if "$" in c or c == "n" else "{:.2f}") for c in t.columns}
    out = t.apply(lambda col: col.map(fmt[col.name].format))
    lines = [f"# Homes metrics, every common way (model `{a.id}`, out-of-fold; Zestimate = reference, not apples-to-apples)", "",
             f"Clean subset = homes only with list price between ${lo:,.0f} and ${hi:,.0f} (1st–99th pct). "
             "Zestimate is computed by Zillow WITH the listing visible, so it is not a fair competitor.", "",
             out.to_markdown(), "",
             "**What could '4%' mean?** (1) Zestimate vs list price: MAPE / mean |log error| come out ~3.5% — but Zillow "
             "computes it after seeing the listing (it tracks the asking price), so it is not a prediction. (2) 'MAPE on log "
             "scale' divides log errors by log(price) ≈ 12.8, shrinking errors ~13× (ours < 1%) — not a percentage of price. "
             "Honest headline numbers for a model that never sees the price: MdAPE (half of homes within ±X%) and % within 10%."]
    os.makedirs(path("pitch"), exist_ok=True)
    open(path("pitch", "metrics_all_ways.md"), "w").write("\n".join(lines) + "\n")
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(out.to_string())

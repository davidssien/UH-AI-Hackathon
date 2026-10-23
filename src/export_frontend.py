"""Export scored homes (artifacts only) for the MapLibre frontend -> frontend/public/data/listings.json.
Compact rows: [id, lng, lat, address, type, beds, baths, sqft, year, list, fair, p10, p90, gap%, deal, url, top factors]
python src/export_frontend.py
"""
import json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import core

if __name__ == "__main__":
    model, fz, s, shap, m = core.load()
    h = s[s.segment == "homes"].copy()
    # Confidence from the calibrated range width (log p90/p10): narrow range = model is sure. Cut points = median and
    # 85th pct of homes. Measured OOF: HIGH 4.0% typical error (0.5% miss >30%), MEDIUM 7.0%, LOW 14.2% (22.5%).
    w = np.log(h.p90 / h.p10)
    q50, q85 = w.quantile([0.5, 0.85]).values
    h["conf"] = np.where(w <= q50, "HIGH", np.where(w <= q85, "MEDIUM", "LOW"))
    sh = shap[(shap.row_id.isin(h.row_id)) & (~shap.feature.str.startswith("_"))].sort_values(["row_id", "rank"])
    sh = sh.groupby("row_id").head(3)
    top = sh.groupby("row_id").apply(lambda g: [[core.factor_label(r.feature, r.value), round(float(r.pct), 1)]
                                                for r in g.itertuples()], include_groups=False)
    num = lambda v, nd=0: None if pd.isna(v) else (int(round(v)) if nd == 0 else round(float(v), nd))
    rows = [[f"L{r.row_id}", round(r.lon, 6), round(r.lat, 6), r.address, r.home_type, num(r.beds), num(r.baths, 1),
             num(r.living_area), num(r.year_built), num(r.price), num(r.pred), num(r.p10), num(r.p90), num(r.gap_pct, 1),
             r.deal, r.url, top.get(r.row_id, []), r.conf] for r in h.itertuples()]
    H = m["segments"]["homes"]
    meta = {"model": m["id"], "homes_mdape": round(H["cv"]["mdape"], 2), "coverage_p10_p90": round(H["interval_coverage_p10_p90"], 3),
            "note": "Fair price = out-of-fold model estimate (the model never saw this home). Range = calibrated 80% interval. "
                    "Factors = LightGBM SHAP explanation. Listing data: Kaggle Houston 2024 (Zillow listings).",
            "fields": ["id", "lng", "lat", "address", "type", "beds", "baths", "sqft", "year", "list", "fair", "p10", "p90",
                       "gap", "deal", "url", "factors", "conf"],
            "confidence": {c: {"share": round(float((h.conf == c).mean()), 3),
                               "mdape": round(float(((h.pred - h.price).abs() / h.price)[h.conf == c].median() * 100), 1)}
                           for c in ("HIGH", "MEDIUM", "LOW")}}
    out = os.path.join(ROOT, "frontend", "public", "data", "listings.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"meta": meta, "rows": rows}, open(out, "w"), separators=(",", ":"))
    print(f"wrote {out}: {len(rows)} homes, {os.path.getsize(out) / 1e6:.1f} MB")

"""Artifact loading + prediction for the app. No training here: everything comes from artifacts/."""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))  # featurize_new (needed to unpickle the featurizer)
ART = os.environ.get("ARTIFACTS_DIR", os.path.join(ROOT, "artifacts"))
from featurize_new import HUBS, haversine  # noqa: E402

UH = HUBS["uh"]

PRETTY = {
    "living_area": "Living area (sqft)", "lot_sqft": "Lot (sqft)", "beds": "Bedrooms", "baths": "Bathrooms",
    "year_built": "Year built", "home_type": "Home type", "zip": "ZIP", "lat": "Latitude", "lon": "Longitude",
    "mi_downtown": "Miles to Downtown", "mi_tmc": "Miles to Medical Center", "mi_galleria": "Miles to Galleria",
    "mi_energy": "Miles to Energy Corridor", "mi_uh": "Miles to UH", "mi_hub_min": "Miles to nearest job hub",
    "bearing_downtown": "Direction from Downtown (deg)", "comp_value": "Comp value (neighbors' $/sqft x size)",
    "age": "Age (years)", "log_area": "Living area (log)", "sqft_per_bed": "Sqft per bedroom",
    "baths_per_bed": "Baths per bedroom", "lot_living_ratio": "Lot / living area", "new_construction": "New construction",
}


def pretty(f):
    if f in PRETTY:
        return PRETTY[f]
    if f.startswith("rot"):
        return f"Location axis {f[3:].replace('_', ' ')}"
    if f.startswith("comp_"):
        p = f.split("_")
        return f"Nearby comps: {p[1]} {p[2]} (k={p[3][1:]})" if len(p) == 4 else f
    if f.startswith("zip"):
        return f.replace("zip_home_type", "ZIP x type").replace("zip", "ZIP").replace("_lppsf_te", " avg $/sqft (log)").replace(
            "_logprice_te", " avg price (log)").replace("_count", " listing count")
    return f


def load():
    with gzip.open(os.path.join(ART, "model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(ART, "featurizer.pkl"), "rb") as f:
        fz = pickle.load(f)
    scored = pd.read_parquet(os.path.join(ART, "houses_scored.parquet"))
    shap = pd.read_parquet(os.path.join(ART, "shap_values.parquet"))
    with open(os.path.join(ART, "metrics.json")) as f:
        metrics = json.load(f)
    return model, fz, scored, shap, metrics


def segment_of(home_type):
    return "land" if home_type == "LOT" else "homes"


def predict_home(model, fz, **home):
    """-> dict(pred, p10, p90, contrib DataFrame[feature, value, pct, usd_approx]) for one unseen home.
    model/fz are the per-segment dicts from load(): homes model for houses, land model for LOT."""
    seg = segment_of(home["home_type"])
    model, fz = model["segments"][seg], fz[seg]
    if "app" in model:  # typeable-fields model: a typed-in home has no text/photos/history -> stay in-distribution
        model = model["app"]
        fz = model["fz"]
    X = fz.new_home(**home).drop(columns=model["drop"])[model["columns"]]
    m = model["models"]
    area = home.get("living_area")
    off = float(np.log(area if area and area == area else 1500)) if model.get("target") == "ppsf" else 0.0
    pl = float(m["point"].predict(X)[0]) + off
    s = model.get("interval_scale", 1.0)  # conformal width scale -> calibrated ~80% range
    pred = float(np.expm1(pl))
    p10 = float(np.expm1(pl - s * max(pl - off - m["p10"].predict(X)[0], 0)))
    p90 = float(np.expm1(pl + s * max(m["p90"].predict(X)[0] + off - pl, 0)))
    raw = m["point"].predict(X, pred_contrib=True)[0]
    c = pd.DataFrame({"feature": X.columns, "value": X.iloc[0].astype(object).astype(str).values, "phi_log": raw[:-1]})
    c = c.reindex(c.phi_log.abs().sort_values(ascending=False).index).reset_index(drop=True)
    head = [{"feature": "_base", "value": "", "phi_log": raw[-1]}]
    if off:
        head.append({"feature": "_size", "value": f"{np.exp(off):.0f}", "phi_log": off})
    c = pd.concat([pd.DataFrame(head), c.head(10),
                   pd.DataFrame([{"feature": "_other", "value": "", "phi_log": c.phi_log.iloc[10:].sum()}])], ignore_index=True)
    c["pct"] = (np.exp(c.phi_log) - 1) * 100
    c["usd_approx"] = pred * (1 - np.exp(-c.phi_log))
    c.loc[c.feature.isin(["_base", "_size"]), ["pct", "usd_approx"]] = np.nan
    return {"pred": pred, "p10": p10, "p90": p90, "contrib": c}


def waterfall_frame(contrib):
    """SHAP (log space) -> $ waterfall steps: start at the model's average home, apply each factor multiplicatively."""
    c = contrib.sort_values("feature", key=lambda s: s.map({"_base": 0, "_size": 0.5, "_other": 2}).fillna(1), kind="stable")
    base = c[c.feature == "_base"].phi_log.iloc[0]
    rows, cum = [], base
    for _, r in c[c.feature != "_base"].iterrows():
        start, cum = np.exp(cum), cum + r.phi_log
        lab = ("All other factors" if r.feature == "_other" else f"Size: average $/sqft x {_fmt(r.value)} sqft"
               if r.feature == "_size" else f"{pretty(r.feature)} = {_fmt(r.value, r.feature)}")
        rows.append({"label": lab, "start": start, "end": np.exp(cum), "pct": r.pct})
    w = pd.DataFrame(rows)
    w["delta"] = w.end - w.start
    return float(np.exp(base)), w


def _fmt(v, feature=""):
    if feature in ("zip", "year_built"):
        return str(v).replace(".0", "")
    try:
        x = float(v)
        return "n/a" if np.isnan(x) else f"{x:,.0f}" if abs(x) >= 100 else f"{x:,.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return v

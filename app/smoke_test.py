"""App smoke test (run after every promotion): headless app run, predict 3 houses, 1 monthly cost.
ARTIFACTS_DIR=artifacts_new python app/smoke_test.py   -> exit 0 = PASS
"""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
from finance import affordability, monthly_cost

model, fz, scored, shap, metrics = core.load()
for _, r in scored[scored.home_type == "SINGLE_FAMILY"].sample(3, random_state=0).iterrows():
    res = core.predict_home(model, fz, beds=r.beds, baths=r.baths, living_area=r.living_area, lot_sqft=r.lot_sqft,
                            home_type=r.home_type, year_built=r.year_built, zip=r.zip, lat=r.lat, lon=r.lon)
    assert 1e4 < res["pred"] < 1e8 and res["p10"] <= res["pred"] <= res["p90"], res
    base, w = core.waterfall_frame(res["contrib"])
    assert abs(w.end.iloc[-1] - (res["pred"] + 1)) / res["pred"] < 1e-3, (w.end.iloc[-1], res["pred"])
    print(f"predict ok: {r.address} list ${r.price:,.0f} -> fair ${res['pred']:,.0f} [{res['p10']:,.0f}, {res['p90']:,.0f}]")
# app-form path must be unbiased on real homes (audit: +26% before the typeable-fields app model)
s = scored[scored.segment == "homes"].sample(100, random_state=1)
pp = np.array([core.predict_home(model, fz, beds=r.beds, baths=r.baths, living_area=r.living_area, lot_sqft=r.lot_sqft,
                                 home_type=r.home_type, year_built=r.year_built, zip=r.zip, lat=r.lat, lon=r.lon)["pred"]
               for r in s.itertuples()])
bias = np.median((pp - s.price.values) / s.price.values * 100)
assert abs(bias) < 5, f"app-form median signed error {bias:+.1f}%"
print(f"app-form bias ok: median signed {bias:+.2f}%")
zip_only = core.predict_home(model, fz, beds=3, baths=2, living_area=1600, lot_sqft=np.nan, home_type="SINGLE_FAMILY",
                             year_built=2005, zip="77004")
assert zip_only["pred"] > 1e4
land = core.predict_home(model, fz, beds=np.nan, baths=np.nan, living_area=np.nan, lot_sqft=20000, home_type="LOT",
                         year_built=np.nan, zip="77433")
assert 1e3 < land["pred"] < 1e8, land
print(f"land ok: ${land['pred']:,.0f}")
c = monthly_cost(300000, 6.5, 10, 30, 2.2, 3000, 0, 0, 0.5)
assert abs(c["total"] - sum(c[k] for k in ["principal_interest", "property_tax", "insurance", "hoa", "flood", "pmi"])) < 1e-6
assert 1700 < c["principal_interest"] < 1720, c  # 270k @ 6.5%/30y = $1,706.59
print(f"monthly ok: ${c['total']:,.0f} share {affordability(c['total'], 65000)}")
assert set(scored.deal) <= {"UNDERPRICED", "FAIR", "OVERPRICED"} and shap.row_id.isin(scored.row_id).all()

from streamlit.testing.v1 import AppTest
at = AppTest.from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamlit_app.py"), default_timeout=120).run()
assert not at.exception, [e.value for e in at.exception]
print("app headless run ok")
print("SMOKE PASS")

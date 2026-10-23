"""Extract per-listing extras from the Kaggle Light JSON (datadetective08/houston-housing-market-2024, ~143 MB).
-> data/light.parquet keyed by zpid. Display fields (address, photo, url) + non-price listing flags.
Leakage firewall: taxAssessedValue, priceChange/priceReduction/datePriceChanged, zestimate, rentZestimate,
daysOnZillow are NOT extracted.
"""
import json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path

SRC = path("data", "raw", "light", "houston_housing market 2024_light.json")

if __name__ == "__main__":
    rows = []
    for x in json.load(open(SRC)):
        h = x.get("hdpData", {}).get("homeInfo", {})
        sub = h.get("listing_sub_type", {})
        lot, unit = h.get("lotAreaValue"), h.get("lotAreaUnit")
        rows.append({
            "zpid": int(x["zpid"]),
            "street": h.get("streetAddress") or x.get("addressStreet"),
            "img": x.get("imgSrc"),
            "detail_url": x.get("detailUrl"),
            "lot_sqft_unit": (lot * 43560 if unit == "acres" else lot) if lot is not None and unit else np.nan,
            "f_new_home": float(bool(sub.get("is_newHome"))),
            "f_bank_owned": float(bool(sub.get("is_bankOwned"))),
            "f_auction": float(bool(sub.get("is_forAuction")) or bool(h.get("isPreforeclosureAuction"))),
            "f_non_owner_occ": float(bool(h.get("isNonOwnerOccupied"))),
            "f_premier_builder": float(bool(h.get("isPremierBuilder"))),
            "f_has_builder": float(bool(x.get("builderName"))),
            "f_condo_unit": float(bool(h.get("unit"))),
        })
    d = pd.DataFrame(rows).drop_duplicates("zpid")
    d.to_parquet(path("data", "light.parquet"), index=False)
    print(f"wrote data/light.parquet rows={len(d)}; flag means:",
          d.filter(like="f_").mean().round(4).to_dict())

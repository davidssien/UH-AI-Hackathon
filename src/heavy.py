"""Stream the Heavy JSON (zip, 6.7 GB uncompressed) and keep only what new experiments need -> data/heavy.parquet.
Leakage firewall (enforced here, at extraction):
- priceHistory: ONLY 'Sold' event dates, and the last asking price of PREVIOUS listings that ENDED (sold/removed)
  >= 12 months before the current listing date. Current listing/price-change
  events, pricePerSquareFoot, and anything later are dropped.
- taxHistory, zestimate, rentZestimate, lastSoldPrice (may be the current deal), foreclosure amounts: not extracted.
Kept: description text, school ratings, monthly HOA fee (app only), first 3 photo URLs.
"""
import json, os, sys, zipfile
from datetime import date, timedelta

import ijson
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path

SRC = path("data", "raw", "heavy", "heavy.zip")


def listing_date(x):
    """Current listing date: latest 'Listed for sale' event, else datePostedString."""
    ds = [e.get("date") for e in (x.get("priceHistory") or []) if (e.get("event") or "").lower().startswith("listed for sale")]
    d = max([s for s in ds if s] or [None] * 1, key=lambda s: s or "") or x.get("datePostedString")
    return date.fromisoformat(d[:10]) if d else None


def photos(x, n=3):
    out = []
    for p in (x.get("responsivePhotos") or [])[:n]:
        js = (p.get("mixedSources") or {}).get("jpeg") or []
        js = sorted(js, key=lambda j: abs((j.get("width") or 0) - 384))
        if js:
            out.append(js[0]["url"])
    return out


if __name__ == "__main__":
    z = zipfile.ZipFile(SRC)
    rows, n = [], 0
    with z.open(z.namelist()[0]) as f:
        for x in ijson.items(f, "item", use_float=True):
            n += 1
            ld = listing_date(x)
            cutoff = ld - timedelta(days=365) if ld else None
            sold, listed = [], []  # Texas is non-disclosure: Sold events carry a date but price is null
            for e in x.get("priceHistory") or []:
                if (e.get("event") or "").lower() == "sold" and e.get("date") and cutoff \
                        and date.fromisoformat(e["date"][:10]) <= cutoff:
                    sold.append((e["date"][:10], float(e["price"]) if e.get("price") else None))
            # PREVIOUS listings only: an episode = 'Listed for sale' (+ price changes) ending in 'Sold' or 'Listing removed'.
            # Kept only if the episode ENDED >= 12 months before the current listing date; price = its last asking price.
            ev_sorted = sorted([e for e in x.get("priceHistory") or [] if e.get("date")], key=lambda e: e["date"])
            ask = None
            for e in ev_sorted:
                ev = (e.get("event") or "").lower()
                if ev in ("listed for sale", "price change") and e.get("price"):
                    ask = float(e["price"])
                elif ev in ("sold", "listing removed"):
                    if ask and cutoff and date.fromisoformat(e["date"][:10]) <= cutoff:
                        listed.append((e["date"][:10], ask))  # (end date, last asking price of that ended listing)
                    ask = None
                elif ev.startswith("listed for rent"):
                    ask = None
            sc = [s.get("rating") for s in x.get("schools") or [] if s.get("rating") is not None]
            rows.append({
                "zpid": int(x["zpid"]),
                "listing_date": ld.isoformat() if ld else None,
                "prior_sales": json.dumps(sorted(sold, key=lambda t: t[0])),
                "prior_listings": json.dumps(sorted(listed)),
                "description": x.get("description") or "",
                "school_mean": float(np.mean(sc)) if sc else np.nan,
                "school_min": float(min(sc)) if sc else np.nan,
                "school_max": float(max(sc)) if sc else np.nan,
                "hoa_monthly": float(x["monthlyHoaFee"]) if x.get("monthlyHoaFee") is not None else np.nan,
                "photos": json.dumps(photos(x)),
            })
            if n % 5000 == 0:
                print(f"{n} records", flush=True)
    d = pd.DataFrame(rows).drop_duplicates("zpid")
    d.to_parquet(path("data", "heavy.parquet"), index=False)
    ps = d.prior_sales.map(lambda s: len(json.loads(s)) > 0)
    print(f"wrote data/heavy.parquet rows={len(d)} prior_sale={ps.mean():.3f} school={d.school_mean.notna().mean():.3f} "
          f"desc={(d.description != '').mean():.3f} hoa={d.hoa_monthly.notna().mean():.3f} "
          f"photos={d.photos.map(lambda s: len(json.loads(s))).mean():.2f}")

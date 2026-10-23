"""Load the Houston listings (raw Kaggle or teammate-cleaned), clean, save data/houses.parquet.
python src/prep.py            # uses config HOU.SOURCE
Prints columns/dtypes/rows/NaN%/price describe; logs every NaN-ing count. Never drops rows except price <= 0.
"""
import os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import cfg, path

H = cfg()["HOU"]
C = H["COLS"]


def profile(d):
    with pd.option_context("display.width", 200, "display.max_rows", 60):
        print(f"rows={len(d)} cols={d.shape[1]}")
        print(pd.DataFrame({"dtype": d.dtypes.astype(str), "nan%": (d.isna().mean() * 100).round(1)}).to_string())
        print(d[C["price"]].describe().to_string())


def load():
    src = H["SOURCE"]
    f = path(H["TEAMMATE"] if src == "teammate" else H["RAW"])
    d = pd.read_csv(f, dtype={C["zip"]: str})
    print(f"source={src} file={f}")
    profile(d)
    return d, src


KEYWORDS = {"kw_renovated": r"renovat|remodel|updated", "kw_new_roof": r"new roof", "kw_granite": r"granite|quartz",
            "kw_pool": r"\bpool\b", "kw_never_flooded": r"never flooded|did not flood|no flood", "kw_high_dry": r"high and dry",
            "kw_as_is": r"as[- ]is", "kw_investor": r"investor|cash only|cash buyer", "kw_fixer": r"fixer|tlc|handyman"}


# leakage scrub (audit #3): dollar amounts and current-listing price-event phrases never reach text features
PRICE_RX = (r"\$\s?\d[\d,\.]*\s?(k|m|mm|million|thousand)?\b|\b\d{2,3}(,\d{3})+\b|\b\d{2,4}\s?k\b"
            r"|\b(new|reduced|lowered|adjusted|improved)\s+price\b|\bprice[ds]?\s+(reduc\w*|improve\w*|drop\w*|cut|adjust\w*|"
            r"lowered|change\w*|to sell|below|under|right)\b|\bpriced\s+\w+(\s+\w+)?|\b(reduced|appraised|appraisal)\b"
            r"|\bbelow (market|appraisal|value)\b|\bper (sq\.?\s?ft|square foot)\b|\bmotivated seller\b")


def scrub(text):
    import re
    return re.sub(PRICE_RX, " ", text or "", flags=re.I)


def join_heavy(out, h, log):
    import json, re
    j = out[["zpid", "zip"]].merge(h, on="zpid", how="left")
    assert len(j) == len(out)
    ld = pd.to_datetime(j.listing_date)
    sold = j.prior_sales.fillna("[]").map(json.loads)
    last_sold = pd.to_datetime(sold.map(lambda s: s[-1][0] if s else None))
    out["has_prior_sale"] = sold.map(len).gt(0).astype(float).values
    out["n_prior_sales"] = sold.map(len).astype(float).values
    out["years_since_sale"] = ((ld - last_sold).dt.days / 365.25).values
    # approved 2026-10-23: last asking price of a PREVIOUS listing that ended >= 12 months before the current one,
    # time-adjusted with ZIP ZHVI 5-yr change; years measured from that listing's end date
    lst = j.prior_listings.fillna("[]").map(json.loads)
    last_l = lst.map(lambda s: s[-1] if s else None)
    yrs = ((ld - pd.to_datetime(last_l.map(lambda t: t[0] if t else None))).dt.days / 365.25)
    zf = path("data", "external", "zhvi_zip.csv")
    ch5 = out.zip.map(pd.read_csv(zf, dtype={"zip": str}).set_index("zip").zhvi_5y_change) if os.path.exists(zf) else 0
    adj = np.log(last_l.map(lambda t: t[1] if t else np.nan).values) + (yrs.values / 5) * np.log1p(np.asarray(ch5, float))
    out["prior_list_logadj"], out["years_since_list"] = adj, yrs.values
    for c in ["school_mean", "school_min", "school_max", "hoa_monthly"]:
        out[c] = j[c].values
    raw = j.description.fillna("")
    clean = raw.map(scrub)
    log.append(f"descriptions scrubbed of $ amounts / price-event phrases: {(clean != raw).sum()} changed")
    desc = clean.str.lower()
    out["description"] = clean.values
    out["photos"] = j.photos.fillna("[]").values
    for k, rx in KEYWORDS.items():
        out[k] = desc.str.contains(rx, regex=True).astype(float).where(desc != "").values
    log.append(f"heavy.parquet joined: prior sale {out.has_prior_sale.mean():.3f}, past listing {np.isfinite(adj).mean():.3f}, "
               f"school {out.school_mean.notna().mean():.3f}, description {(desc != '').mean():.3f}")
    return out


def clean(d, src):
    log = []
    out = pd.DataFrame({
        "row_id": d["row_id"] if "row_id" in d else np.arange(len(d)),
        "zpid": d[C["id"]],
        "price": d[C["price"]].astype(float),
        "beds": d[C["beds"]].astype(float),
        "baths": d[C["baths"]].astype(float),
        "living_area": d[C["living_area"]].astype(float),
        "year_built": d[C["year_built"]].astype(float),
        "home_type": d[C["home_type"]].astype(str),
        "lat": d[C["lat"]].astype(float),
        "lon": d[C["lon"]].astype(float),
        "zip": d[C["zip"]].astype(str).str.extract(r"(\d{5})")[0],
        "city": d[C["city"]].astype(str),
    })
    # zestimate kept aside as BENCHMARK only (NaN where Zillow had none -> imputed constant in raw file)
    z = d[C["zestimate"]].astype(float)
    if C["has_zestimate"] in d:
        z = z.where(d[C["has_zestimate"]] == 1)
    out["zestimate"] = z

    if "lot_sqft" in d:
        out["lot_sqft"] = d["lot_sqft"].astype(float)
    else:  # raw: no unit column; values < 100 are acres
        lot = d[C["lot"]].astype(float)
        for t, v in H["IMPUTED"]["lot"].items():
            m = (out.home_type == t) & np.isclose(lot, v)
            log.append(f"lot imputed placeholder {t}={v} -> NaN: {m.sum()}")
            lot = lot.mask(m)
        acres = lot < 100
        log.append(f"lot < 100 treated as acres (x43560): {acres.sum()}")
        out["lot_sqft"] = np.where(acres, lot * 43560, lot)
    for t, v in H["IMPUTED"]["year_built"].items():
        m = (out.home_type == t) & np.isclose(out.year_built, v)
        log.append(f"year_built imputed placeholder {t}={v} -> NaN: {m.sum()}")
        out.loc[m, "year_built"] = np.nan

    rules = {
        "year_built": (out.year_built < 1800) | (out.year_built > 2025),
        "living_area": out.living_area < 200,
        "beds": out.beds < 0,
        "baths": out.baths < 0,
        "lot_sqft": out.lot_sqft <= 0,
    }
    for c, m in rules.items():
        log.append(f"{c} impossible -> NaN: {int(m.sum())}")
        out.loc[m, c] = np.nan
    # vacant land: 0 beds/baths are structural absence, not a measurement
    lot_rows = out.living_area.isna() & (out.beds == 0) & (out.baths == 0)
    out.loc[lot_rows, ["beds", "baths"]] = np.nan
    log.append(f"beds/baths=0 with no living area -> NaN: {lot_rows.sum()}")

    n = len(out)
    keycols = [c for c in out.columns if c not in ("row_id", "zpid")]
    out = out[~out.duplicated(keycols)]
    log.append(f"exact duplicates (all fields but id) dropped: {n - len(out)}")
    n = len(out)
    out = out[out.price > 0]
    log.append(f"price <= 0 dropped: {n - len(out)}")

    vc = out.home_type.value_counts()
    rare = vc[vc < 30].index
    out["home_type"] = out.home_type.where(~out.home_type.isin(rare), "OTHER")
    log.append(f"rare home_type -> OTHER: {list(rare)}")

    # CV groups (audit #2): connected components over rows sharing EITHER lat/lon (5 dp) OR street address + ZIP
    # (street address from the raw file if present, else from the Light JSON) -> relisted homes never straddle folds
    ll = out.lat.round(5).astype(str) + "," + out.lon.round(5).astype(str)
    street = None
    if "streetAddress" in d:
        street = d.loc[out.index, "streetAddress"]
    elif os.path.exists(path("data", "light.parquet")):
        street = out[["zpid"]].merge(pd.read_parquet(path("data", "light.parquet"))[["zpid", "street"]], on="zpid",
                                     how="left").street.values
    keys = [ll.values]
    if street is not None:
        st = pd.Series(street, index=out.index).fillna("").astype(str).str.lower().str.replace(r"[^a-z0-9 ]", "", regex=True).str.strip()
        keys.append(np.where(st != "", st + "|" + out.zip, "nokey_" + out.index.astype(str)))
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(out)
    rows, cols, offset = [], [], n  # bipartite graph: row nodes 0..n-1, key nodes after them
    for k in keys:
        codes = pd.factorize(k)[0]
        rows.append(np.arange(n))
        cols.append(offset + codes)
        offset += codes.max() + 1
    r, c = np.concatenate(rows), np.concatenate(cols)
    g = coo_matrix((np.ones(len(r)), (r, c)), shape=(c.max() + 1, c.max() + 1))
    out["group"] = connected_components(g, directed=False)[1][:n]
    out["group"] = pd.factorize(out.group)[0]
    log.append(f"groups (lat/lon OR street+zip): {out.group.nunique()} for {len(out)} rows (max size {out.group.value_counts().max()})")
    out["address"] = out.city + " TX " + out.zip
    out["url"] = "https://www.zillow.com/homedetails/" + out.zpid.astype(str) + "_zpid/"
    out["img"] = None
    lf = path("data", "light.parquet")  # src/light.py: street address, photo, listing flags (no price fields)
    if os.path.exists(lf):
        li = pd.read_parquet(lf)
        j = out[["zpid"]].merge(li, on="zpid", how="left")
        assert len(j) == len(out)
        st = j.street.fillna("").str.strip().values
        out["address"] = np.where(st != "", st + ", " + out.city + " TX " + out.zip, out.address)
        out["url"] = j.detail_url.fillna(pd.Series(out.url.values)).values
        out["img"] = j.img.values
        n0 = out.lot_sqft.isna().sum()  # teammate file leaves lot blank (units unknown) -> Light JSON explicit units
        out["lot_sqft"] = out.lot_sqft.fillna(pd.Series(j.lot_sqft_unit.values, index=out.index))
        log.append(f"lot_sqft filled from Light JSON explicit units (sqft/acres): {n0 - out.lot_sqft.isna().sum()}")
        for c in [c for c in li if c.startswith("f_") and li[c].nunique() > 1]:
            out[c] = j[c].values
        log.append(f"light.parquet joined: street address for {(st != '').sum()} rows")
    hf = path("data", "heavy.parquet")  # src/heavy.py (leakage-filtered at extraction)
    if os.path.exists(hf):
        out = join_heavy(out, pd.read_parquet(hf), log)
    out["y"] = np.log1p(out.price)
    return out.reset_index(drop=True), log


if __name__ == "__main__":
    d, src = load()
    out, log = clean(d, src)
    print("\n".join(log))
    os.makedirs(path("logs"), exist_ok=True)
    with open(path("logs", "prep.log"), "w") as f:
        f.write("\n".join(log) + "\n")
    out.to_parquet(path(H["CLEAN"]), index=False)
    print(f"wrote {H['CLEAN']} rows={len(out)}")

"""Feature builder shared by training (fold-only) and the app (full data).

Featurizer(sets).fit(train_rows) learns everything target-based from those rows only (KNN comps, ZIP encodings).
transform(df, train=True) is for the rows it was fit on: comps exclude the row's own CV group and ZIP encodings
are inner out-of-fold, so a training row never sees its own price. transform(df) is for unseen rows
(validation fold, or a new home in the app).

Feature sets (joined with '+'): base hubs rot comps tcomps (same home type) zip struct flags
Leakage firewall: no feature reads price except through fit() rows; zestimate/rentZestimate/ppsf are never inputs.
"""
import os

import numpy as np, pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree

HUBS = {"downtown": (29.7604, -95.3698), "tmc": (29.7079, -95.3978), "galleria": (29.7399, -95.4617),
        "energy": (29.7848, -95.6265), "uh": (29.7199, -95.3422)}
BASE = ["beds", "baths", "living_area", "lot_sqft", "home_type", "year_built", "lat", "lon", "zip"]
CATS = ["home_type", "zip"]
# Heavy JSON features (src/heavy.py; leakage-filtered at extraction). New homes in the app -> NaN.
HEAVY_SETS = {
    "prior": ["has_prior_sale", "n_prior_sales", "years_since_sale"],
    "priorlist": ["prior_list_logadj", "years_since_list"],  # past (>= 12 mo) list price, ZHVI-adjusted
    "school": ["school_mean", "school_min", "school_max"],
    "hoa": ["hoa_monthly"],  # monthly HOA fee (Heavy JSON; not a price field)
    "kw": ["kw_renovated", "kw_new_roof", "kw_granite", "kw_pool", "kw_never_flooded", "kw_high_dry", "kw_as_is",
           "kw_investor", "kw_fixer"],
}
EMB_DIM = 32
# non-price listing flags from the Light JSON (src/light.py); missing -> 0 (resale, no builder)
FLAGS = ["f_new_home", "f_bank_owned", "f_auction", "f_premier_builder", "f_has_builder", "f_condo_unit"]
KS = (5, 10, 25)
EXT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "external")
# external ZIP tables (teammate drops), joined on 5-digit ZIP string. Each set is one keep/revert experiment.
EXTERNAL = {
    "census": ("census_zip.csv", ["median_household_income", "median_gross_rent", "housing_units", "population", "rent_to_income"]),
    "censusv": ("census_zip.csv", ["census_median_home_value"]),  # ACS 2019-23 ZIP home value: ZIP-level price proxy
    "zhvi": ("zhvi_zip.csv", ["zhvi_2024_06", "zhvi_1y_change", "zhvi_5y_change"]),  # ZIP-level index, June 2024
}
R_MILES = 3958.8
REF_YEAR = 2024  # listings are 2024
M_SMOOTH = 20


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_MILES * np.arcsin(np.sqrt(a))


def hubs(df):
    o = pd.DataFrame(index=df.index)
    for k, (la, lo) in HUBS.items():
        o[f"mi_{k}"] = haversine(df.lat.values, df.lon.values, la, lo)
    o["mi_hub_min"] = o.min(axis=1)
    la, lo = map(np.radians, HUBS["downtown"])
    la2, lo2 = np.radians(df.lat.values), np.radians(df.lon.values)
    o["bearing_downtown"] = np.degrees(np.arctan2(np.sin(lo2 - lo) * np.cos(la2),
                                                  np.cos(la) * np.sin(la2) - np.sin(la) * np.cos(la2) * np.cos(lo2 - lo))) % 360
    return o


def rot(df):
    o = pd.DataFrame(index=df.index)
    for a in (15, 30, 45, 60):
        t = np.radians(a)
        o[f"rot{a}_x"] = df.lat * np.cos(t) - df.lon * np.sin(t)
        o[f"rot{a}_y"] = df.lat * np.sin(t) + df.lon * np.cos(t)
    return o


def struct(df):
    o = pd.DataFrame(index=df.index)
    o["age"] = REF_YEAR - df.year_built
    o["log_area"] = np.log(df.living_area)
    o["sqft_per_bed"] = df.living_area / df.beds.replace(0, np.nan)
    o["baths_per_bed"] = df.baths / df.beds.replace(0, np.nan)
    o["lot_living_ratio"] = df.lot_sqft / df.living_area
    o["new_construction"] = (o.age <= 2).astype(float).where(o.age.notna())
    return o


def _log_ppsf(df):
    return np.log(df.price / df.living_area)  # NaN where no living area (land)


class Featurizer:
    def __init__(self, sets="base"):
        self.sets = set(sets.split("+"))

    # ---------- fit: everything learned from these rows only ----------
    def fit(self, tr):
        self.cats = {c: sorted(tr[c].dropna().unique().tolist()) for c in CATS}
        self.zip_centroid = tr.groupby("zip")[["lat", "lon"]].median()
        for k in ("text", "textL", "textC", "img"):  # PCA fitted on training-fold rows only
            if k in self.sets:
                from sklearn.decomposition import PCA
                E, ok = self._emb_lookup(tr, k)
                setattr(self, f"pca_{k}", PCA(EMB_DIM, random_state=0).fit(E[ok]))
        self.ext = {}  # stored in the pickle so the app needs no data/ files
        for k in self.sets & set(EXTERNAL):
            f, cols = EXTERNAL[k]
            self.ext[k] = pd.read_csv(os.path.join(EXT_DIR, f), dtype={"zip": str}).set_index("zip")[cols]
        if self.sets & {"comps", "tcomps", "tight"}:
            lp = _log_ppsf(tr)
            ok = lp.notna().values
            self.c_xy = np.radians(tr[["lat", "lon"]].values)
            self.c_lp, self.c_y, self.c_ok, self.c_group = lp.values, tr.y.values, ok, tr.group.values
            self.c_maxg = int(tr.group.value_counts().max())
            self.c_type = tr.home_type.values
            self.c_area = tr.living_area.values
            self._trees = None
        if "zip" in self.sets:
            self.zip_stats = self._zip_fit(tr)
            gk = GroupKFold(5, shuffle=True, random_state=0)
            self.inner = [(tr.index[a], self._zip_fit(tr.iloc[a]), tr.index[b]) for a, b in gk.split(tr, groups=tr.group)]
        return self

    def _zip_fit(self, tr):
        lp = _log_ppsf(tr)
        g_lp, g_y = lp.mean(), tr.y.mean()
        st = {"g_lp": g_lp, "g_y": g_y}
        for key in (["zip"], ["zip", "home_type"]):
            name = "_".join(key)
            t = pd.DataFrame({"lp": lp, "y": tr.y}).join(tr[key]).groupby(key)
            agg = t.agg(n=("y", "size"), n_lp=("lp", "count"), s_lp=("lp", "sum"), s_y=("y", "sum"))
            agg[f"{name}_lppsf_te"] = (agg.s_lp + M_SMOOTH * g_lp) / (agg.n_lp + M_SMOOTH)
            agg[f"{name}_logprice_te"] = (agg.s_y + M_SMOOTH * g_y) / (agg.n + M_SMOOTH)
            agg[f"{name}_count"] = agg.n
            st[name] = agg[[f"{name}_lppsf_te", f"{name}_logprice_te", f"{name}_count"]]
        return st

    @staticmethod
    def _zip_apply(df, st):
        o = pd.DataFrame(index=df.index)
        for key in (["zip"], ["zip", "home_type"]):
            name = "_".join(key)
            j = df[key].join(st[name], on=key)
            o[f"{name}_lppsf_te"] = j[f"{name}_lppsf_te"].fillna(st["g_lp"])
            o[f"{name}_logprice_te"] = j[f"{name}_logprice_te"].fillna(st["g_y"])
            o[f"{name}_count"] = j[f"{name}_count"].fillna(0)
        return o

    def _knn(self, xy, grp, sub, tag, prefix):
        """KNN stats over fit rows `sub` (boolean mask). Training rows (grp given) skip their own CV group."""
        key = (prefix, tag)
        if key not in self._trees:
            self._trees[key] = BallTree(self.c_xy[sub], metric="haversine")
        vals, groups = (self.c_lp if tag == "lppsf" else self.c_y)[sub], self.c_group[sub]
        kmax = min(max(KS) + (self.c_maxg if grp is not None else 0), len(vals))
        dist, idx = self._trees[key].query(xy, k=kmax)
        if grp is not None:  # drop neighbours from the row's own CV group (incl. itself), keep first max(KS)
            keep = groups[idx] != grp[:, None]
            order = np.argsort(~keep, axis=1, kind="stable")[:, :max(KS)]
            idx, dist = np.take_along_axis(idx, order, 1), np.take_along_axis(dist, order, 1)
        v, o = vals[idx], {}
        for k in KS if tag == "lppsf" else (10,):
            o[f"{prefix}_{tag}_med_k{k}"] = np.median(v[:, :k], 1)
            if tag == "lppsf":
                o[f"{prefix}_{tag}_mean_k{k}"] = v[:, :k].mean(1)
                o[f"{prefix}_dist_k{k}"] = dist[:, k - 1] * R_MILES
        return o

    def _tight(self, df, train, r_mi=0.25, tol=0.2, k=3):
        """Up to 3 nearest same-type homes within 0.25 mi and +-20% sqft (fit rows only; training rows skip own group):
        median log $/sqft + count found."""
        if self._trees is None:
            self._trees = {}
        med, cnt = np.full(len(df), np.nan), np.zeros(len(df))
        xy = np.radians(df[["lat", "lon"]].values)
        area, grp = df.living_area.values, (df.group.values if train else None)
        for t in df.home_type.unique():
            rows = np.where((df.home_type == t).values & ~np.isnan(area))[0]
            sub = np.where((self.c_type == t) & self.c_ok)[0]
            if not len(rows) or not len(sub):
                continue
            key = ("tight", t)
            if key not in self._trees:
                self._trees[key] = BallTree(self.c_xy[sub], metric="haversine")
            ind, dist = self._trees[key].query_radius(xy[rows], r=r_mi / R_MILES, return_distance=True, sort_results=True)
            for i, (ii, _) in zip(rows, zip(ind, dist)):
                c = sub[ii]
                ok = np.abs(self.c_area[c] / area[i] - 1) <= tol
                if grp is not None:
                    ok &= self.c_group[c] != grp[i]
                c = c[ok][:k]
                cnt[i] = len(c)
                if len(c):
                    med[i] = np.median(self.c_lp[c])
        return pd.DataFrame({"tight_lppsf_med": med, "tight_count": cnt}, index=df.index)

    def _comps(self, df, train, typed=False):
        if self._trees is None:
            self._trees = {}
        prefix = "tcomp" if typed else "comp"
        xy = np.radians(df[["lat", "lon"]].values)
        grp = df.group.values if train else None
        o = pd.DataFrame(index=df.index)
        if not typed:
            for tag, sub in (("lppsf", self.c_ok), ("logprice", np.ones_like(self.c_ok))):
                if sub.sum() < max(KS) + 1:  # e.g. land-only fit: no $/sqft
                    continue
                for c, v in self._knn(xy, grp, sub, tag, prefix).items():
                    o[c] = v
        else:  # neighbours of the same home type (types with < 200 fit rows fall back to all rows)
            for t in df.home_type.unique():
                rows = (df.home_type == t).values
                same = self.c_type == t
                if same.sum() < 200:
                    same = np.ones_like(same)
                for tag, sub in (("lppsf", self.c_ok & same), ("logprice", same)):
                    if sub.sum() < max(KS) + 1:
                        continue
                    for c, v in self._knn(xy[rows], None if grp is None else grp[rows], sub, tag, f"{prefix}_{t}").items():
                        o.loc[rows, c.replace(f"_{t}", "", 1)] = v
        o[f"{prefix}_value"] = np.exp(o[f"{prefix}_lppsf_med_k10"]) * df.living_area if f"{prefix}_lppsf_med_k10" in o else np.nan
        return o

    # ---------- transform ----------
    def transform(self, df, train=False):
        parts = [df[BASE].copy()]
        for c in CATS:
            parts[0][c] = pd.Categorical(df[c], categories=self.cats[c])
        if "hubs" in self.sets:
            parts.append(hubs(df))
        if "rot" in self.sets:
            parts.append(rot(df))
        if "struct" in self.sets:
            parts.append(struct(df))
        for k, t in getattr(self, "ext", {}).items():
            parts.append(df[["zip"]].join(t, on="zip").drop(columns="zip"))
        if "flags" in self.sets:
            parts.append(df.reindex(columns=FLAGS).astype(float).fillna(0))
        for k, cols in HEAVY_SETS.items():
            if k in self.sets:
                parts.append(df.reindex(columns=cols).astype(float))
        for k in ("text", "textL", "textC", "img"):
            if k in self.sets:
                parts.append(self._emb(df, k))
        if "deb" in self.sets:  # DeBERTa OOF log(price/sqft) (src/deberta_hou.py); new homes -> NaN
            t = self._deb_table()
            parts.append(pd.DataFrame({"deb_lppsf": df["zpid"].map(t).values if "zpid" in df else np.nan}, index=df.index))
        if "comps" in self.sets:
            parts.append(self._comps(df, train))
        if "tcomps" in self.sets:
            parts.append(self._comps(df, train, typed=True))
        if "tight" in self.sets:
            parts.append(self._tight(df, train))
        if "zip" in self.sets:
            if train:
                parts.append(pd.concat([self._zip_apply(df.loc[va], st) for _, st, va in self.inner]).loc[df.index])
            else:
                parts.append(self._zip_apply(df, self.zip_stats))
        return pd.concat(parts, axis=1)

    @staticmethod
    def _emb_table(kind):
        """data/emb_<kind>.npz (zpid, E) -> cached dict; absent in the app -> empty (new homes get NaN)."""
        cache = Featurizer.__dict__.get("_emb_cache") or {}
        if kind not in cache:
            f = os.path.join(os.path.dirname(EXT_DIR), f"emb_{kind}.npz")
            if os.path.exists(f):
                z = np.load(f)
                cache[kind] = (pd.Index(z["zpid"]), z["E"].astype(np.float32))
            else:
                cache[kind] = (pd.Index([]), np.zeros((0, 1), np.float32))
            Featurizer._emb_cache = cache
        return cache[kind]

    @staticmethod
    def _deb_table():
        f = os.path.join(os.path.dirname(EXT_DIR), "deb_oof.parquet")
        if not os.path.exists(f):
            return pd.Series(dtype=float)
        t = pd.read_parquet(f)
        return pd.Series(t.deb_lppsf.values, index=t.zpid.values)

    def _emb_lookup(self, df, kind):
        idx, E = self._emb_table(kind)
        pos = idx.get_indexer(df["zpid"]) if "zpid" in df and len(idx) else np.full(len(df), -1)
        ok = pos >= 0
        out = np.zeros((len(df), E.shape[1]), np.float32)
        out[ok] = E[pos[ok]]
        return out, ok

    def _emb(self, df, kind):
        E, ok = self._emb_lookup(df, kind)
        Z = np.full((len(df), EMB_DIM), np.nan)
        if ok.any():
            Z[ok] = getattr(self, f"pca_{kind}").transform(E[ok])
        return pd.DataFrame(Z, index=df.index, columns=[f"{kind}_pc{i}" for i in range(EMB_DIM)])

    def __getstate__(self):  # BallTrees rebuilt lazily after unpickling (portable across sklearn builds)
        s = self.__dict__.copy()
        s["_trees"] = None
        s.pop("inner", None)
        return s

    # ---------- app helper ----------
    def new_home(self, beds, baths, living_area, lot_sqft, home_type, year_built, zip=None, lat=None, lon=None, **flags):
        """One unseen home -> feature row. lat/lon optional (falls back to the ZIP centroid)."""
        if lat is None or lon is None:
            lat, lon = self.zip_centroid.loc[str(zip)]
        if zip is None:
            zip = self.zip_centroid.index[np.argmin(haversine(lat, lon, self.zip_centroid.lat.values, self.zip_centroid.lon.values))]
        d = pd.DataFrame([dict(beds=beds, baths=baths, living_area=living_area, lot_sqft=lot_sqft, home_type=home_type,
                               year_built=year_built, lat=float(lat), lon=float(lon), zip=str(zip), **flags)])
        d[["beds", "baths", "living_area", "lot_sqft", "year_built"]] = d[["beds", "baths", "living_area", "lot_sqft", "year_built"]].astype(float)
        return self.transform(d)

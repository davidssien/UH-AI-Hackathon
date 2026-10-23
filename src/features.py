"""All feature engineering. build() returns (X_train, X_test, cat_cols).
--fe takes feature sets joined by '+', e.g. base+count+combos.
Target encoding is NOT here at build time: add_te() is called inside each fold by common.run_cv (--te).
"""
from itertools import combinations
import numpy as np, pandas as pd
from sklearn.model_selection import KFold


def detect_cats(X, c):
    if c.get("CAT_COLS", "auto") != "auto":
        return [col for col in c["CAT_COLS"] if col in X]
    return [col for col in X if X[col].dtype == object or str(X[col].dtype) in ("category", "bool", "string")]


def fe_base(X, cats, c):
    return X, cats


def fe_count(X, cats, c):
    for col in cats:
        X[f"cnt_{col}"] = X[col].map(X[col].value_counts(dropna=False)).astype(float)
    return X, cats


def fe_combos(X, cats, c, max_cats=6):
    top = sorted(cats, key=lambda col: X[col].nunique())[:max_cats]
    new = []
    for a, b in combinations(top, 2):
        X[f"{a}__{b}"] = X[a].astype(str) + "_" + X[b].astype(str)
        new.append(f"{a}__{b}")
    return X, cats + new


def fe_ratios(X, cats, c):
    for a, b in c.get("RATIO_PAIRS", []):
        X[f"{a}_div_{b}"] = X[a] / X[b].replace(0, np.nan)
    return X, cats


def fe_grpagg(X, cats, c):
    for g, v in c.get("GROUP_AGG", []):
        grp = X.groupby(g, observed=True)[v]
        X[f"{v}_mean_by_{g}"] = grp.transform("mean")
        X[f"{v}_std_by_{g}"] = grp.transform("std")
        X[f"{v}_dev_by_{g}"] = X[v] - X[f"{v}_mean_by_{g}"]
        X[f"{v}_rank_by_{g}"] = grp.rank(pct=True)
    return X, cats


FE = {"base": fe_base, "count": fe_count, "combos": fe_combos, "ratios": fe_ratios, "grpagg": fe_grpagg}


def build(train, test, c, fe="base"):
    drop = [c["TARGET"], c["ID_COL"]] + list(c.get("DROP_COLS", []))
    n = len(train)
    X = pd.concat([train.drop(columns=drop, errors="ignore"), test.drop(columns=drop, errors="ignore")], ignore_index=True)
    cats = detect_cats(X, c)
    for name in fe.split("+"):
        X, cats = FE[name](X, cats, c)
    for col in cats:
        X[col] = X[col].astype(str).where(X[col].notna(), None).astype("category")
    return X.iloc[:n].reset_index(drop=True), X.iloc[n:].reset_index(drop=True), cats


def add_te(Xtr, ytr, Xva, Xte, cats, seed, smooth=20, inner=5):
    """Smoothed mean target encoding. Train rows get inner-fold (out-of-fold) encodings; val/test use all train rows."""
    Xtr, Xva, Xte = Xtr.copy(), Xva.copy(), Xte.copy()
    prior = float(np.mean(ytr))
    ys = pd.Series(ytr)

    def enc(keys_fit, y_fit, keys_apply):
        st = pd.DataFrame({"k": keys_fit.astype(str).values, "y": y_fit.values}).groupby("k")["y"].agg(["sum", "count"])
        m = (st["sum"] + prior * smooth) / (st["count"] + smooth)
        return keys_apply.astype(str).map(m).astype(float).fillna(prior).values

    for col in cats:
        tr_enc = np.zeros(len(Xtr))
        for itr, iva in KFold(inner, shuffle=True, random_state=seed).split(Xtr):
            tr_enc[iva] = enc(Xtr[col].iloc[itr], ys.iloc[itr], Xtr[col].iloc[iva])
        Xtr[f"te_{col}"] = tr_enc
        Xva[f"te_{col}"] = enc(Xtr[col], ys, Xva[col])
        Xte[f"te_{col}"] = enc(Xtr[col], ys, Xte[col])
    return Xtr, Xva, Xte

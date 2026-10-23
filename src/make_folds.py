"""Create folds.csv ONCE from data/houses.parquet: GroupKFold(5, shuffle, seed 42) on the CV group
(streetAddress+zip, fallback lat/lon 5dp). FROZEN: rebuild only on a data source switch (--force).
Also writes folds_zip.csv (GroupKFold by ZIP) for the spatial-CV robustness check.
"""
import argparse, os
import numpy as np, pandas as pd
from sklearn.model_selection import GroupKFold
from common import cfg, path

ap = argparse.ArgumentParser()
ap.add_argument("--force", action="store_true")
a = ap.parse_args()

out = path("folds.csv")
if os.path.exists(out) and not a.force:
    raise SystemExit("folds.csv exists (FROZEN). --force only on a data source switch.")
d = pd.read_parquet(path(cfg()["HOU"]["CLEAN"]))
for name, g in [("folds.csv", d.group), ("folds_zip.csv", d.zip)]:
    f = np.full(len(d), -1)
    for i, (_, va) in enumerate(GroupKFold(5, shuffle=True, random_state=42).split(d, groups=g)):
        f[va] = i
    pd.DataFrame({"row_id": d.row_id, "zpid": d.zpid, "fold": f}).to_csv(path(name), index=False)
    print(f"wrote {name}: n={len(d)} counts={np.bincount(f).tolist()}")

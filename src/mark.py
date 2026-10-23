"""Set the 'kept' column for a run: python src/mark.py ID 1|0"""
import sys
import pandas as pd
from common import path

r = pd.read_csv(path("results.tsv"), sep="\t", dtype=str, keep_default_na=False)
assert (r.id == sys.argv[1]).any(), f"unknown id {sys.argv[1]}"
r.loc[r.id == sys.argv[1], "kept"] = sys.argv[2]
r.to_csv(path("results.tsv"), sep="\t", index=False)
print(f"{sys.argv[1]} kept={sys.argv[2]}")

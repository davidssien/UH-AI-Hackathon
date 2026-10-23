"""Demo data for pipeline tests (NOT contest data): California housing -> data/, 2000 IMDB rows -> data/nlp/."""
import os
import numpy as np, pandas as pd
from sklearn.datasets import fetch_california_housing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rng = np.random.default_rng(0)

df = fetch_california_housing(as_frame=True).frame.rename(columns={"MedHouseVal": "target"})
df["region"] = pd.cut(df.Longitude, 6, labels=list("ABCDEF")).astype(str)  # fake categorical
df.loc[rng.random(len(df)) < 0.02, "HouseAge"] = np.nan  # some NaNs
df.insert(0, "id", np.arange(len(df)) + 1000)
df = df.sample(frac=1, random_state=0).reset_index(drop=True)
n_te = 4000
os.makedirs(f"{ROOT}/data/nlp", exist_ok=True)
df.iloc[n_te:].to_csv(f"{ROOT}/data/train.csv", index=False)
df.iloc[:n_te].drop(columns="target").to_csv(f"{ROOT}/data/test.csv", index=False)
pd.DataFrame({"id": df.id[:n_te].sort_values().values, "target": 0.0}).to_csv(f"{ROOT}/data/sample_submission.csv", index=False)

from datasets import load_dataset
im = load_dataset("stanfordnlp/imdb", split="train").shuffle(seed=0).select(range(2000)).to_pandas()
im.insert(0, "id", np.arange(len(im)))
im.iloc[400:].to_csv(f"{ROOT}/data/nlp/train.csv", index=False)
im.iloc[:400].drop(columns="label").to_csv(f"{ROOT}/data/nlp/test.csv", index=False)
pd.DataFrame({"id": im.id[:400], "label": 0}).to_csv(f"{ROOT}/data/nlp/sample_submission.csv", index=False)
print("demo data written:", len(df) - n_te, n_te, "| imdb", 1600, 400)

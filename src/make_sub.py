"""Write submissions/sub_<name>.csv in the EXACT sample_submission format and validate it.
python src/make_sub.py --id blend1 [--name final_best] [--track tab|nlp]"""
import argparse, json
import numpy as np, pandas as pd
import common
from common import path

ap = argparse.ArgumentParser()
ap.add_argument("--id", required=True)
ap.add_argument("--name", default=None)
ap.add_argument("--track", default="tab", choices=["tab", "nlp"])
a = ap.parse_args()

c = common.cfg() if a.track == "tab" else common.nlp_cfg()
idc = c["ID_COL"]
train, test = common.load_data(a.track)
sample = pd.read_csv(path(c["DATA_DIR"], c["SAMPLE_SUB"]))
pred = np.load(path("test_preds", f"test_{a.id}.npy"))
assert len(pred) == len(test), f"pred rows {len(pred)} != test rows {len(test)}"
assert not np.isnan(pred).any(), "NaN in test preds"

if a.track == "nlp" and c["TASK"] == "cls":
    inv = {i: v for v, i in common.label_map(train).items()}
    pred = np.array([inv[i] for i in (pred.argmax(1) if pred.ndim == 2 else (pred > 0.5).astype(int))])
else:
    pred = np.asarray(pred, dtype=float).ravel()
    if a.track == "tab" and c["METRIC"] == "rmsle":
        pred = np.clip(pred, 0, None)

tcols = [col for col in sample.columns if col != idc]
assert len(tcols) == 1, f"expected 1 target column in sample_submission, got {tcols}"
assert test[idc].is_unique, "test ids not unique"
assert set(sample[idc]) == set(test[idc]), "sample_submission ids != test ids"
sub = sample.copy()
sub[tcols[0]] = pd.Series(pred, index=test[idc].values).loc[sample[idc].values].values
if pd.api.types.is_integer_dtype(sample[tcols[0]]) and a.track == "nlp":
    sub[tcols[0]] = sub[tcols[0]].astype(int)

assert list(sub.columns) == list(sample.columns) and len(sub) == len(sample)
assert sub[tcols[0]].notna().all()
out = path("submissions", f"sub_{a.name or a.id}.csv")
sub.to_csv(out, index=False)
print(f"SUB {out} rows={len(sub)} cols={list(sub.columns)} mean_pred={sub[tcols[0]].head(1000).astype(float).mean():.4f}")

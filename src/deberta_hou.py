"""DeBERTa-v3-base 5-fold OOF regression of log(price/sqft) for HOMES from
'type, beds, baths, sqft, year, zip, city' + description.  bf16, max_len 384, 2 epochs, lr 2e-5.
-> oof/DEB.npy + meta (log price, homes rows) and data/deb_oof.parquet (zpid, deb_lppsf) for the 'deb' feature set.
Per-fold results cached in oof/deb_fold<k>.npy (resumable).
Stacking note: when used as a LightGBM feature, training rows carry OOF values from other folds' models (standard
level-2 stacking on the same frozen folds); validation rows are always predicted by a model that never saw them.
"""
import json, os, shutil, sys
import numpy as np, pandas as pd, torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path
from eval import load_truth, score
from exp import SEGMENTS, target_offset
from datasets import Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, Trainer,
                          TrainingArguments, set_seed)

MODEL, MAXLEN, EPOCHS, LR, BS = "microsoft/deberta-v3-base", 384, 2, 2e-5, 16


def text(r):
    f = lambda v, fmt: "unknown" if pd.isna(v) else fmt.format(v)
    return (f"{r.home_type.replace('_', ' ').lower()}, {f(r.beds, '{:.0f}')} beds, {f(r.baths, '{:g}')} baths, "
            f"{f(r.living_area, '{:,.0f}')} sqft, built {f(r.year_built, '{:.0f}')}, zip {r.zip}, {r.city}. {r.description or ''}")


if __name__ == "__main__":
    set_seed(42)
    d, folds = load_truth()
    m = SEGMENTS["homes"](d)
    d, folds = d[m].reset_index(drop=True), folds[m]
    off = target_offset(d, "ppsf")
    t = d.y.values - off
    tok = AutoTokenizer.from_pretrained(MODEL)
    enc = Dataset.from_dict({"text": [text(r) for r in d.itertuples()]}).map(
        lambda b: tok(b["text"], truncation=True, max_length=MAXLEN), batched=True, remove_columns=["text"])
    oof = np.full(len(d), np.nan)
    for k in sorted(set(folds)):
        fk = path("oof", f"deb_fold{k}.npy")
        tr, va = np.where(folds != k)[0], np.where(folds == k)[0]
        if os.path.exists(fk):
            oof[va] = np.load(fk)
            continue
        mu, sd = t[tr].mean(), t[tr].std()
        dtr = enc.select(tr).add_column("labels", ((t[tr] - mu) / sd).astype(np.float32).tolist())
        model = AutoModelForSequenceClassification.from_pretrained(MODEL, num_labels=1, problem_type="regression")
        ck = path("nlp_ckpt", f"deb_hou_{k}")
        args = TrainingArguments(output_dir=ck, learning_rate=LR, num_train_epochs=EPOCHS, per_device_train_batch_size=BS,
                                 per_device_eval_batch_size=BS, warmup_ratio=0.1, weight_decay=0.01, bf16=True,
                                 save_strategy="no", report_to=[], logging_steps=200, seed=42, dataloader_num_workers=2)
        tr_ = Trainer(model=model, args=args, train_dataset=dtr, data_collator=DataCollatorWithPadding(tok),
                      processing_class=tok)
        tr_.train()
        p = tr_.predict(enc.select(va)).predictions.reshape(-1) * sd + mu
        np.save(fk, p)
        oof[va] = p
        print(f"fold {k}: rmse(log ppsf) {np.sqrt(np.mean((p - t[va]) ** 2)):.4f}", flush=True)
        shutil.rmtree(ck, ignore_errors=True)
        del model, tr_
        torch.cuda.empty_cache()
    np.save(path("oof", "DEB.npy"), oof + off)
    json.dump({"feats": "deberta-text", "model": "deberta", "segment": "homes", "drop": [], "info": [], "target": "ppsf"},
              open(path("oof", "meta_DEB.json"), "w"))
    pd.DataFrame({"zpid": d.zpid.values, "deb_lppsf": oof}).to_parquet(path("data", "deb_oof.parquet"), index=False)
    mm = score(oof + off, d.price.values, folds)[0]
    print(f"DEB done: homes MdAPE {mm['mdape']:.2f}% RMSE_log {mm['rmse_log']:.4f}")

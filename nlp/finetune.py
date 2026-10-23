"""HF Trainer fine-tuning on nlp_folds.csv. Saves oof (val logits) + test logits (avg over fold models).
python nlp/finetune.py --id nlp1 [--model microsoft/deberta-v3-base] [--lr 2e-5] [--epochs 3] [--bs 16] [--max-len 0=auto p95]
                       [--folds 0 | 0,1,2 | all]
"""
import argparse, os, shutil, sys, time
import numpy as np, torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common
from common import finish, load_data, load_folds, load_y, nlp_cfg, path
from eval import HIGHER, metric, score_folds
from datasets import Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, Trainer,
                          TrainingArguments, set_seed)

ap = argparse.ArgumentParser()
ap.add_argument("--id", required=True)
ap.add_argument("--model", default=None)
ap.add_argument("--lr", type=float, default=2e-5)
ap.add_argument("--epochs", type=float, default=3)
ap.add_argument("--bs", type=int, default=16)
ap.add_argument("--grad-accum", type=int, default=1)
ap.add_argument("--max-len", type=int, default=0)
ap.add_argument("--folds", default="0")
ap.add_argument("--wd", type=float, default=0.01)
ap.add_argument("--warmup", type=float, default=0.1)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--no-bf16", action="store_true")
ap.add_argument("--change", default="")
args = ap.parse_args()
t0 = time.time()
c = nlp_cfg()
args.model = args.model or c["MODEL"]
set_seed(args.seed)

train, test = load_data("nlp")
folds, y = load_folds("nlp"), load_y("nlp")
is_cls = c["TASK"] == "cls"
n_labels = len(common.label_map(train)) if is_cls else 1
tok = AutoTokenizer.from_pretrained(args.model)
sep = f" {tok.sep_token} " if tok.sep_token else " | "
txt = lambda df: df[c["TEXT_COLS"]].fillna("").astype(str).agg(sep.join, axis=1).tolist()
tr_text, te_text = txt(train), txt(test)

if not args.max_len:
    sample = tr_text[:5000]
    lens = [len(x) for x in tok(sample, add_special_tokens=True)["input_ids"]]
    args.max_len = int(min(512, max(32, np.percentile(lens, 95))))
print(f"max_len={args.max_len} n_train={len(train)} n_test={len(test)} labels={n_labels}", flush=True)


def to_ds(texts, labels=None):
    d = {"text": texts}
    if labels is not None:
        d["labels"] = labels.astype(np.int64 if is_cls else np.float32)
    return Dataset.from_dict(d).map(lambda b: tok(b["text"], truncation=True, max_length=args.max_len),
                                    batched=True, remove_columns=["text"])


ds_test = to_ds(te_text)
ks = sorted(set(folds)) if args.folds == "all" else [int(k) for k in args.folds.split(",")]
oof = np.full((len(y), n_labels) if is_cls else len(y), np.nan)
te = 0
ckpt = path("nlp_ckpt", args.id)
for k in ks:
    tr, va = np.where(folds != k)[0], np.where(folds == k)[0]
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=n_labels, problem_type="single_label_classification" if is_cls else "regression")
    targs = TrainingArguments(
        output_dir=ckpt, learning_rate=args.lr, num_train_epochs=args.epochs, per_device_train_batch_size=args.bs,
        per_device_eval_batch_size=args.bs,  # bigger spills VRAM to sysmem -> 10x slower gradient_accumulation_steps=args.grad_accum, weight_decay=args.wd,
        warmup_ratio=args.warmup, lr_scheduler_type="linear", bf16=not args.no_bf16, eval_strategy="epoch",
        save_strategy="epoch", load_best_model_at_end=True, metric_for_best_model="score",
        greater_is_better=c["METRIC"] in HIGHER, save_total_limit=1, logging_steps=50, report_to=[],
        seed=args.seed + k,  # NO group_by_length: it reorders predict() output in transformers 4.57
        dataloader_num_workers=2, disable_tqdm=True)
    trainer = Trainer(
        model=model, args=targs, train_dataset=to_ds([tr_text[i] for i in tr], y[tr]),
        eval_dataset=(ds_va := to_ds([tr_text[i] for i in va], y[va])), processing_class=tok,
        data_collator=DataCollatorWithPadding(tok),
        compute_metrics=lambda p: {"score": metric(c["METRIC"], p.label_ids, np.squeeze(p.predictions))})
    trainer.train()
    pv = np.squeeze(trainer.predict(ds_va).predictions)
    oof[va] = pv
    te = te + np.squeeze(trainer.predict(ds_test).predictions) / len(ks)
    print(f"fold {k}: {c['METRIC']}={metric(c['METRIC'], y[va], pv):.5f} {time.time() - t0:.0f}s "
          f"vram={torch.cuda.max_memory_allocated() / 1e9:.1f}GB", flush=True)
    shutil.rmtree(ckpt, ignore_errors=True)
    del model, trainer
    torch.cuda.empty_cache()

mean, std, _ = score_folds(oof, y, folds, c["METRIC"])
finish(args, args.model.split("/")[-1], oof, te, mean, std, t0, "nlp")

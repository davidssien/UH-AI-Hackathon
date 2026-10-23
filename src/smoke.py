import sys, time, traceback, numpy as np, warnings
warnings.filterwarnings("ignore")
which = sys.argv[1]
rng = np.random.default_rng(0)
X = rng.normal(size=(1000, 10)).astype("float32"); y = X[:, 0] * 2 + np.sin(X[:, 1]) + rng.normal(scale=.1, size=1000)
t = time.time()
try:
    if which == "xgb":
        import xgboost as xgb
        m = xgb.XGBRegressor(device="cuda", tree_method="hist", n_estimators=200).fit(X, y); note = "cuda"
    elif which == "cat":
        from catboost import CatBoostRegressor
        try:
            CatBoostRegressor(task_type="GPU", iterations=200, verbose=0).fit(X, y); note = "GPU"
        except Exception as e:
            CatBoostRegressor(iterations=200, verbose=0).fit(X, y); note = f"CatBoost: CPU only ({str(e)[:80]})"
    elif which == "lgbm":
        import lightgbm as lgb
        lgb.LGBMRegressor(n_jobs=-1, n_estimators=200, verbose=-1).fit(X, y); note = "cpu"
    elif which == "tabpfn":
        from tabpfn import TabPFNRegressor
        m = TabPFNRegressor(device="cuda").fit(X[:500], y[:500]); p = m.predict(X[500:]); note = f"rmse={np.sqrt(((p-y[500:])**2).mean()):.3f}"
    elif which == "tabicl":
        from tabicl import TabICLRegressor
        m = TabICLRegressor(device="cuda").fit(X[:500], y[:500]); p = m.predict(X[500:]); note = f"rmse={np.sqrt(((p-y[500:])**2).mean()):.3f}"
    elif which == "ag":
        import pandas as pd
        from autogluon.tabular import TabularPredictor
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(10)]); df["y"] = y
        pr = TabularPredictor(label="y", path="/tmp/ag_smoke", verbosity=1).fit(df, presets="extreme", time_limit=120)
        lb = pr.leaderboard(silent=True); note = f"models={len(lb)} best={lb.iloc[0]['model']}"
    elif which == "hf":
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
        from datasets import Dataset
        name = sys.argv[4] if len(sys.argv)>4 else "microsoft/deberta-v3-base"
        tok = AutoTokenizer.from_pretrained(name)
        model = AutoModelForSequenceClassification.from_pretrained(name, num_labels=2)
        ds = Dataset.from_dict({"text": ["good movie"] * 160 + ["bad film"] * 160, "label": [1] * 160 + [0] * 160}).map(lambda b: tok(b["text"], truncation=True, max_length=32), batched=True)
        args = TrainingArguments("/tmp/hf_smoke", max_steps=int(sys.argv[2]) if len(sys.argv)>2 else 20, learning_rate=2e-5, warmup_ratio=0.1, per_device_train_batch_size=16, bf16=(sys.argv[3]!="fp32" if len(sys.argv)>3 else True), report_to=[], save_strategy="no", logging_steps=10)
        tr = Trainer(model=model, args=args, train_dataset=ds, processing_class=tok); r = tr.train()
        note = f"dtype={model.dtype} loss={r.training_loss:.3f} vram={torch.cuda.max_memory_allocated()/1e9:.1f}GB"
    print(f"RESULT {which} PASS {time.time()-t:.0f}s {note}")
except Exception as e:
    traceback.print_exc(); print(f"RESULT {which} FAIL {time.time()-t:.0f}s {type(e).__name__}: {str(e)[:200]}")

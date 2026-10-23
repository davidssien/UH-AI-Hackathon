"""Optuna for the homes model: features built once per fold (3 folds), only model params searched.
python src/tune_hou.py --model lgbm|cat --feats ... --segment homes --target ppsf --timeout 900
Writes logs/params_<model>.json; refit on 5 folds with src/exp.py --params (keep/revert there).
"""
import argparse, json, os, sys, warnings
import numpy as np, pandas as pd, optuna

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import path
from eval import load_truth
from exp import SEGMENTS, fit_predict, target_offset
from featurize_new import Featurizer

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)


def space(trial, model):
    if model == "lgbm":
        return dict(num_leaves=trial.suggest_int("num_leaves", 15, 255, log=True),
                    learning_rate=trial.suggest_float("learning_rate", 0.015, 0.08, log=True),
                    min_child_samples=trial.suggest_int("min_child_samples", 5, 100, log=True),
                    colsample_bytree=trial.suggest_float("colsample_bytree", 0.2, 1.0),
                    subsample=trial.suggest_float("subsample", 0.5, 1.0),
                    reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 30, log=True),
                    reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10, log=True),
                    min_split_gain=trial.suggest_float("min_split_gain", 0, 0.05),
                    cat_smooth=trial.suggest_float("cat_smooth", 1, 50, log=True))
    return dict(depth=trial.suggest_int("depth", 4, 10), learning_rate=trial.suggest_float("learning_rate", 0.02, 0.12, log=True),
                l2_leaf_reg=trial.suggest_float("l2_leaf_reg", 0.5, 30, log=True),
                bagging_temperature=trial.suggest_float("bagging_temperature", 0, 2),
                random_strength=trial.suggest_float("random_strength", 0.1, 5, log=True),
                rsm=trial.suggest_float("rsm", 0.3, 1.0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="lgbm")
    ap.add_argument("--feats", required=True)
    ap.add_argument("--segment", default="homes")
    ap.add_argument("--target", default="ppsf")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    d, folds = load_truth()
    m = SEGMENTS[a.segment](d)
    d, folds = d[m], folds[m]
    cache = []
    for k in (0, 1, 2):
        tr, va = d[folds != k], d[folds == k]
        fz = Featurizer(a.feats).fit(tr)
        cache.append((fz.transform(tr, train=True), tr.y.values - target_offset(tr, a.target), tr.group.values,
                      fz.transform(va), va.y.values, target_offset(va, a.target)))
    print("features cached", flush=True)

    def objective(trial):
        p = space(trial, a.model)
        if a.model == "cat":
            p["thread_count"] = 12
        errs = []
        for Xtr, ytr, g, Xva, yva, ova in cache:
            _, (pr,), _ = fit_predict(a.model, Xtr, ytr, [Xva], p, 42, g)
            errs.append(np.sqrt(np.mean((pr + ova - yva) ** 2)))
        return float(np.mean(errs))

    st = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
    st.optimize(objective, timeout=a.timeout)
    print(f"trials={len(st.trials)} best={st.best_value:.5f} params={st.best_params}", flush=True)
    json.dump(st.best_params, open(path("logs", f"params_{a.model}.json"), "w"))

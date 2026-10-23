"""Optuna on a GBDT over a subset of folds (default 3). Writes logs/params_<id>.json.
python src/tune.py --id tune_lgbm --model lgbm --timeout 900 --folds 0,1,2 [--tt log1p] [--fe ...]
then: python src/train_lgbm.py --id lgbm_tuned --params logs/params_tune_lgbm.json"""
import json
import optuna
from common import base_args, cfg, parse_params, path, run_cv
from eval import HIGHER

SPACES = {
    "lgbm": lambda t: dict(
        learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
        num_leaves=t.suggest_int("num_leaves", 15, 255, log=True),
        min_child_samples=t.suggest_int("min_child_samples", 5, 200, log=True),
        colsample_bytree=t.suggest_float("colsample_bytree", 0.3, 1.0),
        subsample=t.suggest_float("subsample", 0.5, 1.0),
        reg_lambda=t.suggest_float("reg_lambda", 1e-3, 30, log=True),
        reg_alpha=t.suggest_float("reg_alpha", 1e-3, 10, log=True)),
    "xgb": lambda t: dict(
        learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
        max_depth=t.suggest_int("max_depth", 3, 12),
        min_child_weight=t.suggest_float("min_child_weight", 1, 100, log=True),
        colsample_bytree=t.suggest_float("colsample_bytree", 0.3, 1.0),
        subsample=t.suggest_float("subsample", 0.5, 1.0),
        reg_lambda=t.suggest_float("reg_lambda", 1e-3, 30, log=True),
        reg_alpha=t.suggest_float("reg_alpha", 1e-3, 10, log=True)),
    "cat": lambda t: dict(
        learning_rate=t.suggest_float("learning_rate", 0.02, 0.15, log=True),
        depth=t.suggest_int("depth", 4, 10),
        l2_leaf_reg=t.suggest_float("l2_leaf_reg", 1, 30, log=True),
        random_strength=t.suggest_float("random_strength", 0.1, 10, log=True)),
}

if __name__ == "__main__":
    ap = base_args()
    ap.add_argument("--model", required=True, choices=list(SPACES))
    ap.add_argument("--timeout", type=int, default=900)
    ap.set_defaults(folds="0,1,2")
    args = ap.parse_args()
    mod = __import__(f"train_{args.model}")
    fixed = parse_params(args.params)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize" if cfg()["METRIC"] in HIGHER else "minimize",
                                sampler=optuna.samplers.TPESampler(seed=42))

    def obj(t):
        p = {**fixed, **SPACES[args.model](t)}
        m, s = run_cv(args, mod.make_fit(p), args.model, save=False)
        print(f"trial {t.number}: {m:.5f} ± {s:.5f}", flush=True)
        return m

    tuned = {"learning_rate", "num_leaves", "min_child_samples", "colsample_bytree", "subsample", "reg_lambda",
             "max_depth", "min_child_weight", "depth"}
    study.enqueue_trial({k: v for k, v in mod.DEFAULT.items() if k in tuned})  # trial 0 = current defaults
    study.optimize(obj, timeout=args.timeout)
    best = {**fixed, **study.best_params}
    with open(path("logs", f"params_{args.id}.json"), "w") as f:
        json.dump(best, f, indent=1)
    print(f"BEST {study.best_value:.5f} after {len(study.trials)} trials -> logs/params_{args.id}.json {best}")

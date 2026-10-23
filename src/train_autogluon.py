"""AutoGluon (GPU). Bags on OUR folds via groups=fold column, so predict_oof() is comparable with other models.
python src/train_autogluon.py --id ag1 --presets extreme --time-limit 3600 [--tt log1p]   (run with TIMEOUT=65m ./run.sh)"""
import time
import numpy as np
from autogluon.tabular import TabularPredictor
import common, features
from common import TT, base_args, cfg, finish, load_data, load_folds, path
from eval import score_folds

AG_METRIC = {"rmse": "root_mean_squared_error", "mae": "mean_absolute_error", "r2": "r2",
             "rmsle": "root_mean_squared_error"}  # rmsle: pair with --tt log1p

if __name__ == "__main__":
    ap = base_args()
    ap.add_argument("--presets", default="extreme")
    ap.add_argument("--time-limit", type=int, default=3600)
    args = ap.parse_args()
    t0 = time.time()
    c = cfg()
    train, test = load_data()
    X, Xte, cats = features.build(train, test, c, args.fe)
    y = train[c["TARGET"]].values.astype(float)
    fwd, inv = TT[args.tt]
    folds = load_folds()
    df = X.copy()
    df["__y__"], df["__fold__"] = fwd(y), folds
    pr = TabularPredictor(label="__y__", problem_type="regression", eval_metric=AG_METRIC[c["METRIC"]],
                          path=path("ag_models", args.id), groups="__fold__", verbosity=2)
    pr.fit(df, presets=args.presets, time_limit=args.time_limit, dynamic_stacking=False,
           num_gpus=1, **common.parse_params(args.params))
    oof = inv(pr.predict_oof().values.astype(float))
    te = inv(pr.predict(Xte).values.astype(float))
    print(pr.leaderboard(silent=True)[["model", "score_val"]].head(8).to_string())
    mean, std, _ = score_folds(oof, y, folds, c["METRIC"])
    finish(args, f"ag_{args.presets}", oof, te, mean, std, t0, "tab")

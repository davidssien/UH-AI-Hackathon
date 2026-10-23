"""LightGBM (CPU). python src/train_lgbm.py --id lgbm1 [--tt log1p] [--fe base+count] [--params '{...}']"""
import lightgbm as lgb
from common import base_args, parse_params, run_cv

DEFAULT = dict(learning_rate=0.03, n_estimators=10000, num_leaves=63, min_child_samples=20, subsample=0.8,
               subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0, n_jobs=12, verbose=-1)  # n_jobs=-1 (24) is ~40x slower on this CPU+WSL


def make_fit(params):
    p = {**DEFAULT, **params}

    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        m = lgb.LGBMRegressor(**p, random_state=seed)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], callbacks=[lgb.early_stopping(200, verbose=False)])
        return m.predict(Xva), m.predict(Xte), {"best_iter": m.best_iteration_}
    return fit


if __name__ == "__main__":
    args = base_args().parse_args()
    run_cv(args, make_fit(parse_params(args.params)), "lgbm")

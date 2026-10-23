"""XGBoost (GPU). python src/train_xgb.py --id xgb1 [--tt log1p] [--params '{...}']"""
import xgboost as xgb
from common import base_args, parse_params, run_cv

DEFAULT = dict(device="cuda", tree_method="hist", learning_rate=0.03, max_depth=7, subsample=0.8, colsample_bytree=0.7,
               min_child_weight=5, n_estimators=10000, early_stopping_rounds=200, enable_categorical=True,
               max_cat_to_onehot=1, verbosity=0)


def make_fit(params):
    p = {**DEFAULT, **params}

    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        m = xgb.XGBRegressor(**p, random_state=seed)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        return m.predict(Xva), m.predict(Xte), {"best_iter": m.best_iteration}
    return fit


if __name__ == "__main__":
    args = base_args().parse_args()
    run_cv(args, make_fit(parse_params(args.params)), "xgb")

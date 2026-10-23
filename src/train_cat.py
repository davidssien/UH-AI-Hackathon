"""CatBoost (CPU by default: ~10s/fold vs ~230s on GPU at 16k rows, and GPU grabs all VRAM).
GPU for big data: --params '{"task_type":"GPU","gpu_ram_part":0.5}'. Native cat_features."""
from catboost import CatBoostRegressor, Pool
from common import base_args, parse_params, run_cv

DEFAULT = dict(learning_rate=0.05, depth=7, iterations=10000, od_type="Iter", od_wait=200, use_best_model=True,
               task_type="CPU", thread_count=12, verbose=0)


def _str_cats(X, cats):
    X = X.copy()
    for col in cats:
        X[col] = X[col].astype(str)
    return X


def make_fit(params):
    p = {**DEFAULT, **params}

    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        Xtr, Xva, Xte = (_str_cats(X, cats) for X in (Xtr, Xva, Xte))
        m = CatBoostRegressor(**p, random_seed=seed)
        m.fit(Pool(Xtr, ytr, cat_features=cats), eval_set=Pool(Xva, yva, cat_features=cats))
        return m.predict(Pool(Xva, cat_features=cats)), m.predict(Pool(Xte, cat_features=cats)), {"best_iter": m.get_best_iteration()}
    return fit


if __name__ == "__main__":
    args = base_args().parse_args()
    run_cv(args, make_fit(parse_params(args.params)), "cat")

"""TabPFN regressor (GPU). In-context model: no early stopping. Subsamples train to --max-train rows per fold."""
import numpy as np
from tabpfn import TabPFNRegressor
from common import base_args, ordinal, parse_params, run_cv


def make_fit(params, max_train):
    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        idx = np.random.default_rng(seed).permutation(len(Xtr))[:max_train]
        Xn_tr, Xn_va, Xn_te = (ordinal(X, cats).values for X in (Xtr, Xva, Xte))
        cat_idx = [i for i, c in enumerate(Xtr.columns) if c in cats]
        m = TabPFNRegressor(device="cuda", random_state=seed, categorical_features_indices=cat_idx or None,
                            ignore_pretraining_limits=True, **params)
        m.fit(Xn_tr[idx], ytr[idx])
        return m.predict(Xn_va), m.predict(Xn_te), {"n_train": len(idx)}
    return fit


if __name__ == "__main__":
    ap = base_args()
    ap.add_argument("--max-train", type=int, default=10000)
    args = ap.parse_args()
    run_cv(args, make_fit(parse_params(args.params), args.max_train), "tabpfn")

"""TabICL regressor (GPU). In-context model: no early stopping. Subsamples train to --max-train rows per fold."""
import numpy as np
from tabicl import TabICLRegressor
from common import base_args, ordinal, parse_params, run_cv


def make_fit(params, max_train):
    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        idx = np.random.default_rng(seed).permutation(len(Xtr))[:max_train]
        Xn_tr, Xn_va, Xn_te = (ordinal(X, cats) for X in (Xtr, Xva, Xte))
        m = TabICLRegressor(device="cuda", random_state=seed, **params)
        m.fit(Xn_tr.iloc[idx], ytr[idx])
        return m.predict(Xn_va), m.predict(Xn_te), {"n_train": len(idx)}
    return fit


if __name__ == "__main__":
    ap = base_args()
    ap.add_argument("--max-train", type=int, default=20000)
    args = ap.parse_args()
    run_cv(args, make_fit(parse_params(args.params), args.max_train), "tabicl")

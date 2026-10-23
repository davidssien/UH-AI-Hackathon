"""RealMLP / TabM via pytabkit (GPU). Early stopping on the validation fold (X_val/y_val).
python src/train_pytabkit.py --id realmlp1 --model realmlp|tabm [--tt log1p]"""
import numpy as np, pandas as pd
from common import base_args, parse_params, run_cv


def make_fit(model, params):
    from pytabkit import RealMLP_TD_Regressor, TabM_D_Regressor
    cls = {"realmlp": RealMLP_TD_Regressor, "tabm": TabM_D_Regressor}[model]

    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        # pytabkit rejects NaN in numeric cols: train-median fill + missing indicator
        Xtr, Xva, Xte = Xtr.copy(), Xva.copy(), Xte.copy()
        for col in [c for c in Xtr if c not in cats and pd.concat([Xtr[c], Xva[c], Xte[c]]).isna().any()]:
            med = Xtr[col].median()
            for X in (Xtr, Xva, Xte):
                X[f"{col}_isna"] = X[col].isna().astype(float)
                X[col] = X[col].fillna(med)
        m = cls(device="cuda", random_state=seed, verbosity=0, **params)
        m.fit(Xtr, ytr, X_val=Xva, y_val=yva, cat_col_names=cats or None)
        return m.predict(Xva), m.predict(Xte), {}
    return fit


if __name__ == "__main__":
    ap = base_args()
    ap.add_argument("--model", default="realmlp", choices=["realmlp", "tabm"])
    args = ap.parse_args()
    run_cv(args, make_fit(args.model, parse_params(args.params)), args.model)

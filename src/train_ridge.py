"""Ridge baseline: median impute + scale numerics, one-hot cats, RidgeCV alpha. No early stopping (closed form)."""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from common import base_args, parse_params, run_cv


def make_fit(params):
    alphas = params.get("alphas", np.logspace(-3, 3, 13))

    def fit(Xtr, ytr, Xva, yva, Xte, cats, seed):
        nums = [c for c in Xtr if c not in cats]
        pre = ColumnTransformer([
            ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), nums),
            ("cat", make_pipeline(SimpleImputer(strategy="constant", fill_value="NA"),
                                  OneHotEncoder(handle_unknown="ignore", min_frequency=5)), cats),
        ])
        to_obj = lambda X: X.astype({c: object for c in cats})
        m = make_pipeline(pre, RidgeCV(alphas=alphas)).fit(to_obj(Xtr), ytr)
        return m.predict(to_obj(Xva)), m.predict(to_obj(Xte)), {"alpha": float(m[-1].alpha_)}
    return fit


if __name__ == "__main__":
    args = base_args().parse_args()
    run_cv(args, make_fit(parse_params(args.params)), "ridge")

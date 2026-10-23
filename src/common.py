"""Shared helpers: config, data, folds, target transforms, CV runner, results logging."""
import argparse, json, os, sys, time
import numpy as np, pandas as pd, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def path(*p):
    return os.path.join(ROOT, *p)


def cfg():
    with open(path("config.yaml")) as f:
        return yaml.safe_load(f)


def nlp_cfg():
    return cfg()["NLP"]


def load_data(track="tab"):
    c = cfg() if track == "tab" else nlp_cfg()
    d = path(c["DATA_DIR"])
    return pd.read_csv(f"{d}/{c['TRAIN']}"), pd.read_csv(f"{d}/{c['TEST']}")


def folds_file(track="tab"):
    return path("folds.csv" if track == "tab" else "nlp_folds.csv")


def load_folds(track="tab"):
    return pd.read_csv(folds_file(track))["fold"].values


def label_map(train):
    """NLP cls: sorted unique labels -> 0..C-1."""
    return {v: i for i, v in enumerate(sorted(train[nlp_cfg()["LABEL_COL"]].unique()))}


def load_y(track="tab"):
    if track == "tab":
        return load_data("tab")[0][cfg()["TARGET"]].values.astype(float)
    c = nlp_cfg()
    tr = pd.read_csv(path(c["DATA_DIR"], c["TRAIN"]))
    if c["TASK"] == "cls":
        return tr[c["LABEL_COL"]].map(label_map(tr)).values
    return tr[c["LABEL_COL"]].values.astype(float)


TT = {
    "none": (lambda y: y, lambda y: y),
    "log1p": (np.log1p, np.expm1),
    "sqrt": (np.sqrt, lambda y: np.square(np.clip(y, 0, None))),
}


def parse_params(s):
    if not s:
        return {}
    if os.path.exists(s):
        with open(s) as f:
            return json.load(f)
    return json.loads(s)


def base_args(desc=""):
    ap = argparse.ArgumentParser(desc)
    ap.add_argument("--id", required=True)
    ap.add_argument("--tt", default="none", choices=list(TT), help="target transform")
    ap.add_argument("--fe", default="base", help="feature sets joined by +, see features.py")
    ap.add_argument("--te", action="store_true", help="add in-fold target encoding of cat cols")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--folds", default="all", help="'all' or comma list, e.g. 0,1,2")
    ap.add_argument("--params", default="", help="JSON string or json file overriding model params")
    ap.add_argument("--change", default="", help="short description for results.tsv")
    return ap


def fold_list(args, folds):
    return sorted(int(k) for k in set(folds) if k >= 0) if args.folds == "all" else [int(k) for k in args.folds.split(",")]


def run_cv(args, fit, model, save=True):
    """fit(Xtr, ytr, Xva, yva, Xte, cats, seed) -> (va_pred, te_pred, info_dict). Preds in transformed space."""
    import features
    from eval import score_folds
    t0 = time.time()
    c = cfg()
    seed = c["SEED"] if args.seed is None else args.seed
    train, test = load_data()
    X, Xte, cats = features.build(train, test, c, args.fe)
    y = train[c["TARGET"]].values.astype(float)
    fwd, inv = TT[args.tt]
    yt = fwd(y)
    folds = load_folds()
    oof = np.full(len(y), np.nan)
    te = np.zeros(len(Xte))
    ks = fold_list(args, folds)
    for k in ks:
        tr, va = folds != k, folds == k
        Xtr, Xva, Xt = X[tr].reset_index(drop=True), X[va].reset_index(drop=True), Xte
        if args.te:
            Xtr, Xva, Xt = features.add_te(Xtr, yt[tr], Xva, Xt, cats, seed)
        pv, pt, info = fit(Xtr, yt[tr], Xva, yt[va], Xt, cats, seed + k)
        oof[va] = inv(np.asarray(pv, dtype=float).ravel())
        te += inv(np.asarray(pt, dtype=float).ravel()) / len(ks)
        print(f"fold {k} done {time.time() - t0:.0f}s {info}", flush=True)
    mean, std, _ = score_folds(oof, y, folds, c["METRIC"])
    if save:
        finish(args, model, oof, te, mean, std, t0, "tab")
    return mean, std


def finish(args, model, oof, te, mean, std, t0, track):
    np.save(path("oof", f"oof_{args.id}.npy"), oof)
    np.save(path("test_preds", f"test_{args.id}.npy"), te)
    meta = {k: v for k, v in vars(args).items()} | {"model": model, "track": track, "cv_mean": mean, "cv_std": std}
    with open(path("oof", f"meta_{args.id}.json"), "w") as f:
        json.dump(meta, f, indent=1, default=str)
    append_result(args.id, track, model, mean, std, (time.time() - t0) / 60, args.change)
    print(f"RESULT {args.id} {model} cv={mean:.5f} std={std:.5f} min={(time.time() - t0) / 60:.1f}", flush=True)


COLS = ["id", "track", "model", "cv_mean", "cv_std", "minutes", "change", "kept"]


def append_result(id_, track, model, mean, std, minutes, change, kept=""):
    f = path("results.tsv")
    new = not os.path.exists(f)
    with open(f, "a") as fh:
        if new:
            fh.write("\t".join(COLS) + "\n")
        fh.write(f"{id_}\t{track}\t{model}\t{mean:.6f}\t{std:.6f}\t{minutes:.1f}\t{change}\t{kept}\n")


def ordinal(X, cats):
    """Numeric matrix for models without native cat support (cat -> codes, NaN kept)."""
    X = X.copy()
    for col in cats:
        codes = X[col].cat.codes.astype(float) if hasattr(X[col], "cat") else pd.Series(pd.factorize(X[col])[0], dtype=float)
        X[col] = codes.where(codes >= 0, np.nan)
    return X.astype(float)

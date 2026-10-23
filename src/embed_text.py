"""Description embeddings (GPU) -> data/emb_text.npz (zpid, E). PCA to 32 dims happens in-fold in featurize_new.
python src/embed_text.py [model]   default BAAI/bge-small-en-v1.5
"""
import os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import cfg, path

if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer
    name = sys.argv[1] if len(sys.argv) > 1 else "BAAI/bge-small-en-v1.5"
    kind = sys.argv[2] if len(sys.argv) > 2 else "text"  # e.g. textL for bge-large (separate file, separate feature set)
    d = pd.read_parquet(path(cfg()["HOU"]["CLEAN"]), columns=["zpid", "description"])
    d = d[d.description.str.len() > 0].drop_duplicates("zpid")
    m = SentenceTransformer(name, device="cuda")
    E = m.encode(d.description.tolist(), batch_size=64, normalize_embeddings=True, show_progress_bar=False,
                 convert_to_numpy=True)
    np.savez_compressed(path("data", f"emb_{kind}.npz"), zpid=d.zpid.values, E=E.astype(np.float16))
    print(f"wrote data/emb_{kind}.npz {E.shape} model={name}")

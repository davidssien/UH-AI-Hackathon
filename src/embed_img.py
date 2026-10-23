"""CLIP image embeddings of the first 3 listing photos -> data/emb_img.npz (zpid, E = mean of photo embeddings).
Photos cached in data/img/<zpid>_<i>.jpg (download is resumable). PCA to 32 dims happens in-fold.
python src/embed_img.py download | embed
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import cfg, path

IMG = path("data", "img")


def jobs():
    d = pd.read_parquet(path(cfg()["HOU"]["CLEAN"]), columns=["zpid", "photos"]).drop_duplicates("zpid")
    return [(z, i, u) for z, p in zip(d.zpid, d.photos) for i, u in enumerate(json.loads(p or "[]")[:3])]


def fetch(job):
    import requests
    z, i, u = job
    f = os.path.join(IMG, f"{z}_{i}.jpg")
    if os.path.exists(f):
        return 1
    for _ in range(2):
        try:
            r = requests.get(u, timeout=15, headers={"User-Agent": "Mozilla/5.0 (research; UH hackathon)"})
            if r.status_code == 200 and r.content:
                open(f + ".tmp", "wb").write(r.content)
                os.replace(f + ".tmp", f)
                return 1
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    os.makedirs(IMG, exist_ok=True)
    if sys.argv[1] == "download":
        J = jobs()
        ok = 0
        with ThreadPoolExecutor(48) as ex:
            for n, r in enumerate(ex.map(fetch, J), 1):
                ok += r
                if n % 5000 == 0:
                    print(f"{n}/{len(J)} ok={ok}", flush=True)
        print(f"DOWNLOAD DONE {ok}/{len(J)}")
    else:
        import torch, open_clip
        from PIL import Image
        model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k", device="cuda")
        model.eval()
        files = sorted(os.listdir(IMG))
        files = [f for f in files if f.endswith(".jpg")]
        zp = np.array([int(f.split("_")[0]) for f in files])
        E = np.zeros((len(files), 512), np.float32)
        for s in range(0, len(files), 256):
            ims = []
            for f in files[s:s + 256]:
                try:
                    ims.append(pre(Image.open(os.path.join(IMG, f)).convert("RGB")))
                except Exception:
                    ims.append(torch.zeros(3, 224, 224))
            with torch.no_grad(), torch.autocast("cuda"):
                e = model.encode_image(torch.stack(ims).cuda()).float()
            E[s:s + len(ims)] = torch.nn.functional.normalize(e, dim=-1).cpu().numpy()
        df = pd.DataFrame(E)
        df["zpid"] = zp
        g = df.groupby("zpid").mean()
        np.savez_compressed(path("data", "emb_img.npz"), zpid=g.index.values, E=g.values.astype(np.float16))
        print(f"wrote data/emb_img.npz {g.shape} from {len(files)} photos")

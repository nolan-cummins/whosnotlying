"""
Full-scale DYK gate: train logistic regression and a 1-hidden-layer MLP (PyTorch, GPU if available) on the precomputed embeddings
(parts/pN/emb.npy from embed_all.py) with every DYK-featured candidate as a positive and 3 length/popularity-matched non-DYK
candidates per positive, then score all candidates. Split 80/10/10: train / val (early stopping) / test (reported AUC).
Hand labels and the bake gate sample are excluded from training. Per-epoch log on stdout; curves redrawn to train/curves.png.
Writes parts/pN/dyk_score_{lr,mlp}.npy (float32, emb_ids.json order), dyk_rank_{lr,mlp}.json (all ids, best first) and a topic-lift table.

    uv run --no-project --with scikit-learn --with numpy --with pyarrow --with matplotlib --with torch python -I score_dyk.py /mnt/hdd2/wikipedia [TOP_N]
"""
import json
import os
import random
import sys

import numpy as np
import pyarrow.parquet as pq
import torch
from sklearn.metrics import roc_auc_score

NEG_PER_POS = 3
EPOCHS, PATIENCE, BATCH = 60, 5, 2048
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def bin_of(m):
    return min(16, int(np.log2(max(m["chars"], 1)))), int(m["pct"] // 20)


def make(kind, d):
    if kind == "lr":
        return torch.nn.Linear(d, 1)
    return torch.nn.Sequential(torch.nn.Linear(d, 256), torch.nn.ReLU(), torch.nn.Dropout(.2), torch.nn.Linear(256, 1))


def predict(net, X):
    net.eval()
    with torch.no_grad():
        return torch.cat([torch.sigmoid(net(torch.as_tensor(X[k:k + 200_000]).to(DEV).float())).squeeze(1).cpu()
                          for k in range(0, len(X), 200_000)]).numpy()


def plot(hist, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4))
    for kind, h in hist.items():
        a.plot([x["train"] for x in h], label=f"{kind} train")
        a.plot([x["val"] for x in h], "--", label=f"{kind} val")
        b.plot([x["auc"] for x in h], label=kind)
    a.set(xlabel="epoch", ylabel="log loss", title="loss"), b.set(xlabel="epoch", ylabel="AUC", title="val AUC (is it DYK?)")
    a.legend(), b.legend(), fig.tight_layout()
    fig.savefig(os.path.join(out, "curves.tmp.png"), dpi=100)
    plt.close(fig)
    os.replace(os.path.join(out, "curves.tmp.png"), os.path.join(out, "curves.png"))


def train(kind, X, y, tr, va, hist, out):
    torch.manual_seed(1)
    net = make(kind, X.shape[1]).to(DEV)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    Xt, yt = torch.as_tensor(X[tr]).to(DEV), torch.as_tensor(y[tr], dtype=torch.float32).to(DEV)
    Xv, yv = torch.as_tensor(X[va]).to(DEV), torch.as_tensor(y[va], dtype=torch.float32).to(DEV)
    best, best_state, bad = -1, None, 0
    hist[kind] = []
    for ep in range(EPOCHS):
        net.train()
        tot = 0.0
        for idx in torch.randperm(len(Xt), device=DEV).split(BATCH):
            loss = loss_fn(net(Xt[idx].float()).squeeze(1), yt[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        net.eval()
        with torch.no_grad():
            lv = net(Xv.float()).squeeze(1)
            vl = loss_fn(lv, yv).item()
        auc = roc_auc_score(y[va], lv.cpu().numpy())
        hist[kind].append({"train": tot / len(Xt), "val": vl, "auc": auc})
        print(f"[{kind}] epoch {ep + 1:>2}  train loss {tot / len(Xt):.4f}  val loss {vl:.4f}  val AUC {auc:.4f}", flush=True)
        plot(hist, out)
        if auc > best:
            best, best_state, bad = auc, {k: v.clone() for k, v in net.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= PATIENCE:
                break
    net.load_state_dict(best_state)
    return net


def top_topic(m):
    t = m.get("topics") or {}
    return ".".join(max(t, key=t.get).rstrip("*").split(".")[:2]) if t else "none"


def main(root, top_n=100_000):
    parts_dir = os.path.join(root, "parts")
    parts = sorted(os.listdir(parts_dir), key=lambda p: int(p[1:]))
    t = pq.read_table(os.path.join(root, "dyk", "dyk-en.parquet"), columns=["linked_pages"]).column(0).to_pylist()
    dyk = {lp["page_id"] for row in t for lp in (row or []) if lp["prominent"]}
    labels = os.path.join(root, "p0", "exp", "labels")
    sample = json.load(open(os.path.join(labels, "sample.json")))
    held = set(sample) | set(json.load(open(os.path.join(root, "p0", "exp", "bake", "sample.json")))["gate"])

    embs, ids, bins, topics = [], [], [], []
    for p in parts:
        pd = os.path.join(parts_dir, p)
        pid = json.load(open(os.path.join(pd, "emb_ids.json")))
        meta = {}
        for line in open(os.path.join(pd, "meta.jsonl")):
            m = json.loads(line)
            meta[m["id"]] = m
        embs.append(np.load(os.path.join(pd, "emb.npy")))
        ids += pid
        bins += [bin_of(meta[i]) for i in pid]
        topics += [top_topic(meta[i]) for i in pid]
    E = np.concatenate(embs)
    ids = np.array(ids)
    del embs
    print(f"{len(ids):,} candidates, {E.shape[1]} dims; {len(dyk):,} DYK page ids", flush=True)

    rng = random.Random(1)
    pos, by_bin = [], {}
    for k, (i, b) in enumerate(zip(ids, bins)):
        if i in held:
            continue
        if i in dyk:
            pos.append(k)
        else:
            by_bin.setdefault(b, []).append(k)
    neg = []
    for k in pos:
        b = by_bin.get(bins[k], [])
        neg += rng.sample(b, min(NEG_PER_POS, len(b)))
    rows = np.array(pos + neg)
    y = np.array([1] * len(pos) + [0] * len(neg))
    print(f"train: {len(pos):,} DYK positives, {len(neg):,} matched negatives", flush=True)

    X = E[rows]
    perm = np.random.default_rng(1).permutation(len(rows))
    tr, va, te = np.split(perm, [int(len(rows) * .8), int(len(rows) * .9)])
    out = os.path.join(root, "train")
    os.makedirs(out, exist_ok=True)
    hist = {}
    print(f"device: {DEV}", flush=True)
    topics = np.array(topics)
    sizes = [len(json.load(open(os.path.join(parts_dir, p, "emb_ids.json")))) for p in parts]
    for kind in ("lr", "mlp"):
        net = train(kind, X, y, tr, va, hist, out)
        print(f"[{kind}] DYK test AUC (untouched 10%): {roc_auc_score(y[te], predict(net, X[te])):.4f}", flush=True)
        s = predict(net, E)
        k = 0
        for p, n in zip(parts, sizes):
            np.save(os.path.join(parts_dir, p, f"dyk_score_{kind}.npy"), s[k:k + n])
            k += n
        top = np.argsort(-s)[:top_n]
        print(f"[{kind}] top {top_n:,} cutoff score {s[top[-1]]:.3f}; DYK share in top: {np.isin(ids[top], list(dyk)).mean():.1%}")
        json.dump([int(i) for i in ids[np.argsort(-s)]], open(os.path.join(root, f"dyk_rank_{kind}.json"), "w"))
        allt, topt = {}, {}
        for t in topics:
            allt[t] = allt.get(t, 0) + 1
        for t in topics[top]:
            topt[t] = topt.get(t, 0) + 1
        print(f"[{kind}] topic: share of all -> share of top {top_n:,} (lift)")
        for t in sorted(allt, key=lambda t: -topt.get(t, 0) / top_n / (allt[t] / len(ids))):
            a, b = allt[t] / len(ids), topt.get(t, 0) / top_n
            if a > .003 or b > .003:
                print(f"    {t:<28} {a:6.1%} -> {b:6.1%}  x{b / a:.2f}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 100_000)

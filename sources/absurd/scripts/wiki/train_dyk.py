"""
Gate classifier from Wikipedia "Did you know" membership: DYK-featured articles are positives, non-DYK articles matched on
length and popularity band are negatives. Features: qwen3-embedding (local Ollama) of title + first 2,000 chars.
Evaluated against hand labels (labels/claude.json over labels/sample.json), which are excluded from training.

    uv run --no-project --with scikit-learn --with numpy python -I train_dyk.py D DYK_IDS.json
"""
import json
import os
import random
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import load
from trim import strip_refs
from ollama_embed import embed

NEG_PER_POS = 3


def text_of(c):
    return f"{c['title']}\n{strip_refs(c['text'])[:2000]}"


def embed_all(texts, cache):
    vecs = json.load(open(cache)) if os.path.exists(cache) else {}
    todo = [t for t in dict.fromkeys(texts) if t not in vecs]
    for k in range(0, len(todo), 32):
        for t, v in zip(todo[k:k + 32], embed(todo[k:k + 32], timeout=300)):
            vecs[t] = v
        if k % 640 == 0:
            print(f"  embedded {k + 32}/{len(todo)}", flush=True)
            json.dump(vecs, open(cache, "w"))
    json.dump(vecs, open(cache, "w"))
    return np.array([vecs[t] for t in texts])


def main(d, dyk_path):
    meta, text = load(d)
    dyk = set(json.load(open(dyk_path)))
    sample = json.load(open(os.path.join(d, "exp", "labels", "sample.json")))
    gold = {sample[int(k)]: v for k, v in json.load(open(os.path.join(d, "exp", "labels", "claude.json"))).items()}
    held = set(sample) | set(json.load(open(os.path.join(d, "exp", "bake", "sample.json")))["gate"])
    rng = random.Random(1)
    pos = [i for i in dyk if i in meta and i not in held]
    pool = [m for m in meta.values() if m["id"] not in dyk and m["id"] not in held and m["chars"] > 600]
    by_bin = {}
    for m in pool:  # bins of (length decile-ish, popularity band) so negatives look like positives on both
        by_bin.setdefault((min(9, int(np.log2(max(m["chars"], 1)))), int(m["pct"] // 20)), []).append(m["id"])
    neg = []
    for i in pos:
        b = by_bin.get((min(9, int(np.log2(max(meta[i]["chars"], 1)))), int(meta[i]["pct"] // 20)), [])
        neg += rng.sample(b, min(NEG_PER_POS, len(b)))
    ids = pos + neg
    y = np.array([1] * len(pos) + [0] * len(neg))
    print(f"train: {len(pos)} DYK positives, {len(neg)} matched negatives", flush=True)
    cache = os.path.join(d, "exp", "labels", "emb_cache.json")
    X = embed_all([text_of(text[i]) for i in ids], cache)
    G = embed_all([text_of(text[i]) for i in sample], cache)
    perm = rng.sample(range(len(ids)), len(ids))
    cut = int(len(ids) * .8)
    tr, va = perm[:cut], perm[cut:]
    clf = LogisticRegression(C=1.0, max_iter=2000).fit(X[tr], y[tr])
    print(f"DYK held-out AUC (is it a DYK article?): {roc_auc_score(y[va], clf.predict_proba(X[va])[:, 1]):.3f}")
    clf = LogisticRegression(C=1.0, max_iter=2000).fit(X, y)
    s = clf.predict_proba(G)[:, 1]
    lab = np.array([gold[i] for i in sample])
    out = {"auc_ge2": roc_auc_score(lab >= 2, s), "auc_ge1": roc_auc_score(lab >= 1, s), "auc_3": roc_auc_score(lab >= 3, s)}
    print("vs my 200 labels: " + ", ".join(f"{k} {v:.3f}" for k, v in out.items()))
    order = np.argsort(-s)
    for k in (20, 40, 80):
        print(f"  top {k}: {(lab[order[:k]] >= 2).sum()}/{k} rated >=2 (base {(lab >= 2).sum()}/200)")
    json.dump({str(i): float(v) for i, v in zip(sample, s)}, open(os.path.join(d, "exp", "labels", "dyk_scores.json"), "w"))
    np.save(os.path.join(d, "exp", "labels", "dyk_clf.npy"), np.concatenate([clf.coef_[0], clf.intercept_]))


if __name__ == "__main__":
    main(*sys.argv[1:3])

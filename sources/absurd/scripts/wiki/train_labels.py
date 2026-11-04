"""
Gate trained on real labels: logistic regression on the article embeddings (+ the DYK regressor's score as one extra feature)
predicting "has at least one surprising fact" (LLM score >= 2 from label_llm.py). 5-fold cross-validated, so every labelled
article is scored by a model that never saw it. Reports precision / recall per threshold, the estimated number of interesting
articles in all 4.7M, then scores every candidate -> parts/pN/gate_score.npy and gate_rank.json.

    uv run --no-project --with scikit-learn --with numpy python -I train_labels.py sonnet
"""
import json
import os
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from progress import Job

ROOT = "/mnt/hdd2/wikipedia"


def main(model):
    job = Job("06_gate", "6. Train the gate on real labels and score all 4.7M", total=4, unit="stages",
              note=f"Logistic regression on embeddings + DYK score; target = {model} score >= 2; 5-fold cross-validation")
    lab = {int(x["key"]): x["score"] for x in map(json.loads, open(f"{ROOT}/labels/sample_{model}.jsonl"))}
    parts = sorted(os.listdir(f"{ROOT}/parts"), key=lambda p: int(p[1:]))
    rows, where = [], {}
    for p in parts:
        for k, i in enumerate(json.load(open(f"{ROOT}/parts/{p}/emb_ids.json"))):
            if i in lab:
                where[i] = (p, k)
    ids = sorted(where)
    for i in ids:
        p, k = where[i]
        e = np.load(f"{ROOT}/parts/{p}/emb.npy", mmap_mode="r")[k]
        d = np.load(f"{ROOT}/parts/{p}/dyk_score_lr.npy", mmap_mode="r")[k]
        rows.append(np.append(e.astype(np.float32), d))
    X, y = np.array(rows), np.array([lab[i] >= 2 for i in ids], dtype=int)
    job.log(f"{len(ids):,} labelled articles, {y.sum():,} interesting ({y.mean():.1%} of a random sample)")
    job.metric("labelled", len(ids))
    job.metric("interesting in random sample", f"{y.mean():.1%}")
    job.step()

    best = None
    for C in (0.1, 0.3, 1, 3, 10):  # pick regularisation by cross-validated AUC
        oof = np.zeros(len(y))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=1).split(X, y):
            oof[te] = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        auc = roc_auc_score(y, oof)
        job.point("CV AUC by C (log10)", round(float(np.log10(C)), 2), round(auc, 4))
        job.log(f"C={C}: cross-validated AUC {auc:.3f}")
        if best is None or auc > best[0]:
            best = (auc, C, oof)
    auc, C, oof = best
    job.metric("cross-validated AUC", round(auc, 3))
    dyk_only = roc_auc_score(y, X[:, -1])
    job.metric("AUC of old DYK regressor on these labels", round(dyk_only, 3))
    job.step()

    table, cut75 = [], None
    for t in np.round(np.arange(0.05, 0.96, 0.05), 2):
        pred = oof >= t
        tp = int((pred & (y == 1)).sum())
        prec, rec = tp / max(1, pred.sum()), tp / max(1, y.sum())
        acc = float((pred == y).mean())
        table.append((t, prec, rec, acc, pred.mean()))
        job.point("precision % vs recall %", round(100 * rec, 1), round(100 * prec, 1))
        if cut75 is None and prec >= .75 and pred.sum() >= 10:
            cut75 = t
    for t, prec, rec, acc, share in table:
        job.log(f"threshold {t:.2f}: precision {prec:.0%}  recall {rec:.0%}  accuracy {acc:.0%}  passes {share:.1%}")
    job.step()

    clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(X, y)
    w, b = clf.coef_[0].astype(np.float32), np.float32(clf.intercept_[0])
    all_ids, all_s = [], []
    for p in parts:
        e = np.load(f"{ROOT}/parts/{p}/emb.npy")
        d = np.load(f"{ROOT}/parts/{p}/dyk_score_lr.npy")
        s = 1 / (1 + np.exp(-(e.astype(np.float32) @ w[:-1] + d * w[-1] + b)))
        np.save(f"{ROOT}/parts/{p}/gate_score.npy", s.astype(np.float32))
        all_ids += json.load(open(f"{ROOT}/parts/{p}/emb_ids.json"))
        all_s.append(s)
    s = np.concatenate(all_s)
    order = np.argsort(-s)
    json.dump([int(all_ids[k]) for k in order], open(f"{ROOT}/gate_rank.json", "w"))
    n = len(s)
    job.metric("estimated interesting articles in all 4.7M", f"{y.mean() * n:,.0f}")
    for t, prec, rec, acc, share in table:
        if t in (0.3, 0.5, 0.7) or t == cut75:
            k = int((s >= t).sum())
            job.metric(f"threshold {t:.2f}", f"keeps {k:,} articles; precision {prec:.0%}, recall {rec:.0%}")
    job.metric("lowest threshold with precision >= 75%", "none" if cut75 is None else f"{cut75:.2f}")
    job.step()
    job.finish()


if __name__ == "__main__":
    main(sys.argv[1])

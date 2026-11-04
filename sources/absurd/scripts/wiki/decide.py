"""
Gate test with Base Labs decision models (joey/elephant/mammoth) via OpenRouter's /api/alpha/decisions.

    python3 -I decide.py D MODEL...        # 40 gate articles (bake/sample.json) vs bake/gold.json -> bake/decide__<model>.jsonl
Prints per-model AUC and accuracy of P(minable), each boringness question's AUC, and cost.
"""
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake import GATE_CHARS, KEY
from bench import load
from llm import Q

URL = os.environ.get("DECIDE_URL", "https://openrouter.ai/api/alpha/decisions")
QUESTIONS = {
    "minable": {"type": "noul", "instructions":
                "This is a Wikipedia article being screened for a party trivia game. Does it contain at least one specific, "
                "non-obvious fact that would surprise or delight a general audience? Routine biographies, places described "
                "only by geography and statistics, sports results, plot summaries, lists and bare taxonomy do not count."},
    "richness": {"type": "score", "instructions": "How much usable trivia material does this article contain?",
                 "criteria": ["Nothing usable", "Thin: dry facts only", "At least one interesting fact",
                              "Several surprising or memorable facts"]},
    **{k: {"type": "noul", "instructions": v} for k, v in Q.items()},
}


def decide(model, state):
    body = json.dumps({"model": model, "state": state, "questions": QUESTIONS}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(3):
        try:
            return {**json.load(urllib.request.urlopen(req, timeout=120)), "secs": time.time() - t0}
        except urllib.error.HTTPError as e:
            err = f"{e.code} {e.read()[:200]!r}"
            if e.code != 429:
                break
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            err = f"net {e}"
    return {"error": err, "secs": time.time() - t0}


def auc(pos, neg):
    """P(score of a random positive > a random negative); ties count half."""
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / max(1, len(pos) * len(neg))


def main(d, models):
    _, text = load(d)
    B = os.path.join(d, "exp", "bake")
    ids = json.load(open(os.path.join(B, "sample.json")))["gate"]
    gold = {int(k): v for k, v in json.load(open(os.path.join(B, "gold.json")))["gate"].items()}
    for model in models:
        state = lambda i: f"TITLE: {text[i]['title']}\n\n{text[i]['text'][:GATE_CHARS]}"
        with cf.ThreadPoolExecutor(8) as ex:
            res = dict(zip(ids, ex.map(lambda i: decide(model, state(i)), ids)))
        with open(os.path.join(B, f"decide__{model.replace('/', '_')}.jsonl"), "w", encoding="utf-8") as f:
            for i, r in res.items():
                f.write(json.dumps({**r, "gen_id": r.get("id"), "id": i}, ensure_ascii=False) + "\n")
        ok = {i: r["answers"] for i, r in res.items() if "answers" in r}
        pos = [i for i in ok if gold[i]["minable"]]
        neg = [i for i in ok if not gold[i]["minable"]]
        p = {i: ok[i]["minable"]["noul"] for i in ok}
        rich = {i: sum(int(k) * v for k, v in ok[i]["richness"]["probabilities"].items()) for i in ok}
        best = max((sum((p[i] >= t) == gold[i]["minable"] for i in ok), t) for t in sorted(set(p.values())))
        cost = sum((r.get("usage") or {}).get("cost") or 0 for r in res.values())
        toks = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in res.values()) / max(1, len(res))
        print(f"\n== {model}: {len(ok)}/{len(ids)} ok, ${cost:.5f} total, {toks:.0f} input tokens/article, "
              f"p50 {sorted(r['secs'] for r in res.values())[len(res) // 2]:.1f}s")
        print(f"   minable: AUC {auc([p[i] for i in pos], [p[i] for i in neg]):.2f}, acc@0.5 "
              f"{sum((p[i] >= .5) == gold[i]['minable'] for i in ok)}/{len(ok)}, best acc {best[0]}/{len(ok)} at p>={best[1]:.2f}, "
              f"said yes@0.5 {sum(p[i] >= .5 for i in ok)}")
        print(f"   richness (expected level 0-3): AUC {auc([rich[i] for i in pos], [rich[i] for i in neg]):.2f}, "
              f"MAE vs my 0-3 {sum(abs(rich[i] - gold[i]['richness']) for i in ok) / max(1, len(ok)):.2f}")
        print("   per-question AUC (>0.5 = yes means minable, <0.5 = yes means boring): " + ", ".join(
            f"{q} {auc([ok[i][q]['noul'] for i in pos], [ok[i][q]['noul'] for i in neg]):.2f}" for q in Q))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

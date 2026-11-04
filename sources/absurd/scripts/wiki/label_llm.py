"""
Label articles 0-3 for "has at least one genuinely surprising fact" with headless Claude Code (claude -p), on the same
text the embedding saw (title + first 2,000 chars). Batches of 20, WORKERS parallel calls, resumable, progress on dash.py.

    python3 -I label_llm.py calib haiku|sonnet       # the 180 blind-read articles, compared to Claude's own scores
    python3 -I label_llm.py sample 4000              # draw N random candidates -> ROOT/labels/sample.jsonl
    python3 -I label_llm.py label haiku|sonnet       # label the sample -> ROOT/labels/sample_<model>.jsonl
"""
import concurrent.futures as cf
import json
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from progress import Job
from trim import strip_refs

ROOT = "/mnt/hdd2/wikipedia"
OUT = os.path.join(ROOT, "labels")
BATCH, WORKERS = 20, 4
RUBRIC = """You rate Wikipedia article excerpts for a trivia game that needs surprising true facts.
For each numbered article, score whether the excerpt contains at least one fact that would make a curious adult say
"wait, really?" - surprising, counterintuitive or delightfully odd, and stated in the excerpt itself.
0 = nothing surprising (routine biography, place, building, species description, results, lists)
1 = mildly interesting, but nothing you would retell
2 = at least one genuinely surprising fact you would retell
3 = an excellent "no way" fact
Judge only the text given. Reply with JSON only, no prose: [{"n": <number>, "score": <0-3>}, ...] covering every article."""


def call(model, items):
    body = "\n\n".join(f"### {n}\n{t}" for n, t in items)
    for attempt in range(3):
        r = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                            "--system-prompt", RUBRIC, "--output-format", "json"],
                           input=body, capture_output=True, text=True, timeout=600, cwd=OUT)
        try:
            res = json.loads(r.stdout)
            m = re.search(r"\[.*\]", res["result"], re.S)
            got = {int(x["n"]): int(x["score"]) for x in json.loads(m.group(0))}
            if all(n in got for n, _ in items):
                return got, res.get("total_cost_usd", 0)
        except (ValueError, KeyError, AttributeError, TypeError):
            pass
    raise RuntimeError(f"batch starting {items[0][0]} failed 3 times: {r.stderr[-300:] or r.stdout[-300:]}")


def run(model, items, dest, job, check=None):
    """items: [(key, text)]; appends {"key", "score"} lines to dest; check: {key: reference score} for live agreement."""
    done = {}
    if os.path.exists(dest):
        for line in open(dest):
            x = json.loads(line)
            done[x["key"]] = x["score"]
    todo = [(k, t) for k, t in items if k not in done]
    job.set(done=len(done), total=len(items))
    cost = 0.0

    def stats():
        v = list(done.values())
        job.metric("labelled", len(v))
        job.metric("share scored >=2", f"{sum(s >= 2 for s in v) / max(1, len(v)):.1%}")
        job.metric("est. cost (USD, if billed)", round(cost, 3))
        if check:
            both = [(done[k], check[k]) for k in done if k in check]
            agree = sum((a >= 2) == (b >= 2) for a, b in both) / max(1, len(both))
            tp = sum(a >= 2 and b >= 2 for a, b in both)
            job.metric("agreement with Claude's blind read (>=2 vs <2)", f"{agree:.1%}")
            job.metric("precision vs Claude", f"{tp / max(1, sum(a >= 2 for a, _ in both)):.1%}")
            job.metric("recall vs Claude", f"{tp / max(1, sum(b >= 2 for _, b in both)):.1%}")
            job.point("agreement %", len(both), round(100 * agree, 1))

    batches = [todo[k:k + BATCH] for k in range(0, len(todo), BATCH)]
    with open(dest, "a") as f, cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(call, model, [(i, t) for i, (_, t) in enumerate(b)]): b for b in batches}
        for fut in cf.as_completed(futs):
            b = futs[fut]
            try:
                got, c = fut.result()
            except Exception as e:
                job.log(f"error: {e}")
                continue
            cost += c
            for i, (k, _) in enumerate(b):
                done[k] = got[i]
                f.write(json.dumps({"key": k, "score": got[i]}) + "\n")
            f.flush()
            job.set(done=len(done))
            stats()
    stats()
    job.log(f"finished: {len(done)}/{len(items)} labelled")
    job.finish("done" if len(done) == len(items) else "failed")


def blind_items():
    text = {m.group(1): m.group(2) for m in re.finditer(r"### (\d+)\n(.*?)\n\n(?=### |\Z)", open(f"{ROOT}/blind/blind.md").read(), re.S)}
    mine = json.load(open(f"{ROOT}/blind/blind_scores.json"))
    return sorted(text.items(), key=lambda x: int(x[0])), mine


def sample(n):
    job = Job("04_sample", f"4. Draw {n:,} random articles for labelling", total=66, unit="parts scanned")
    ids = []
    parts = sorted(os.listdir(f"{ROOT}/parts"), key=lambda p: int(p[1:]))
    for p in parts:
        ids += json.load(open(f"{ROOT}/parts/{p}/emb_ids.json"))
    blind = {int(i) for i in json.load(open(f"{ROOT}/blind/blind_key.json"))["ids"].values()}
    want = set(random.Random(11).sample([i for i in ids if i not in blind], n))
    job.log(f"{len(ids):,} candidates; drew {n:,} at random (blind-read articles excluded)")
    out = {}
    for p in parts:
        for line in open(f"{ROOT}/parts/{p}/corpus.jsonl", encoding="utf-8"):
            i = int(line[7:line.index(",")])
            if i in want:
                c = json.loads(line)
                out[i] = f"{c['title']}\n{strip_refs(c['text'])[:2000]}"
        job.step()
    with open(f"{OUT}/sample.jsonl", "w") as f:
        for i in sorted(out):
            f.write(json.dumps({"id": i, "text": out[i]}) + "\n")
    job.log(f"wrote {len(out):,} articles to labels/sample.jsonl")
    job.finish()


def main():
    os.makedirs(OUT, exist_ok=True)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "calib":
        items, mine = blind_items()
        job = Job(f"04_calib_{arg}", f"4. Calibrate {arg}: label the 180 blind-read articles", unit="articles",
                  note="Agreement with Claude's own blind scores decides which model labels the big sample")
        run(arg, items, f"{OUT}/calib_{arg}.jsonl", job, check=mine)
    elif cmd == "sample":
        sample(int(arg))
    elif cmd == "label":
        items = [(str(x["id"]), x["text"]) for x in map(json.loads, open(f"{OUT}/sample.jsonl"))]
        job = Job(f"05_label_{arg}", f"5. Label {len(items):,} random articles with {arg}", unit="articles")
        run(arg, items, f"{OUT}/sample_{arg}.jsonl", job)


if __name__ == "__main__":
    main()

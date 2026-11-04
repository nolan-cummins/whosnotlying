"""
Blind spot-check of the DYK gate rankings (dyk_rank_{lr,mlp}.json from score_dyk.py). Per model: 30 random from the top 100k,
30 from ranks 90k-110k (the cutoff band) and 30 random from the bottom half. The union is shuffled into blind.md (numbered
articles, title + the 2,000 chars the model saw) and the bucket key goes to blind_key.json; read blind.md, write scores
{"n": 0-3} to blind_scores.json, then run with --report.

    python3 -I blind_sample.py /mnt/hdd2/wikipedia [--report]
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trim import strip_refs

N, TOP = 30, 100_000


def main(root):
    out = os.path.join(root, "blind")
    if "--report" in sys.argv:
        key = json.load(open(os.path.join(out, "blind_key.json")))
        sc = json.load(open(os.path.join(out, "blind_scores.json")))
        for kind, buckets in key["buckets"].items():
            for b, nums in buckets.items():
                v = [sc[str(n)] for n in nums]
                print(f"[{kind}] {b:<7} mean {sum(v) / len(v):.2f}  >=2: {sum(x >= 2 for x in v)}/{len(v)}  "
                      f"0s: {sum(x == 0 for x in v)}/{len(v)}")
        return
    rng = random.Random(7)
    picks = {}
    for kind in ("lr", "mlp"):
        r = json.load(open(os.path.join(root, f"dyk_rank_{kind}.json")))
        picks[kind] = {"top": rng.sample(r[:TOP], N), "cutoff": rng.sample(r[TOP - 10_000:TOP + 10_000], N),
                       "bottom": rng.sample(r[len(r) // 2:], N)}
    ids = sorted({i for b in picks.values() for v in b.values() for i in v})
    rng.shuffle(ids)
    num = {i: n for n, i in enumerate(ids)}
    want, text = set(ids), {}
    parts_dir = os.path.join(root, "parts")
    for p in os.listdir(parts_dir):
        for line in open(os.path.join(parts_dir, p, "corpus.jsonl"), encoding="utf-8"):
            i = int(line[7:line.index(",")]) if line.startswith('{"id": ') else json.loads(line)["id"]
            if i in want:
                c = json.loads(line)
                text[i] = f"{c['title']}\n{strip_refs(c['text'])[:2000]}"
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "blind.md"), "w") as f:
        for i in ids:
            f.write(f"### {num[i]}\n{text[i]}\n\n")
    key = {"ids": {num[i]: i for i in ids},
           "buckets": {k: {b: [num[i] for i in v] for b, v in bs.items()} for k, bs in picks.items()}}
    json.dump(key, open(os.path.join(out, "blind_key.json"), "w"))
    print(f"{len(ids)} articles -> {out}/blind.md")


if __name__ == "__main__":
    main(sys.argv[1])

"""
Experiments on one trimmed dump part (output of trim.py). Each test appends a section to D/exp/REPORT.md.

    python3 -I bench.py D bands|calib|quadrants|types
"""
import collections
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BANDS = [(0, 10), (10, 25), (25, 50), (50, 75), (75, 100)]
# Mass-produced article types (judged by infobox/taxobox); the "type cut" candidates.
BORING_BOX = {"species", "taxon", "settlement", "football biography", "football club season", "sportsperson",
              "baseball biography", "cricketer", "ice hockey player", "basketball biography", "officeholder",
              "election", "legislative election", "road", "station", "NRHP", "school", "album", "single", "song",
              "film", "television", "planet", "ship begin", "military person", "company", "musical artist",
              "person", "U.S. county", "river", "mountain", "body of water", "university", "airport", "football league season"}


def load(d):
    meta = {}
    for line in open(os.path.join(d, "meta.jsonl"), encoding="utf-8"):
        m = json.loads(line)
        meta[m["id"]] = m
    text = {}
    for line in open(os.path.join(d, "corpus.jsonl"), encoding="utf-8"):
        c = json.loads(line)
        text[c["id"]] = c
    return meta, text


def top_topic(m):
    return max(m["topics"], key=m["topics"].get) if m["topics"] else "-"


def band_of(m):
    return next(f"{a}-{b}" for a, b in BANDS if a <= m["pct"] < b or (b == 100 and m["pct"] >= a))


def sample(ids, text, n, rng, chars=300):
    out = []
    for i in rng.sample(ids, min(n, len(ids))):
        t = text[i]["text"][:chars].replace("\n", " ")
        out.append(f"- **{text[i]['title']}**: {t}")
    return out


def bands(meta, text, rng):
    out = ["## T1. Popularity bands (percentile within part)", "",
           "| band | articles | tokens (M) | chars p50 | chars p90 | top topics | top boxes |", "|---|---|---|---|---|---|---|"]
    groups = collections.defaultdict(list)
    for m in meta.values():
        groups[band_of(m)].append(m)
    samples = []
    for a, b in BANDS:
        g = groups[f"{a}-{b}"]
        ch = sorted(m["chars"] for m in g)
        tt = collections.Counter(top_topic(m) for m in g).most_common(4)
        bx = collections.Counter(m["infobox"] or "(none)" for m in g).most_common(4)
        out.append(f"| {a}-{b} | {len(g)} | {sum(ch) / 4e6:.1f} | {ch[len(ch) // 2]} | {ch[int(len(ch) * .9)]} | "
                   + ", ".join(f"{k} {100 * v // len(g)}%" for k, v in tt) + " | "
                   + ", ".join(f"{k} {100 * v // len(g)}%" for k, v in bx) + " |")
        samples += ["", f"### Band {a}-{b}: 10 random"] + sample([m["id"] for m in g], text, 10, rng)
    return out + samples


def calib(meta, text, rng):
    import fame
    by_pct = sorted(meta.values(), key=lambda m: m["pct"])
    picks = []
    for p in range(0, 100, 2):  # one article per 2-percentile step, 50 total, plus 10 from the top 1%
        g = [m for m in by_pct if p <= m["pct"] < p + 2]
        picks.append(rng.choice(g))
    picks += rng.sample([m for m in by_pct if m["pct"] >= 99], 10)
    views = fame.bulk([m["id"] for m in picks])
    out = ["## T2. popularity_score vs real views (60-day average, x30 = views/month)", "",
           "| pct | pop score | views/month | ratio (views/month per 1e-8) | title |", "|---|---|---|---|---|"]
    ratios = []
    for m in picks:
        v = views.get(m["id"])
        if v is None:
            continue
        r = (v * 30) / (m["pop"] / 1e-8) if m["pop"] else 0
        ratios.append(r)
        out.append(f"| {m['pct']:.1f} | {m['pop']:.2e} | {v * 30:.0f} | {r:.0f} | {text[m['id']]['title']} |")
    out += ["", f"Median ratio: {statistics.median(ratios):.0f} views/month per 1e-8 of score "
            f"(IQR {statistics.quantiles(ratios, n=4)[0]:.0f}-{statistics.quantiles(ratios, n=4)[2]:.0f}); {len(ratios)}/{len(picks)} had views."]
    return out


def quadrants(meta, text, rng):
    ms = list(meta.values())
    lk = statistics.median(m["links"] for m in ms)
    out = ["## T3. Popularity x incoming links", "", f"Low pop = bottom 25%, high pop = top 25%; links split at the median ({lk:.0f}).", "",
           "| quadrant | articles | chars p50 |", "|---|---|---|"]
    q = collections.defaultdict(list)
    for m in ms:
        p = "low pop" if m["pct"] < 25 else "high pop" if m["pct"] >= 75 else None
        if p:
            q[f"{p}, {'high' if m['links'] > lk else 'low'} links"].append(m)
    samples = []
    for k in sorted(q):
        ch = sorted(m["chars"] for m in q[k])
        out.append(f"| {k} | {len(q[k])} | {ch[len(ch) // 2]} |")
        samples += ["", f"### {k}: 8 random"] + sample([m["id"] for m in q[k]], text, 8, rng, 200)
    return out + samples


def types(meta, text, rng):
    out = ["## T4. Mass-produced types (infobox/taxobox in the boring list)", "",
           "| band | articles | boring-type share | no box share | tokens kept after cut (M) |", "|---|---|---|---|---|"]
    groups = collections.defaultdict(list)
    for m in meta.values():
        groups[band_of(m)].append(m)
    for a, b in BANDS:
        g = groups[f"{a}-{b}"]
        bor = [m for m in g if m["infobox"] in BORING_BOX]
        none = [m for m in g if not m["infobox"]]
        kept = sum(m["chars"] for m in g if m["infobox"] not in BORING_BOX) / 4e6
        out.append(f"| {a}-{b} | {len(g)} | {100 * len(bor) // len(g)}% | {100 * len(none) // len(g)}% | {kept:.1f} |")
    c = collections.Counter(m["infobox"] for m in meta.values() if m["infobox"])
    out += ["", "Most common boxes overall: " + ", ".join(f"{k} ({v})" for k, v in c.most_common(30))]
    low = [m["id"] for m in meta.values() if m["pct"] < 50 and not m["infobox"] and m["chars"] > 1500]
    out += ["", "### Survivors (bottom 50%, no box, >1500 chars): 12 random"] + sample(low, text, 12, rng)
    return out


ANCHORS = ["A dog was elected mayor of the town and served for several years.",
           "The court put a pig on trial for murder and sentenced it to death.",
           "The army fought a war against birds and lost.",
           "He ate an entire aeroplane, piece by piece, over two years.",
           "The town's official mascot was a potato, and its residents legally married it.",
           "The ship was accidentally sunk by its own torpedo, which circled back.",
           "The scientists trained pigeons to guide missiles from inside the warhead."]


def chunks(text, size=400):
    """~size-char windows on sentence boundaries (Cirrus text has no paragraph breaks)."""
    import re
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(s) > size:
            out.append(cur)
            cur = ""
        cur = (cur + " " + s).strip()
    return out + ([cur] if cur else [])


def embed(meta, text, rng):
    import time
    sys.path.insert(0, os.path.expanduser("~/src/liars/src"))
    from src.match import embed as emb
    ids = rng.sample([m["id"] for m in meta.values() if 25 <= m["pct"] < 90 and m["chars"] > 1500], 300)
    pieces = [(i, c) for i in ids for c in chunks(text[i]["text"])[:40]]
    av = emb(ANCHORS, timeout=120)
    t0, vecs = time.time(), []
    for k in range(0, len(pieces), 64):
        vecs += emb([c for _, c in pieces[k:k + 64]], timeout=300)
    dt = time.time() - t0
    chars = sum(len(c) for _, c in pieces)
    total_chars = 8.3e9 * 4 * 0.36  # whole-wiki plain text ~33G chars; obscure share 36%
    best = collections.defaultdict(lambda: (-1, ""))
    mean = collections.defaultdict(list)
    for (i, c), v in zip(pieces, vecs):
        s = max(sum(a * b for a, b in zip(v, x)) for x in av)
        mean[i].append(s)
        if s > best[i][0]:
            best[i] = (s, c)
    out = ["## T5. Embedding (qwen3-embedding 0.6b via Ollama, this GPU)", "",
           f"{len(pieces)} chunks / {chars / 1e6:.2f}M chars in {dt:.0f}s = {len(pieces) / dt:.0f} chunks/s, {chars / dt / 1e3:.0f}k chars/s.",
           f"Extrapolated: obscure 36% of the whole wiki (~{total_chars / 1e9:.0f}G chars) = {total_chars / (chars / dt) / 3600:.0f} h.", "",
           "Score = max cosine of a chunk to 7 absurd anchor sentences (dog mayor, pig trial, emu war, ...).", "",
           "### Top 10 articles by best chunk"]
    for i in sorted(best, key=lambda i: -best[i][0])[:10]:
        out.append(f"- {best[i][0]:.3f} **{text[i]['title']}**: {best[i][1][:250]}")
    out += ["", "### Top 10 articles by mean chunk"]
    for i in sorted(mean, key=lambda i: -statistics.mean(mean[i]))[:10]:
        out.append(f"- {statistics.mean(mean[i]):.3f} **{text[i]['title']}**: {text[i]['text'][:150]}")
    out += ["", "### Bottom 5 by best chunk"]
    for i in sorted(best, key=lambda i: best[i][0])[:5]:
        out.append(f"- {best[i][0]:.3f} **{text[i]['title']}**: {best[i][1][:150]}")
    return out


if __name__ == "__main__":
    d, test = sys.argv[1], sys.argv[2]
    meta, text = load(d)
    lines = globals()[test](meta, text, random.Random(7))
    os.makedirs(os.path.join(d, "exp"), exist_ok=True)
    with open(os.path.join(d, "exp", "REPORT.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")
    print("\n".join(lines[:14]))

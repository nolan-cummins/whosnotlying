"""Build packs/absurd-1.json: pilot (../ab/truths.py, lies.py) + atNN.txt / alNN.txt; verifies every quote.
Block: "@ Category | Title | Tag, Tag", statement, "- fact"s, truths: "S pub | year | url | archive | quote"
(+ "A ..." lines for source.also), last "# keywords". Ids at<NN>-<k> / al<NN>-<k>."""
import glob, json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H); sys.path.insert(0, H + "/../ab")
from truths import T
from lies import L
from atext import text
norm = lambda x: re.sub(r"[^a-z0-9]+", " ", x.lower().replace("’", "'")).strip()
bad = []
def src(pub, yr, url, arch, quote):
    if norm(quote) not in norm(text(arch.rsplit(".", 1)[0])): bad.append((arch, quote[:70]))
    d = {"publisher": pub, "year": int(yr) if str(yr).isdigit() else None, "url": url, "archive": arch, "quote": quote}
    return {k: v for k, v in d.items() if v is not None}
topics = []
for tid, cat, title, tags, stmt, facts, s, also, kw in T:
    source = src(*s)
    if also: source["also"] = [src(*a) for a in also]
    topics.append({"id": tid, "category": cat, "topic": title, "tags": tags, "source": source,
                   "summary": f"{stmt} Topics: {kw}.", "truth": {"text": stmt, "facts": facts}})
for lid, cat, title, tags, stmt, facts, kw in L:
    topics.append({"id": lid, "category": cat, "topic": title, "tags": tags,
                   "summary": f"{stmt} Topics: {kw}.", "lies": [{"text": stmt, "facts": facts}]})
for fn in sorted(glob.glob(H + "/a[tl][0-9][0-9].txt")):
    b = os.path.basename(fn); kind = b[1]
    for k, blk in enumerate(re.split(r"\n\s*\n", open(fn, encoding="utf-8").read().strip()), 1):
        ln = [x.strip() for x in blk.splitlines() if x.strip()]
        cat, title, tags = [x.strip() for x in ln[0].lstrip("@ ").split("|")]
        it = {"id": f"a{kind}{b[2:4]}-{k:02d}", "category": cat, "topic": title, "tags": [t.strip() for t in tags.split(",")]}
        facts = [x[2:].strip() for x in ln if x.startswith("- ")]
        kw = next(x[1:].strip() for x in ln if x.startswith("#"))
        it["summary"] = f"{ln[1]} Topics: {kw}."
        if kind == "t":
            S = [[p.strip() for p in x[2:].split("|", 4)] for x in ln[2:] if x[:2] in ("S ", "A ")]
            it["source"] = src(*S[0])
            if len(S) > 1: it["source"]["also"] = [src(*a) for a in S[1:]]
            it["truth"] = {"text": ln[1], "facts": facts}
        else:
            it["lies"] = [{"text": ln[1], "facts": facts}]
        topics.append(it)
famous = {x.strip() for x in open(H + "/famous.txt") if x.strip() and not x.startswith("#")} if os.path.exists(H + "/famous.txt") else set()
topics = [t for t in topics if t["id"] not in famous]
for b in bad: print("QUOTE NOT FOUND:", *b)
pack = {"id": "absurd-1", "name": "Absurd", "version": 1,
        "description": "Utterly absurd facts that are true (researched, each with a link and an offline copy), plus invented ones just as absurd. See sources/absurd/GUIDE.md.",
        "default_off": True, "topics": topics}
out = sys.argv[1] if len(sys.argv) > 1 else "/home/nolan/src/liars/src/packs/absurd-1.json"
json.dump(pack, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(out, "a").write("\n")
print(len(topics), "topics", "(%d bad quotes)" % len(bad))

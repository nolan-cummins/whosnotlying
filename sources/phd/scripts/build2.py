"""Merge compact item files into a pack: python3 build2.py <pack.json> FILE...
Files tNN.txt (truths) / lNN.txt (lies); blocks separated by blank lines:
  truth: "@ <paper idx> | Title | Tag, Tag | Institution"   lie: "@ <Category> | Title | Tag, Tag"
  then the statement line, "- fact" lines, lies: "J <journals> | <descriptor>", last "# keywords".
Ids: t<NN>-<k> / l<NN>-<k> (file number, block number), so rebuilding is stable."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meta import src, papers
HDR = {"name": "PhD Mode", "version": 1, "description": "Real findings from recent open-access papers, plus invented look-alike findings for liars. See sources/phd/GUIDE.md.", "default_off": True}

def summary(abstract, kw, words=170):
    w = re.sub(r"^Abstract\s*", "", abstract or "").split()
    return (" ".join(w[:words]) + ("..." if len(w) > words else "") + " Topics: " + kw + ".").strip()

def items(fn):
    kind, nn = os.path.basename(fn)[0], os.path.basename(fn)[1:3]
    for k, blk in enumerate(re.split(r"\n\s*\n", open(fn, encoding="utf-8").read().strip()), 1):
        ln = [x.strip() for x in blk.strip().splitlines() if x.strip()]
        head = [x.strip() for x in ln[0].lstrip("@ ").split("|")]
        facts = [x[2:].strip() for x in ln if x.startswith("- ")]
        for x in ln:
            if x.startswith("J "):
                j, d = x[2:].split("|")
                facts.append(f"Journals like {j.strip()} publish papers on {d.strip()}")
        kw = next(x[1:].strip() for x in ln if x.startswith("#"))
        text = ln[1]
        tags = [t.strip() for t in head[2].split(",")]
        tid = f"{kind}{nn}-{k:02d}"
        if kind == "t":
            i = int(head[0]); s = src(i); r = papers[i]
            assert s["archive"], f"{tid}: paper {i} has no archived PDF"
            yield {"id": tid, "category": r.get("subfield") or r.get("field"), "topic": head[1], "tags": tags,
                   "group": s["doi"], "source": {"journal": s["journal"], "year": s["year"], "doi": s["doi"], "url": s["url"],
                   "archive": s["archive"], "institution": head[3]}, "summary": summary(r["abstract"], kw),
                   "truth": {"text": text, "facts": facts}}
        else:
            yield {"id": tid, "category": head[0], "topic": head[1], "tags": tags,
                   "summary": text + " Topics: " + kw + ".", "lies": [{"text": text, "facts": facts}]}

path = sys.argv[1]
pid = os.path.basename(path)[:-5]
pack = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"id": pid, **HDR, "topics": []}
byid = {t["id"]: n for n, t in enumerate(pack["topics"])}
added = 0
for fn in sys.argv[2:]:
    for it in items(fn):
        if it["id"] in byid: pack["topics"][byid[it["id"]]] = it  # rebuild replaces
        else: pack["topics"].append(it); byid[it["id"]] = len(pack["topics"]) - 1; added += 1
open(path, "w", encoding="utf-8").write(json.dumps(pack, indent=1, ensure_ascii=False) + "\n")
print("added", added, "total", len(pack["topics"]))

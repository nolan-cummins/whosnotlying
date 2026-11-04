"""List papers.jsonl entries not yet used by any pack (index, archived?, journal, title)."""
import json, glob, os, sys
R = "/home/nolan/src/liars/src"
used = set()
for f in glob.glob(f"{R}/packs/*.json"):
    for t in json.load(open(f))["topics"]:
        d = (t.get("source") or {}).get("doi")
        if d: used.add(d.lower())
skip = set(open(os.path.join(os.path.dirname(__file__), "skip.txt")).read().split()) if os.path.exists(os.path.join(os.path.dirname(__file__), "skip.txt")) else set()
start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
for i, l in enumerate(open(f"{R}/sources/raw/openalex/papers.jsonl")):
    if i < start: continue
    r = json.loads(l); d = r["doi"].split("doi.org/")[-1].lower()
    if d in used or str(i) in skip: continue
    a = "A" if os.path.exists(f"/mnt/hdd2/liars-archive/{r['slug']}.pdf") else "-"
    print(i, a, (r.get("journal") or "")[:22], "|", r["title"][:110])

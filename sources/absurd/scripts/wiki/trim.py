"""
Split one CirrusSearch bulk dump part into plain-text bodies and a metadata sidecar.

    python3 -I trim.py IN.json[.bz2] OUTDIR      # -> OUTDIR/corpus.jsonl {id,title,text}, OUTDIR/meta.jsonl
    python3 -I trim.py --selftest

Input alternates {"index":...} header lines and page lines; only primary namespace-0 pages are kept.
pct is the page's popularity percentile within this part (0 = least viewed).
"""
import bisect
import bz2
import json
import os
import re
import sys
import tempfile


def pages(path):
    with (bz2.open if path.endswith(".bz2") else open)(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if "index" in d or d.get("page_type") != "primary" or d.get("namespace") != 0:
                continue
            yield d


# First citation in the trailing reference list: "Title". Publisher. Retrieved ... / ISBN / (PDF) / doi / page refs.
CITE = re.compile(r'"[^"]{5,200}"\.? [^.]{0,80}\. (Retrieved|Archived)|Retrieved \d{1,2} \w+ \d{4}|Retrieved \w+ \d{1,2}, \d{4}'
                  r'|ISBN[ -]|\(PDF\)|\bdoi:|\bpp?\. \d')
SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c(])')


def strip_refs(text):
    """Drop the reference list Cirrus appends to the body (cut at the sentence holding the first citation)."""
    m = CITE.search(text)
    if not m:
        return text
    s = text.rfind(". ", max(0, m.start() - 300), m.start())
    return text[:s + 1] if s >= 0 else text[:m.start()].rstrip()


def sentences(text):
    return [x for x in SENT.split(text) if x.strip()]


def meta(d):
    topics = {}
    for t in d.get("weighted_tags") or []:
        if t.startswith("classification.prediction.articletopic/"):
            name, _, w = t.split("/", 1)[1].rpartition("|")
            topics[name] = int(w)
    boxes = {"Template:Speciesbox": "species", "Template:Automatic taxobox": "taxon", "Template:Taxobox": "taxon"}
    infobox = next((t[17:] if t.startswith("Template:Infobox ") else boxes[t] for t in d.get("template") or []
                    if t.startswith("Template:Infobox ") or t in boxes), None)
    return {"id": d["page_id"], "pop": d.get("popularity_score") or 0.0, "links": d.get("incoming_links") or 0,
            "chars": len(d.get("text") or ""), "topics": topics, "infobox": infobox, "created": d.get("create_timestamp")}


def main(src, out):
    os.makedirs(out, exist_ok=True)
    rows = []
    with open(os.path.join(out, "corpus.jsonl"), "w", encoding="utf-8") as c:
        for d in pages(src):
            c.write(json.dumps({"id": d["page_id"], "title": d["title"], "text": d.get("text") or ""}, ensure_ascii=False) + "\n")
            rows.append(meta(d))
    pops = sorted(r["pop"] for r in rows)
    with open(os.path.join(out, "meta.jsonl"), "w", encoding="utf-8") as m:
        for r in rows:
            r["pct"] = round(100 * bisect.bisect_left(pops, r["pop"]) / len(pops), 2)
            m.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} articles -> {out}", file=sys.stderr)


def selftest():
    d = tempfile.mkdtemp()
    src = os.path.join(d, "in.json")
    with open(src, "w", encoding="utf-8") as f:
        f.write('{"index":{"_id":1}}\n')
        f.write(json.dumps({"page_id": 1, "title": "R", "page_type": "redirect", "namespace": 0, "text": ""}) + "\n")
        f.write('{"index":{"_id":2}}\n')
        f.write(json.dumps({"page_id": 2, "title": "Cold", "page_type": "primary", "namespace": 0, "text": "It hit −40 °C.",
                            "popularity_score": 1e-8, "template": ["Template:Infobox settlement"],
                            "weighted_tags": ["classification.prediction.articletopic/STEM.Earth and environment|870"]}) + "\n")
    main(src, d)
    corpus = [json.loads(x) for x in open(os.path.join(d, "corpus.jsonl"), encoding="utf-8")]
    m = [json.loads(x) for x in open(os.path.join(d, "meta.jsonl"), encoding="utf-8")]
    assert [c["id"] for c in corpus] == [2], corpus
    assert corpus[0]["text"] == "It hit −40 °C." and "−40 °C" in open(os.path.join(d, "corpus.jsonl"), encoding="utf-8").read()
    assert m[0]["infobox"] == "settlement" and m[0]["topics"] == {"STEM.Earth and environment": 870}
    body = 'He ate a bicycle. It took two years. "Odd Feats". The Times. Retrieved 3 May 2001. ISBN 1-2'
    assert strip_refs(body) == "He ate a bicycle. It took two years.", strip_refs(body)
    assert sentences("It hit −40 °C. Then 1990 came. \"Wow,\" he said.") == ["It hit −40 °C.", "Then 1990 came.", '"Wow," he said.']
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    elif len(sys.argv) == 3:
        main(*sys.argv[1:])
    else:
        sys.exit(__doc__)

#!/usr/bin/env python3
"""PhD Mode: Simple — the rewrite pipeline (see sources/phd/SIMPLE.md).

  python3 -I sources/phd/simple/pipeline.py fetch [--dois FILE] [--workers 4]   paper texts -> texts/simple/*.json (git-ignored) + texts-index.json
  python3 -I sources/phd/simple/pipeline.py batches [--ids FILE] [--papers 4] [--lies 30]   writer inputs -> work/batches/*.in.json
  python3 -I sources/phd/simple/pipeline.py status                                which batches still lack a writer output / a check
  python3 -I sources/phd/simple/pipeline.py revise <batch>        writer input for the items the checker sent back -> <batch>.revise.in.json
  python3 -I sources/phd/simple/pipeline.py apply-revise <batch>  merge <batch>.revise.out.json, re-check input for those items only
  python3 -I sources/phd/simple/pipeline.py validate                              deterministic checks + checker verdicts -> work/merged.json, checks.jsonl, review.jsonl
  python3 -I sources/phd/simple/pipeline.py build                                 work/merged.json -> packs/phd-mode-simple.json

The writer and checker steps are Claude Code subagents (Opus) that read one *.in.json / *.check.in.json
and write the matching *.out.json / *.check.json; the prompts they follow are in prompts/.
Everything under work/ and texts/ is reproducible and git-ignored; checks.jsonl and review.jsonl are kept.
"""
import argparse, collections, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PACK = os.path.join(ROOT, "packs", "phd-mode.json")
OUT_PACK = os.path.join(ROOT, "packs", "phd-mode-simple.json")
TEXTS = os.path.join(ROOT, "sources", "raw", "openalex", "texts", "simple")
WORK = os.path.join(HERE, "work")
BATCHES = os.path.join(WORK, "batches")
INDEX = os.path.join(HERE, "texts-index.json")
CHECKS = os.path.join(HERE, "checks.jsonl")
REVIEW = os.path.join(HERE, "review.jsonl")
UA = "whosnotlying-phd-simple/1.0 (mailto:admin@whosnotlying.com)"
MAX_WORDS = 9000          # paper text handed to the writer / checker (results and discussion are kept ahead of methods)
MAX_STATEMENT_WORDS = 28
MAX_FACT_WORDS = 14

def load_pack():
    return json.load(open(PACK, encoding="utf-8"))

def slug(doi):
    return re.sub(r"[^a-z0-9]+", "-", doi.lower()).strip("-")

def get(url, timeout=40, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return data if binary else data.decode("utf-8", "replace")

def words(s):
    return re.findall(r"\S+", s or "")

def cap_words(s, n=MAX_WORDS):
    w = words(s)
    return s if len(w) <= n else " ".join(w[:n]) + " […]"

# ---------------------------------------------------------------- fetch

def abstract_from_inverted(inv):
    if not inv:
        return ""
    pos = {}
    for w, idxs in inv.items():
        for i in idxs:
            pos[i] = w
    return " ".join(pos[i] for i in sorted(pos))

def openalex(doi):
    u = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="") + "?select=title,abstract_inverted_index,best_oa_location,primary_location,locations&mailto=admin@whosnotlying.com"
    w = json.loads(get(u))
    pdfs = []
    for loc in [w.get("best_oa_location"), w.get("primary_location"), *(w.get("locations") or [])]:
        if loc and loc.get("pdf_url") and loc["pdf_url"] not in pdfs:
            pdfs.append(loc["pdf_url"])
    return {"title": w.get("title") or "", "abstract": abstract_from_inverted(w.get("abstract_inverted_index")), "pdfs": pdfs}

def epmc_fulltext(doi):
    """Full text from Europe PMC (JATS XML) when the paper is in PMC; sections in reading order, references dropped."""
    from lxml import etree
    q = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%s&resultType=lite&format=json" % urllib.parse.quote('"' + doi + '"')
    hits = json.loads(get(q)).get("resultList", {}).get("result", [])
    pmcid = next((h.get("pmcid") for h in hits if h.get("pmcid")), None)
    if not pmcid:
        return None
    xml = get("https://www.ebi.ac.uk/europepmc/webservices/rest/%s/fullTextXML" % pmcid, binary=True)
    if len(xml) < 5000:
        return None
    root = etree.fromstring(xml)
    for bad in root.xpath("//ref-list|//xref|//table-wrap/table|//fn-group|//author-notes|//journal-meta|//permissions|//history|//contrib-group|//aff"):
        bad.getparent().remove(bad)
    def text_of(el):
        return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()
    parts = []  # (rank, text): abstract, results/discussion, introduction, then methods and the rest, so a cap trims methods first
    for ab in root.xpath("//front//abstract"):
        parts.append((0, "ABSTRACT\n" + text_of(ab)))
    body = root.find(".//body")
    if body is None:
        return None
    for sec in body.xpath("./sec|./p"):
        if sec.tag == "p":
            parts.append((2, text_of(sec)))
            continue
        title = sec.find("title")
        t = text_of(title).upper() if title is not None else ""
        if re.search(r"ACKNOWLEDG|SUPPLEMENT|DATA AVAILABILITY|AUTHOR CONTRIB|COMPETING|FUNDING|ETHICS", t):
            continue
        rank = 1 if re.search(r"RESULT|FINDING|DISCUSS|CONCLU|OUTCOME", t) else 2 if re.search(r"INTRO|BACKGROUND|OVERVIEW", t) else 3 if re.search(r"METHOD|MATERIAL|PROCEDURE|EXPERIMENTAL|STATISTIC", t) else 2
        body_text = " ".join(text_of(p) for p in sec.xpath(".//p|.//title|.//caption"))
        parts.append((rank, (t + "\n" if t else "") + body_text))
    parts.sort(key=lambda x: x[0])
    text = "\n\n".join(p for _, p in parts if p.strip())
    return text if len(words(text)) > 400 else None

def pdf_text(url):
    data = get(url, timeout=60, binary=True)
    if data[:4] != b"%PDF":
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        out = subprocess.run(["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True, text=True, timeout=120)
        txt = out.stdout
    finally:
        os.unlink(path)
    # drop the reference list and anything after it
    m = re.search(r"\n\s*(References|REFERENCES|Bibliography)\s*\n", txt)
    if m and m.start() > len(txt) * 0.4:
        txt = txt[: m.start()]
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt if len(words(txt)) > 400 else None

def fetch_one(doi, force=False):
    path = os.path.join(TEXTS, slug(doi) + ".json")
    if os.path.exists(path) and not force:
        rec = json.load(open(path, encoding="utf-8"))
        if rec.get("evidence") == "fulltext" or rec.get("tries", 0) >= 2:
            return rec
    rec = {"doi": doi, "evidence": "none", "source": None, "title": "", "abstract": "", "text": "", "tries": 0, "errors": []}
    try:
        meta = openalex(doi)
        rec["title"], rec["abstract"] = meta["title"], meta["abstract"]
        pdfs = meta["pdfs"]
    except Exception as e:  # noqa: BLE001
        rec["errors"].append("openalex: " + str(e)[:120])
        pdfs = []
    text = None
    try:
        text = epmc_fulltext(doi)
        if text:
            rec["source"] = "europepmc"
    except Exception as e:  # noqa: BLE001
        rec["errors"].append("epmc: " + str(e)[:120])
    if not text:
        for u in pdfs[:3]:
            try:
                text = pdf_text(u)
                if text:
                    rec["source"] = "pdf:" + urllib.parse.urlparse(u).netloc
                    break
            except Exception as e:  # noqa: BLE001
                rec["errors"].append("pdf: " + str(e)[:120])
    if text:
        rec["text"] = cap_words(text)
        rec["evidence"] = "fulltext"
    elif rec["abstract"]:
        rec["evidence"] = "abstract"
    rec["tries"] = (json.load(open(path)).get("tries", 0) + 1) if os.path.exists(path) else 1
    rec["words"] = len(words(rec["text"])) if rec["text"] else len(words(rec["abstract"]))
    json.dump(rec, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return rec

def cmd_fetch(args):
    os.makedirs(TEXTS, exist_ok=True)
    pack = load_pack()
    dois = sorted({t["group"] for t in pack["topics"] if t.get("group")})
    if args.dois:
        want = set(l.strip() for l in open(args.dois) if l.strip())
        dois = [d for d in dois if d in want]
    print(f"fetching {len(dois)} papers with {args.workers} workers", file=sys.stderr)
    done = collections.Counter()
    def work(d):
        try:
            rec = fetch_one(d, force=args.force)
            done[rec["evidence"]] += 1
            return rec
        except Exception as e:  # noqa: BLE001
            done["error"] += 1
            print("ERR", d, str(e)[:100], file=sys.stderr)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, _ in enumerate(ex.map(work, dois), 1):
            if i % 25 == 0:
                print(f"  {i}/{len(dois)} {dict(done)}", file=sys.stderr)
    write_index()
    print(dict(done))

def write_index():
    idx = {}
    for n in sorted(os.listdir(TEXTS)):
        if n.endswith(".json"):
            r = json.load(open(os.path.join(TEXTS, n), encoding="utf-8"))
            idx[r["doi"]] = {"evidence": r["evidence"], "source": r["source"], "words": r.get("words", 0)}
    json.dump(idx, open(INDEX, "w", encoding="utf-8"), indent=0, sort_keys=True)
    c = collections.Counter(v["evidence"] for v in idx.values())
    print("index:", dict(c), file=sys.stderr)

def text_for(doi):
    path = os.path.join(TEXTS, slug(doi) + ".json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None

# ---------------------------------------------------------------- batches

def read_prompt(name):
    return open(os.path.join(HERE, "prompts", name), encoding="utf-8").read()

def cmd_batches(args):
    os.makedirs(BATCHES, exist_ok=True)
    pack = load_pack()
    topics = pack["topics"]
    if args.ids:
        want = set(l.strip() for l in open(args.ids) if l.strip())
        topics = [t for t in topics if t["id"] in want]
    truths = [t for t in topics if t.get("truth")]
    lies = [t for t in topics if t.get("lies")]
    by_paper = collections.OrderedDict()
    for t in truths:
        by_paper.setdefault(t["group"], []).append(t)
    papers = list(by_paper.items())
    n = 0
    for i in range(0, len(papers), args.papers):
        chunk = papers[i : i + args.papers]
        bid = f"{args.prefix}t{i // args.papers + 1:03d}"
        items = []
        for doi, ts in chunk:
            rec = text_for(doi) or {"evidence": "none", "abstract": "", "text": "", "title": ""}
            items.append({
                "doi": doi, "title": rec.get("title", ""), "evidence": rec["evidence"],
                "paper_text": rec["text"] if rec["evidence"] == "fulltext" else "",
                "abstract": rec.get("abstract", ""),
                "items": [{"id": t["id"], "topic": t["topic"], "category": t["category"], "tags": t["tags"],
                           "source": {k: t["source"].get(k) for k in ("journal", "year", "institution")},
                           "phd_mode": t["truth"]} for t in ts],
            })
        json.dump({"batch": bid, "kind": "truth", "rules": read_prompt("writer_truth.md"), "papers": items},
                  open(os.path.join(BATCHES, bid + ".in.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n += 1
    for i in range(0, len(lies), args.lies):
        chunk = lies[i : i + args.lies]
        bid = f"{args.prefix}l{i // args.lies + 1:03d}"
        json.dump({"batch": bid, "kind": "lie", "rules": read_prompt("writer_lie.md"),
                   "items": [{"id": t["id"], "topic": t["topic"], "category": t["category"], "tags": t["tags"], "phd_mode": t["lies"][0]} for t in chunk]},
                  open(os.path.join(BATCHES, bid + ".in.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n += 1
    print(f"{n} batches in {BATCHES} ({len(papers)} papers / {len(truths)} truths, {len(lies)} lies)")

def make_check_input(bid, only=None):
    """The checker sees the paper (or abstract) and the proposed item only, never the writer's notes."""
    inp = json.load(open(os.path.join(BATCHES, bid + ".in.json"), encoding="utf-8"))
    out = json.load(open(os.path.join(BATCHES, bid + ".out.json"), encoding="utf-8"))
    proposed = {o["id"]: o for o in out.get("items", []) if only is None or o["id"] in only}
    if inp["kind"] == "truth":
        papers = []
        for p in inp["papers"]:
            papers.append({"doi": p["doi"], "evidence": p["evidence"], "paper_text": p["paper_text"], "abstract": p["abstract"],
                           "items": [{"id": it["id"], "topic": it["topic"], "proposed": {k: proposed.get(it["id"], {}).get(k) for k in ("statement", "facts", "key_findings", "summary")}}
                                     for it in p["items"] if it["id"] in proposed]})
        chk = {"batch": bid, "kind": "truth", "rules": read_prompt("checker_truth.md"), "papers": [p for p in papers if p["items"]]}
    else:
        chk = {"batch": bid, "kind": "lie", "rules": read_prompt("checker_lie.md"),
               "items": [{"id": it["id"], "topic": it["topic"], "category": it["category"], "original": it["phd_mode"],
                          "proposed": {k: proposed.get(it["id"], {}).get(k) for k in ("statement", "facts", "venues")}}
                         for it in inp["items"] if it["id"] in proposed]}
    json.dump(chk, open(os.path.join(BATCHES, bid + ".check.in.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def load_checks(bid):
    """Checker verdicts for a batch: the first pass, overlaid by any re-check of revised items."""
    out = {}
    for name in (bid + ".check.v1.json", bid + ".check.json"):
        path = os.path.join(BATCHES, name)
        if os.path.exists(path):
            for c in json.load(open(path, encoding="utf-8")).get("items", []):
                out[c["id"]] = c
    return out

def cmd_revise(args):
    """Writer input for the items the checker sent back: the original input, the proposal and the checker's notes."""
    bid = args.batch
    inp = json.load(open(os.path.join(BATCHES, bid + ".in.json"), encoding="utf-8"))
    out = json.load(open(os.path.join(BATCHES, bid + ".out.json"), encoding="utf-8"))
    checks = load_checks(bid)
    bad = {i for i, c in checks.items() if c.get("verdict") != "pass"}
    proposed = {o["id"]: o for o in out["items"]}
    if not bad:
        print("nothing to revise"); return
    if inp["kind"] == "truth":
        papers = []
        for pp in inp["papers"]:
            its = [dict(it, proposed=proposed.get(it["id"]), checker=checks[it["id"]]) for it in pp["items"] if it["id"] in bad]
            if its:
                papers.append(dict(pp, items=its))
        rev = {"batch": bid, "kind": "truth", "revision": True, "rules": inp["rules"], "papers": papers}
    else:
        rev = {"batch": bid, "kind": "lie", "revision": True, "rules": inp["rules"],
               "items": [dict(it, proposed=proposed.get(it["id"]), checker=checks[it["id"]]) for it in inp["items"] if it["id"] in bad]}
    json.dump(rev, open(os.path.join(BATCHES, bid + ".revise.in.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(bad)} items to revise: {sorted(bad)}")

def cmd_apply_revise(args):
    """Merge the writer's revision into the batch output and prepare a re-check of just those items."""
    bid = args.batch
    op = os.path.join(BATCHES, bid + ".out.json")
    out = json.load(open(op, encoding="utf-8"))
    rev = json.load(open(os.path.join(BATCHES, bid + ".revise.out.json"), encoding="utf-8"))
    revised = {o["id"]: o for o in rev["items"]}
    os.replace(op, os.path.join(BATCHES, bid + ".out.v1.json"))
    out["items"] = [revised.get(o["id"], o) for o in out["items"]]
    out["revised"] = sorted(revised)
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cp = os.path.join(BATCHES, bid + ".check.json")
    if os.path.exists(cp):
        os.replace(cp, os.path.join(BATCHES, bid + ".check.v1.json"))
    make_check_input(bid, only=set(revised))
    print(f"applied {len(revised)} revisions; re-check input written for {sorted(revised)}")

def cmd_status(args):
    ids = sorted(n[:-8] for n in os.listdir(BATCHES) if n.endswith(".in.json") and not n.endswith(".check.in.json") and not n.endswith(".revise.in.json"))
    need_write, need_check_in, need_check = [], [], []
    for b in ids:
        if not os.path.exists(os.path.join(BATCHES, b + ".out.json")):
            need_write.append(b)
        elif not os.path.exists(os.path.join(BATCHES, b + ".check.in.json")):
            make_check_input(b)
            need_check_in.append(b)
            if not os.path.exists(os.path.join(BATCHES, b + ".check.json")):
                need_check.append(b)
        elif not os.path.exists(os.path.join(BATCHES, b + ".check.json")):
            need_check.append(b)
    print(json.dumps({"batches": len(ids), "need_writer": need_write, "need_checker": need_check, "check_inputs_made": need_check_in}, indent=1))

# ---------------------------------------------------------------- validate

NUM = re.compile(r"\d[\d,.]*%?")

def count_numbers(s):
    return len(NUM.findall(s or ""))

def lint_item(kind, orig, item):
    """Deterministic rules; returns a list of problems (empty = fine)."""
    probs = []
    st = (item.get("statement") or "").strip()
    facts = [f.strip() for f in (item.get("facts") or []) if f and f.strip()]
    if not st:
        probs.append("no statement")
    if len(words(st)) > MAX_STATEMENT_WORDS:
        probs.append(f"statement {len(words(st))} words > {MAX_STATEMENT_WORDS}")
    if count_numbers(st) > 1:
        probs.append(f"statement has {count_numbers(st)} numbers")
    if st and st == (orig.get("text") or "").strip():
        probs.append("statement unchanged from PhD Mode")
    if re.search(r"\b[A-Z]{3,}\b", st) and not re.search(r"\b(AI|DNA|RNA|USA|UK|EU|NASA|GPS|MRI|CT|LED|3D|CO2|WHO|UN|NHS|FDA|CEO|TV|PhD)\b", st):
        probs.append("acronym in statement")
    lo, hi = (3, 5) if kind == "truth" else (2, 4)
    if not (lo <= len(facts) <= hi):
        probs.append(f"{len(facts)} facts (want {lo}-{hi})")
    for f in facts:
        if len(words(f)) > MAX_FACT_WORDS:
            probs.append(f"fact over {MAX_FACT_WORDS} words: {f[:40]}")
        if f.startswith("Journals like "):
            probs.append("journals line still in facts")
        if re.match(r"^[•\-*]", f):
            probs.append("bullet character in fact")
        if re.match(r"^(some|others|critics|skeptics|proponents)\b.*\b(argue|say|claim|believe|suggest|contend)", f, re.I):
            probs.append(f"fact is an argument: {f[:40]}")
    if kind == "lie":
        v = item.get("venues") or []
        if not (2 <= len(v) <= 3 and all(isinstance(x, str) and x.strip() for x in v)):
            probs.append("venues must list 2-3 journals")
    else:
        kf = item.get("key_findings") or []
        if len(kf) < 3:
            probs.append("fewer than 3 key findings")
        if len(words(item.get("summary") or "")) > 170:
            probs.append("summary over 170 words")
    return probs

def cmd_validate(args):
    pack = load_pack()
    orig = {t["id"]: t for t in pack["topics"]}
    merged, checks, review = {}, [], []
    ids = sorted(n[:-8] for n in os.listdir(BATCHES) if n.endswith(".in.json") and not n.endswith(".check.in.json") and not n.endswith(".revise.in.json"))
    counts = collections.Counter()
    for b in ids:
        op = os.path.join(BATCHES, b + ".out.json")
        cp = os.path.join(BATCHES, b + ".check.json")
        if not os.path.exists(op):
            counts["unwritten_batches"] += 1
            continue
        out = json.load(open(op, encoding="utf-8"))
        verdicts = load_checks(b)
        kind = out.get("kind") or ("truth" if b.split("t")[-1] != b else "lie")
        for item in out.get("items", []):
            tid = item["id"]
            o = orig.get(tid)
            if not o:
                counts["unknown_id"] += 1
                continue
            kind = "truth" if o.get("truth") else "lie"
            oside = o["truth"] if kind == "truth" else o["lies"][0]
            probs = lint_item(kind, oside, item)
            v = verdicts.get(tid)
            evidence = None
            if kind == "truth":
                evidence = (text_for(o["group"]) or {}).get("evidence")
            rec = {"id": tid, "kind": kind, "batch": b, "evidence": evidence, "lint": probs,
                   "checker": {k: v.get(k) for k in ("verdict", "statement_verdict", "issues", "facts", "suggested_edits", "notes")} if v else None}
            checks.append(rec)
            ok = not probs and v is not None and v.get("verdict") == "pass"
            if kind == "truth" and evidence != "fulltext" and ok:
                # abstract-only: the checker must have confirmed every claim is in the abstract
                ok = v.get("all_claims_in_abstract") is True
                if not ok:
                    rec["lint"] = probs + ["abstract-only paper: claims not all confirmed in the abstract"]
            if ok:
                merged[tid] = item
                counts["accepted"] += 1
            else:
                review.append({**rec, "proposed": item})
                counts["review"] += 1
    os.makedirs(WORK, exist_ok=True)
    json.dump(merged, open(os.path.join(WORK, "merged.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(CHECKS, "w", encoding="utf-8") as f:
        for c in checks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(REVIEW, "w", encoding="utf-8") as f:
        for r in review:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(dict(counts)))

# ---------------------------------------------------------------- build

DESCRIPTION = "The same papers as PhD Mode, each finding in one plain sentence with the numbers in the facts; easier to remember, retell and bluff."

def cmd_build(args):
    pack = load_pack()
    merged = json.load(open(os.path.join(WORK, "merged.json"), encoding="utf-8"))
    topics = []
    for t in pack["topics"]:
        m = merged.get(t["id"])
        if not m:
            continue
        if t.get("truth"):
            topics.append({"id": t["id"], "category": t["category"], "topic": m.get("topic") or t["topic"], "tags": t["tags"], "group": t["group"],
                           "source": t["source"], "summary": m["summary"].strip(),
                           "truth": {"text": m["statement"].strip(), "facts": [f.strip() for f in m["facts"]]}})
        else:
            lie = {"text": m["statement"].strip(), "facts": [f.strip() for f in m["facts"]], "venues": [v.strip() for v in m["venues"]]}
            kw = t["summary"].split(" Topics: ")[-1].rstrip(".") if " Topics: " in t["summary"] else ", ".join(t["tags"])
            topics.append({"id": t["id"], "category": t["category"], "topic": m.get("topic") or t["topic"], "tags": t["tags"],
                           "summary": f"{lie['text']} Topics: {kw}.", "lies": [lie]})
    out = {"id": "phd-mode-simple", "name": "PhD Mode: Simple", "version": 2, "description": DESCRIPTION, "default_off": True,
           "derived_from": "phd-mode", "topics": topics}
    json.dump(out, open(OUT_PACK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(OUT_PACK, "a").write("\n")
    print(f"{len(topics)} topics -> {OUT_PACK}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch"); f.add_argument("--dois"); f.add_argument("--workers", type=int, default=4); f.add_argument("--force", action="store_true")
    b = sub.add_parser("batches"); b.add_argument("--ids"); b.add_argument("--papers", type=int, default=4); b.add_argument("--lies", type=int, default=30); b.add_argument("--prefix", default="")
    sub.add_parser("status"); sub.add_parser("validate"); sub.add_parser("build")
    r = sub.add_parser("revise"); r.add_argument("batch")
    ar = sub.add_parser("apply-revise"); ar.add_argument("batch")
    a = ap.parse_args()
    {"fetch": cmd_fetch, "batches": cmd_batches, "status": cmd_status, "validate": cmd_validate, "build": cmd_build, "revise": cmd_revise, "apply-revise": cmd_apply_revise}[a.cmd](a)

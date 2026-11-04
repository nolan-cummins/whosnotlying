"""
Fetch recent open-access papers from top venues (OpenAlex) plus their full text, for writing the PhD pack.

    python3 sources/phd/fetch.py [--months 12] [--pool 300] [--take 40] [--search "3d printing"]
    python3 sources/phd/fetch.py --backfill packs/phd-mode-1.json   # archive PDFs for a pack's truths

Writes sources/raw/openalex/papers.jsonl (metadata) and texts/<slug>.txt (full text, git-ignored), and saves the
open-access PDF as the offline copy: $ARCHIVE_DIR/<slug>.pdf (default /mnt/hdd2/liars-archive, served at /archive/).
Full text: Europe PMC XML when the paper has a PMCID, else the OA PDF via `pdftotext`.
Picks round-robin across OpenAlex fields (most-cited first), so no discipline dominates.
Already-fetched DOIs are skipped, so re-running grows the pool for the next batch.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "raw", "openalex")
# Optional key (src/.env: OPENALEX_API_KEY=...) gives a private daily budget and cursor paging.
_env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
KEY = os.environ.get("OPENALEX_API_KEY") or next((l.split("=", 1)[1].strip() for l in open(_env) if l.startswith("OPENALEX_API_KEY=")), "") if os.path.exists(_env) else os.environ.get("OPENALEX_API_KEY", "")
ARCHIVE = os.environ.get("ARCHIVE_DIR", "/mnt/hdd2/liars-archive")
UA = {"User-Agent": "liars-phd-pack/1.0 (party game; contact via repo owner)"}
# Top journals with plenty of open-access output. ISSN -> short name shown in the game.
VENUES = {
    "0028-0836": "Nature", "0036-8075": "Science", "0092-8674": "Cell", "0027-8424": "PNAS",
    "2041-1723": "Nature Communications", "2375-2548": "Science Advances", "0031-9007": "Physical Review Letters",
    "2397-3374": "Nature Human Behaviour", "2397-334X": "Nature Ecology & Evolution", "1758-678X": "Nature Climate Change",
    "2397-3366": "Nature Astronomy", "1078-8956": "Nature Medicine", "0002-7863": "JACS", "1936-0851": "ACS Nano",
    "1745-2473": "Nature Physics", "1097-6256": "Nature Neuroscience", "0960-9822": "Current Biology",
    "2398-9629": "Nature Sustainability", "1544-9173": "PLOS Biology", "2050-084X": "eLife", "2058-7546": "Nature Energy",
    "1476-1122": "Nature Materials", "2522-5839": "Nature Machine Intelligence", "0028-4793": "NEJM", "0140-6736": "The Lancet",
    "2470-9476": "Science Robotics", "1476-4687": "Nature", "2662-1355": "Nature Food", "2520-1131": "Nature Electronics",
    "2731-9997": "Nature Cities", "2662-138X": "Nature Water",
}


def get(url, binary=False, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def works(months, pool, search="", any_venue=False, min_cites=5):
    since = (dt.date.today() - dt.timedelta(days=30 * months)).isoformat()
    # any_venue: topical search over titles+abstracts, best match first (full-text search + citation sort pulls
    # in big off-topic reviews); otherwise the top-venue list, most-cited first.
    flt = ",".join([f"from_publication_date:{since}", "type:article", "is_oa:true", "has_abstract:true"]
                   + ([f"cited_by_count:>{min_cites - 1}", "primary_location.source.type:journal",
                       f"title_and_abstract.search:{search}"] if any_venue
                      else ["primary_location.source.issn:" + "|".join(VENUES)]
                      + ([f"title_and_abstract.search:{search}"] if search else [])))
    sort = "relevance_score:desc" if search else "cited_by_count:desc"
    out, n = [], 1
    while len(out) < pool:  # plain page= paging: cursor paging needs an API key
        q = urllib.parse.urlencode({"filter": flt, "sort": sort, "per-page": 200, "page": n,
                                   **({"api_key": KEY} if KEY else {})})
        res = json.loads(get("https://api.openalex.org/works?" + q))["results"]
        if not res:
            break
        out += res
        n += 1
    return out[:pool]


def slug_of(doi):
    return re.sub(r"[^a-z0-9]+", "-", doi.lower().split("doi.org/")[-1]).strip("-")


def pdf_matches(data, title):
    """True if the PDF's first two pages carry most of the paper's title (OpenAlex locations sometimes point at a
    related preprint with a different title)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        head = subprocess.run(["pdftotext", "-q", "-l", "2", f.name, "-"], capture_output=True, text=True, timeout=60).stdout
    norm = lambda x: re.sub(r"[^a-z0-9]+", "", x.lower())
    words = [norm(x) for x in (title or "").split() if len(norm(x)) > 3]
    page = norm(head)
    return bool(words) and sum(x in page for x in words) >= 0.7 * len(words)


def oa_pdf(w):
    """The paper's open-access PDF bytes (publisher, repository or Europe PMC render), checked against its title."""
    urls = [loc.get("pdf_url") for loc in [w.get("best_oa_location") or {}] + (w.get("locations") or [])]
    pmcid = (w.get("ids") or {}).get("pmcid")
    if pmcid:
        urls.append(f"https://europepmc.org/articles/{pmcid.rsplit('/', 1)[-1]}/pdf/render")
    doi = (w.get("doi") or "").split("doi.org/")[-1]
    if doi.startswith("10.1038/"):  # Nature-family OA articles: the publisher PDF, often missing from OpenAlex
        urls.append(f"https://www.nature.com/articles/{doi.split('/', 1)[1]}.pdf")
    for url in dict.fromkeys(u for u in urls if u):
        try:
            data = get(url, binary=True)
            if data.startswith(b"%PDF") and pdf_matches(data, w.get("title")):
                return data
        except Exception:
            continue
    return None


def save_pdf(slug, data):
    os.makedirs(ARCHIVE, exist_ok=True)
    with open(os.path.join(ARCHIVE, slug + ".pdf"), "wb") as f:
        f.write(data)
    return slug + ".pdf"


def full_text(w, pdf):
    pmcid = (w.get("ids") or {}).get("pmcid")
    if pmcid:
        try:
            xml = get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid.rsplit('/', 1)[-1]}/fullTextXML")
            body = re.search(r"<body.*?</body>", xml, re.S)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.group(0) if body else xml))
            if len(text) > 5000:
                return text, "europepmc"
        except Exception:
            pass
    if pdf:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.flush()
            text = subprocess.run(["pdftotext", "-q", f.name, "-"], capture_output=True, text=True, timeout=60).stdout
        if len(text) > 5000:
            return re.sub(r"[ \t]+", " ", text), "pdf"
    return None, None


def backfill(pack_path, recheck=False):
    """Save the offline PDF for every paper truth in a pack that doesn't have one yet; list the misses.
    recheck: also re-verify existing PDFs against the title and replace any that don't match."""
    pack = json.load(open(pack_path, encoding="utf-8"))
    missing = []
    for doi in dict.fromkeys(t["source"]["doi"] for t in pack["topics"] if t.get("source")):
        slug = slug_of(doi)
        have = os.path.join(ARCHIVE, slug + ".pdf")
        if os.path.exists(have) and not recheck:
            continue
        w = json.loads(get("https://api.openalex.org/works/doi:" + doi + (f"?api_key={KEY}" if KEY else "")))
        if os.path.exists(have):
            if pdf_matches(open(have, "rb").read(), w.get("title")):
                continue
            print("MISMATCH, replacing " + slug)
            os.remove(have)
        pdf = oa_pdf(w)
        print(("saved " + save_pdf(slug, pdf)) if pdf else ("NO PDF " + doi))
        if not pdf:
            missing.append(doi)
    print(f"done; {len(missing)} without a PDF (archive their landing page with sources/archive/archive_page.py)")


def abstract(w):
    inv = w.get("abstract_inverted_index") or {}
    pos = sorted((i, word) for word, idx in inv.items() for i in idx)
    return " ".join(word for _, word in pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--pool", type=int, default=300)
    ap.add_argument("--take", type=int, default=40)
    ap.add_argument("--search", default="", help="full-text search, e.g. a player's field of expertise")
    ap.add_argument("--any-venue", action="store_true",
                    help="any peer-reviewed journal (with --search), for fields the top-venue list barely covers (MEMS, ESD...)")
    ap.add_argument("--min-cites", type=int, default=5, help="with --any-venue: minimum citations")
    ap.add_argument("--backfill", default="", help="pack JSON: archive PDFs for its paper truths, then exit")
    ap.add_argument("--recheck", action="store_true", help="with --backfill: re-verify saved PDFs against titles")
    a = ap.parse_args()
    if a.backfill:
        return backfill(a.backfill, a.recheck)
    os.makedirs(os.path.join(OUT, "texts"), exist_ok=True)
    meta_path = os.path.join(OUT, "papers.jsonl")
    have = set()
    if os.path.exists(meta_path):
        have = {json.loads(l)["doi"] for l in open(meta_path, encoding="utf-8")}
    by_field = {}
    for w in works(a.months, a.pool, a.search, a.any_venue, a.min_cites):
        if w.get("doi") in have or not w.get("doi"):
            continue
        if re.search(r"\b(review|survey|overview|perspective|roadmap|guideline|consensus|tutorial|progress and)\b", (w.get("title") or "").lower()):
            continue  # we want findings, not literature reviews
        field = ((w.get("primary_topic") or {}).get("field") or {}).get("display_name", "Other")
        if a.search:
            field = "search"  # keep relevance order instead of round-robin across fields
        by_field.setdefault(field, []).append(w)
    taken, skipped = 0, []
    with open(meta_path, "a", encoding="utf-8") as meta:
        while taken < a.take and any(by_field.values()):
            for field in list(by_field):
                if taken >= a.take or not by_field[field]:
                    continue
                w = by_field[field].pop(0)
                pdf = oa_pdf(w)
                text, how = full_text(w, pdf)
                if not text:
                    skipped.append(w["doi"])
                    continue
                slug = slug_of(w["doi"])
                archive = save_pdf(slug, pdf) if pdf else None
                with open(os.path.join(OUT, "texts", slug + ".txt"), "w", encoding="utf-8") as f:
                    f.write(text)
                src = (w.get("primary_location") or {}).get("source") or {}
                issn = next((i for i in src.get("issn") or [] if i in VENUES), None)
                meta.write(json.dumps({
                    "doi": w["doi"], "slug": slug, "title": w.get("title"), "journal": VENUES.get(issn) or src.get("display_name"),
                    "date": w.get("publication_date"), "field": field,
                    "subfield": ((w.get("primary_topic") or {}).get("subfield") or {}).get("display_name"),
                    "cited_by": w.get("cited_by_count"), "license": (w.get("best_oa_location") or {}).get("license"),
                    "text_source": how, "chars": len(text), "archive": archive, "abstract": abstract(w),
                }, ensure_ascii=False) + "\n")
                taken += 1
                print(f"[{taken}] {field[:28]:28} {VENUES.get(issn, '?')[:22]:22} {w.get('title', '')[:70]}")
    print(f"done: {taken} fetched, {len(skipped)} skipped (no readable full text)")


if __name__ == "__main__":
    main()

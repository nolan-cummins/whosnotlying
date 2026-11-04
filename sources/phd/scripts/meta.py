"""Per-DOI source info for pack items: journal, year, institution (majority of authors), url, archive."""
import json, os, re, sys, urllib.request, collections
RAW = "/home/nolan/src/liars/src/sources/raw/openalex"
CACHE = os.path.join(os.path.dirname(__file__), "meta_cache.json")
ENV = "/home/nolan/src/liars/src/.env"
KEY = next((l.split("=", 1)[1].strip() for l in open(ENV) if l.startswith("OPENALEX_API_KEY=")), "")
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
papers = [json.loads(l) for l in open(f"{RAW}/papers.jsonl")]

def work(doi):
    if doi not in cache:
        u = f"https://api.openalex.org/works/doi:{doi}" + (f"?api_key={KEY}" if KEY else "")
        cache[doi] = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "liars"}), timeout=60))
        json.dump(cache, open(CACHE, "w"))
    return cache[doi]

def src(i):
    r = papers[i]; doi = r["doi"].split("doi.org/")[-1]; w = work(doi)
    inst = collections.Counter()
    for a in w.get("authorships") or []:
        for ins in a.get("institutions") or []:
            inst[(ins.get("display_name"), ins.get("country_code"))] += 1
    top = [f"{n}" for (n, c), _ in inst.most_common(2)]
    cc = inst.most_common(1)[0][0][1] if inst else ""
    jn = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or r["journal"]
    arch = r["slug"] + ".pdf" if os.path.exists(f"/mnt/hdd2/liars-archive/{r['slug']}.pdf") else None
    return {"journal": jn, "year": w.get("publication_year"), "doi": doi, "url": "https://doi.org/" + doi,
            "archive": arch, "institution_candidates": top, "country": cc, "title": r["title"]}

if __name__ == "__main__":
    for i in map(int, sys.argv[1:]):
        print(i, json.dumps(src(i), ensure_ascii=False))

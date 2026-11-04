"""Fame gate for Absurd truths: monthly English Wikipedia pageviews of the best-matching article.
    python3 fame.py "search terms" ...          # one line per query: views/month, article title
Famous = an article people actually read. Rule of thumb (GUIDE.md): over ~1,500 views/month is too well known.
"""
import json, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "liars-fame-check/1.0 (https://liars.yozhikov.net)"}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20))


def monthly(title):
    time.sleep(1)  # Wikimedia rate-limits bursts
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    items = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{t}/monthly/2025010100/2025123100")["items"]
    return sum(i["views"] for i in items) // max(1, len(items))


def views(query):
    """Exact article title first (redirects followed); else the top search hit."""
    q = urllib.parse.quote(query)
    pages = get(f"https://en.wikipedia.org/w/api.php?action=query&titles={q}&redirects=1&format=json")["query"]["pages"]
    title = next(iter(pages.values())).get("title")
    if "-1" not in pages and title:
        return monthly(title), title
    hits = get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&srlimit=1&format=json")["query"]["search"]
    if not hits:
        return 0, "- (no article)"
    try:
        return monthly(hits[0]["title"]), hits[0]["title"] + " (search)"
    except Exception:
        return 0, hits[0]["title"] + " (search, no views)"


def bulk(pageids):
    """Average daily views over the last 60 days for each page id, 50 ids per request."""
    out = {}
    for i in range(0, len(pageids), 50):
        q = "action=query&prop=pageviews&pvipdays=60&format=json&pageids=" + "|".join(map(str, pageids[i:i + 50]))
        cont = ""
        while True:
            r = get("https://en.wikipedia.org/w/api.php?" + q + cont)
            for pid, p in r["query"]["pages"].items():
                v = [x for x in (p.get("pageviews") or {}).values() if x is not None]
                if v:
                    out[int(pid)] = sum(v) / len(v)
            if "continue" not in r:
                break
            cont = "&" + urllib.parse.urlencode(r["continue"])
            time.sleep(1)
        time.sleep(1)
    return out


if __name__ == "__main__":
    for q in sys.argv[1:]:
        v, title = views(q)
        print(f"{v:>8}  {title}", flush=True)

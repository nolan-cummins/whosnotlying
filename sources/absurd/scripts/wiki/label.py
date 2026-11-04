"""
Article labelling page for the gate: is this article worth mining for party-game facts?

    python3 -I label.py D [--port 8097] [--n 200]     # open http://<this machine>:8097
Sample: N articles from the Joey-scored pool (D/../joey/pool_out.json), spread evenly over Joey's richness score
(the score itself is hidden while labelling). Labels append to D/exp/labels/labels.jsonl; the latest per id wins.
Keys: 0-3 = richness, s = skip, b = back, n = focus note.
"""
import html
import json
import os
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trim import strip_refs

LEVELS = ["Nothing usable", "Thin: dry facts only", "At least one interesting fact", "Several surprising or memorable facts"]


def build_sample(d, pool_out, n):
    path = os.path.join(d, "exp", "labels", "sample.json")
    if os.path.exists(path):
        return json.load(open(path))
    scores = json.load(open(pool_out))
    rich = {int(i): sum(int(k) * v for k, v in a["richness"]["probabilities"].items()) for i, a in scores.items()}
    order = sorted(rich, key=rich.get)
    bins = 10
    rng = random.Random(9)
    ids = []
    for b in range(bins):  # equal draws from each score decile, so the rare rich articles are well represented
        chunk = order[b * len(order) // bins:(b + 1) * len(order) // bins]
        ids += rng.sample(chunk, n // bins)
    rng.shuffle(ids)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(ids, open(path, "w"))
    return ids


def load_text(d, ids):
    want, out = set(ids), {}
    for line in open(os.path.join(d, "corpus.jsonl"), encoding="utf-8"):
        c = json.loads(line)
        if c["id"] in want:
            out[c["id"]] = c
    return out


class App:
    def __init__(self, d, n):
        self.d = d
        self.ids = build_sample(d, os.path.join(os.path.dirname(d.rstrip("/")), "joey", "pool_out.json"), n)
        self.text = load_text(d, self.ids)
        self.path = os.path.join(d, "exp", "labels", "labels.jsonl")

    def labels(self):
        out = {}
        if os.path.exists(self.path):
            for line in open(self.path, encoding="utf-8"):
                r = json.loads(line)
                out[r["id"]] = r
        return out

    def save(self, rec):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def page(self, pos):
        lab = self.labels()
        done = sum(1 for i in self.ids if i in lab and lab[i].get("richness") is not None)
        if pos is None:
            pos = next((k for k, i in enumerate(self.ids) if i not in lab), len(self.ids))
        if pos >= len(self.ids):
            return f"<h2>All {len(self.ids)} done.</h2><p><a href='/?pos=0'>Review from the start</a></p>"
        i = self.ids[pos]
        c = self.text[i]
        cur = lab.get(i, {})
        body = html.escape(strip_refs(c["text"]))
        btns = "".join(
            f"<button name='r' value='{k}' class='{'on' if cur.get('richness') == k else ''}'><b>{k}</b> {html.escape(t)}</button>"
            for k, t in enumerate(LEVELS))
        return f"""
<div class=top>{done}/{len(self.ids)} labelled &middot; item {pos + 1}
 &middot; <a href='/?pos={max(0, pos - 1)}'>back (b)</a> &middot; <a href='/?pos={pos + 1}'>next</a></div>
<h2><a href='https://en.wikipedia.org/wiki/{html.escape(c["title"].replace(" ", "_"))}' target=_blank>{html.escape(c["title"])}</a></h2>
<form method=post action='/label'>
 <input type=hidden name=id value='{i}'><input type=hidden name=pos value='{pos}'>
 <div class=btns>{btns}<button name='r' value='skip'>skip (s)</button></div>
 <input id=note name=note placeholder='optional note (n)' value='{html.escape(cur.get("note", ""))}'>
</form>
<div class=text>{body}</div>"""


CSS = """body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:1em auto;padding:0 1em;background:#111;color:#ddd}
a{color:#8cf}.top{color:#999;font-size:14px}.btns{display:flex;flex-wrap:wrap;gap:.4em;margin:.6em 0}
button{background:#222;color:#ddd;border:1px solid #444;border-radius:6px;padding:.5em .8em;font-size:15px;cursor:pointer}
button.on{background:#264;border-color:#6c8}#note{width:100%;padding:.4em;background:#1a1a1a;color:#ddd;border:1px solid #444}
.text{white-space:pre-wrap;margin-top:1em;color:#ccc}"""
JS = """document.addEventListener('keydown',e=>{if(e.target.id==='note'){if(e.key==='Escape')e.target.blur();return}
const f=document.querySelector('form');if(!f)return;
if('0123'.includes(e.key)){f.querySelector(`button[value='${e.key}']`).click()}
else if(e.key==='s'){f.querySelector("button[value='skip']").click()}
else if(e.key==='b'){location=document.querySelector('.top a').href}
else if(e.key==='n'){e.preventDefault();document.getElementById('note').focus()}});"""


def handler(app):
    class H(BaseHTTPRequestHandler):
        def send(self, body, code=200, loc=None):
            self.send_response(code)
            if loc:
                self.send_header("Location", loc)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if body:
                self.wfile.write(f"<!doctype html><meta name=viewport content='width=device-width'><style>{CSS}</style>{body}<script>{JS}</script>".encode())

        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if urlparse(self.path).path == "/labels.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(list(app.labels().values())).encode())
                return
            self.send(app.page(int(q["pos"][0]) if "pos" in q else None))

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            f = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
            i, pos = int(f["id"]), int(f["pos"])
            if i not in app.ids:  # only items from the sample can be labelled
                return self.send("unknown id", 400)
            r = f.get("r")
            if r != "skip":
                if r not in ("0", "1", "2", "3"):
                    return self.send("bad label", 400)
                app.save({"id": i, "richness": int(r), "minable": int(r) >= 2, "note": f.get("note", "")[:500], "ts": time.time()})
            self.send("", 303, f"/?pos={pos + 1}")

        def log_message(self, *a):
            pass
    return H


if __name__ == "__main__":
    d = sys.argv[1]
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8097
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 200
    app = App(d, n)
    print(f"{len(app.ids)} articles; http://0.0.0.0:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), handler(app)).serve_forever()

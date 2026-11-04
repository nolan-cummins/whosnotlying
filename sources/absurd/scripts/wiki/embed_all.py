"""
Embed every candidate article (title + first 2,000 chars, reference list stripped) with Qwen3-Embedding-0.6B on one
or more vLLM servers, with a live progress display. Batches come from one shared queue, so each server takes work as
fast as it can; a server that fails is rested and retried while the others carry on.

    python3 -I embed_all.py PARTS_DIR [--servers URL,URL] [--workers 4] [--bench N]
Per part pN: pN/emb.npy (float16, unit-normalised, one row per candidate) and pN/emb_ids.json (page ids, same order).
Parts that already have emb.npy are skipped, so Ctrl-C and rerun resumes (the part in progress restarts).
--bench N embeds N articles from p0 only, times each server alone and together, and writes nothing.
Candidates: popularity percentile 10-90, >= 600 chars, not a list or disambiguation page.
"""
import collections
import json
import os
import queue
import sys
import threading
import time
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trim import strip_refs

BATCH = 64
DEFAULT_SERVERS = "http://127.0.0.1:8092,http://10.0.0.13:8092"


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def keep_meta(m):
    return 10 <= m["pct"] < 90 and m["chars"] >= 600


def candidates(part_dir):
    keep = set()
    for line in open(os.path.join(part_dir, "meta.jsonl"), encoding="utf-8"):
        m = json.loads(line)
        if keep_meta(m):
            keep.add(m["id"])
    out = []
    for line in open(os.path.join(part_dir, "corpus.jsonl"), encoding="utf-8"):
        c = json.loads(line)
        if c["id"] in keep and not c["title"].startswith("List of") and "(disambiguation)" not in c["title"] \
                and "may refer to" not in c["text"][:400]:
            out.append((c["id"], f"{c['title']}\n{strip_refs(c['text'])[:2000]}"))
    return out


def post(url, texts):
    body = json.dumps({"model": "qwen3-emb", "input": texts, "truncate_prompt_tokens": 1000}).encode()
    req = urllib.request.Request(url + "/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return [d["embedding"] for d in sorted(r["data"], key=lambda d: d["index"])]


def short(url):
    return {"127.0.0.1": "3080", "10.0.0.13": "4070"}.get(url.split("//")[1].split(":")[0], url.split("//")[1])


class Stats:
    """Counters shared by the workers and the display."""

    def __init__(self, servers):
        self.lock = threading.Lock()
        self.servers = servers
        self.done = collections.Counter()          # articles embedded per server, whole run
        self.recent = collections.deque()          # (time, server, n) for rolling rates
        self.status = {s: "ok" for s in servers}
        self.log = collections.deque(maxlen=5)
        self.part, self.part_done, self.part_total = "", 0, 0
        self.start = time.time()
        self.history = collections.deque(maxlen=24 * 60)  # [unix time, articles/s], one point a minute
        self.last_hist = time.time()

    def add(self, url, n):
        with self.lock:
            self.done[url] += n
            self.part_done += n
            self.recent.append((time.time(), url, n))

    def rate(self, url=None, window=60):
        with self.lock:
            now = time.time()
            while self.recent and self.recent[0][0] < now - 600:
                self.recent.popleft()
            n = sum(k for t, u, k in self.recent if t >= now - window and (url is None or u == url))
        return n / max(1.0, min(window, now - self.start))  # early on, average over the time actually elapsed

    def note(self, msg):
        with self.lock:
            self.log.append(f"{time.strftime('%H:%M:%S')} {msg}")


def run(items, servers, workers, stats):
    """Embed (id, text) items across servers; returns vectors in input order."""
    q = queue.Queue()
    for k in range(0, len(items), BATCH):
        q.put(k)
    vecs = [None] * len(items)
    remaining = [q.qsize()]
    lock = threading.Lock()

    def work(url):
        fails = 0
        while True:
            with lock:
                if remaining[0] == 0:
                    return
            try:
                k = q.get(timeout=1)
            except queue.Empty:
                continue  # another worker may still hand a failed batch back
            try:
                for j, v in enumerate(post(url, [t for _, t in items[k:k + BATCH]])):
                    vecs[k + j] = v
                with lock:
                    remaining[0] -= 1
                stats.add(url, len(items[k:k + BATCH]))
                if fails:
                    stats.note(f"{short(url)} recovered")
                    stats.status[url] = "ok"
                fails = 0
            except Exception as e:
                q.put(k)  # hand the batch back for any server to take
                fails += 1
                wait = min(300, 15 * fails)
                stats.status[url] = f"error, retry in {wait}s"
                if fails == 1 or fails % 10 == 0:
                    stats.note(f"{short(url)}: {str(e)[:70]}")
                time.sleep(wait)

    threads = [threading.Thread(target=work, args=(s,), daemon=True) for s in servers for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return vecs


def bar(frac, width=30):
    n = int(width * max(0.0, min(1.0, frac)))
    return "#" * n + "-" * (width - n)


def snapshot(stats, total, done_before, t0, state):
    done = done_before + sum(stats.done.values())
    if state[0] == "finished":
        total = done  # the total was a metadata estimate; the title filters drop a few more
    r = stats.rate(window=120)
    eta_h = (total - done) / r / 3600 if r > 0 else None
    return {"state": state[0], "started": t0, "now": time.time(), "done": done, "total": total, "rate": r, "eta_h": eta_h,
            "part": stats.part, "part_done": stats.part_done, "part_total": stats.part_total,
            "servers": [{"name": short(u), "url": u, "rate": stats.rate(u), "done": stats.done[u], "status": stats.status[u]}
                        for u in stats.servers],
            "history": list(stats.history), "log": list(stats.log)}


def display(stats, total, done_before, t0, stop, state):
    lines = 0
    while not stop.is_set():
        if time.time() - stats.last_hist >= 60:  # one point a minute for the page's rate chart
            stats.last_hist = time.time()
            with stats.lock:
                stats.history.append([round(time.time()), round(stats_rate_unlocked(stats), 1)])
        if sys.stdout.isatty():
            d = snapshot(stats, total, done_before, t0, state)
            eta = f"ETA {d['eta_h']:.1f} h (~{time.strftime('%H:%M', time.localtime(time.time() + d['eta_h'] * 3600))})" if d["eta_h"] else "ETA ?"
            out = [f"Embedding Wikipedia candidates  (started {time.strftime('%H:%M', time.localtime(t0))}, "
                   f"running {(time.time() - t0) / 3600:.1f} h)  web: http://10.0.0.12:{PORT}",
                   f"overall [{bar(d['done'] / max(1, total))}] {d['done']:,}/{total:,} ({100 * d['done'] / max(1, total):.1f}%)  "
                   f"{d['rate']:.0f}/s  {eta}",
                   f"part {d['part']:>4} [{bar(d['part_done'] / max(1, d['part_total']))}] {d['part_done']:,}/{d['part_total']:,}"]
            out += [f"  {x['name']:>5}  {x['rate']:6.1f}/s  {x['done']:>10,} done  {x['status']}" for x in d["servers"]]
            out += [f"  {m}" for m in d["log"]]
            sys.stdout.write((f"\x1b[{lines}F" if lines else "") + "".join(f"\x1b[2K{x}\n" for x in out) + "\x1b[J")
            sys.stdout.flush()
            lines = len(out)
        stop.wait(2)


def stats_rate_unlocked(stats, window=60):
    now = time.time()
    n = sum(k for t, u, k in stats.recent if t >= now - window)
    return n / max(1.0, min(window, now - stats.start))


PORT = int(arg("--port", 8097))
PAGE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "embed_status.html"), encoding="utf-8").read()


def serve(get):
    """Read-only status page on the LAN: / (HTML) and /status.json."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body, ctype = (json.dumps(get()).encode(), "application/json") if self.path.startswith("/status.json") \
                else (PAGE.encode(), "text/html; charset=utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def main():
    parts_dir = sys.argv[1]
    servers = arg("--servers", DEFAULT_SERVERS).split(",")
    workers = int(arg("--workers", 4))
    up = []
    for s in servers:
        try:
            urllib.request.urlopen(s + "/health", timeout=5)
            up.append(s)
        except Exception as e:
            print(f"{s} not reachable ({e}); continuing without it")
    if not up:
        sys.exit("no vLLM server reachable")
    if "--bench" in sys.argv:
        items = candidates(os.path.join(parts_dir, "p0"))[:int(arg("--bench", 2000))]
        for s in up + ([None] if len(up) > 1 else []):
            use = up if s is None else [s]
            st = Stats(use)
            t0 = time.time()
            run(items, use, workers, st)
            dt = time.time() - t0
            print(f"{'ALL' if s is None else short(s)}: {len(items) / dt:.1f} articles/s (" +
                  ", ".join(f"{short(u)} {100 * st.done[u] / len(items):.0f}%" for u in use) + ")", flush=True)
        return
    parts = sorted((d for d in os.listdir(parts_dir) if d.startswith("p")), key=lambda d: int(d[1:]))
    todo = [p for p in parts if not os.path.exists(os.path.join(parts_dir, p, "emb.npy"))]
    print(f"counting candidates in {len(parts)} parts ({len(parts) - len(todo)} already embedded)...", flush=True)
    est = {}
    for p in parts:  # metadata-only estimate (titles filter a few more out); exact counts replace it as parts finish
        est[p] = sum(keep_meta(json.loads(line)) for line in open(os.path.join(parts_dir, p, "meta.jsonl"), encoding="utf-8"))
    done_before = sum(est[p] for p in parts if p not in todo)
    stats, stop, t0 = Stats(up), threading.Event(), time.time()
    stats.note(f"servers: {', '.join(short(s) for s in up)}; {len(todo)} parts to go")
    state = ["running"]
    total = sum(est.values())
    serve(lambda: snapshot(stats, total, done_before, t0, state))
    stats.note(f"status page on port {PORT}")
    disp = threading.Thread(target=display, args=(stats, total, done_before, t0, stop, state), daemon=True)
    disp.start()
    try:
        for p in todo:
            pd = os.path.join(parts_dir, p)
            items = candidates(pd)
            with stats.lock:
                stats.part, stats.part_done, stats.part_total = p, 0, len(items)
            vecs = run(items, up, workers, stats)
            arr = np.asarray(vecs, dtype=np.float32)
            arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
            np.save(os.path.join(pd, "emb.tmp.npy"), arr.astype(np.float16))
            json.dump([i for i, _ in items], open(os.path.join(pd, "emb_ids.json"), "w"))
            os.replace(os.path.join(pd, "emb.tmp.npy"), os.path.join(pd, "emb.npy"))  # written last: marks the part done
            stats.note(f"{p} saved ({len(items):,} articles)")
    except KeyboardInterrupt:
        state[0] = "stopped"
        stop.set()
        disp.join()
        print("\nstopped; finished parts are saved, rerun to resume")
        sys.exit(130)
    state[0] = "finished"
    stats.note("all parts done")
    stop.set()
    disp.join()
    print(f"\nall done in {(time.time() - t0) / 3600:.1f} h")
    if "--linger" in sys.argv:  # keep the status page up after finishing
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()

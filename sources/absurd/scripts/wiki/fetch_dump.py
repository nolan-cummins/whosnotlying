#!/usr/bin/env python3
"""
Download the English Wikipedia CirrusSearch dump parts, 2 at a time (Wikimedia's per-IP connection limit), with
resume, retries and a live progress display.

    python3 fetch_dump.py [DIR] [--jobs 2] [--snapshot 20261025] [--mirror yourorg|umu|wikimedia]
DIR defaults to /mnt/hdd2/wikipedia/dumps; --mirror defaults to yourorg (Wikimedia itself allows only 2 connections per IP).

Parts already present (complete .bz2, or an unpacked .json) are skipped. Partial files are kept as *.part and
resumed with HTTP Range requests. A part counts as done only when its size matches the server's Content-Length.
Ctrl-C stops cleanly; rerun to resume.
"""
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

UA = "liars-research/1.0 (https://liars.yozhikov.net)"
# Mirrors carry the same files; your.org measured ~84 MiB/s per connection vs ~2.3 for Wikimedia itself (2026-11-02).
MIRRORS = {"yourorg": "https://dumps.wikimedia.your.org", "umu": "https://ftp.acc.umu.se/mirror/wikimedia.org",
           "wikimedia": "https://dumps.wikimedia.org"}
BASE = "{host}/other/cirrus_search_index/{snap}/index_name%3Denwiki_content/"
RETRIES, CHUNK = 20, 1 << 20


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def listing(base):
    req = urllib.request.Request(base, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=60).read().decode()
    return sorted(set(re.findall(r"enwiki_content-\d+-\d+\.json\.bz2", html)))


class Progress:
    def __init__(self, names):
        self.lock = threading.Lock()
        self.state = {}  # name -> [done_bytes, total_bytes, status]
        self.todo = len(names)
        self.finished = 0
        self.t0 = time.time()
        self.got0 = 0  # bytes fetched this session
        self.lines = 0

    def update(self, name, done=None, total=None, status=None, add=0):
        with self.lock:
            s = self.state.setdefault(name, [0, 0, ""])
            if done is not None:
                s[0] = done
            if total is not None:
                s[1] = total
            if status is not None:
                s[2] = status
            self.got0 += add

    def finish(self, name):
        with self.lock:
            self.state.pop(name, None)
            self.finished += 1

    def draw(self):
        with self.lock:
            el = max(1e-6, time.time() - self.t0)
            rate = self.got0 / el
            out = []
            for name, (d, t, st) in sorted(self.state.items()):
                pct = d / t if t else 0
                bar = "#" * int(30 * pct) + "-" * (30 - int(30 * pct))
                out.append(f"{name[-14:-9]} [{bar}] {pct:6.1%} {d / 2**20:7.0f}/{t / 2**20:.0f} MiB {st}")
            left = self.todo - self.finished
            eta = ""
            if rate > 0:
                remaining = sum(t - d for d, t, _ in self.state.values()) + max(0, left - len(self.state)) * 637e6
                eta = f", ETA {remaining / rate / 3600:.1f} h"
            out.append(f"parts done {self.finished}/{self.todo} | {rate / 2**20:.1f} MiB/s{eta}")
            sys.stdout.write(f"\x1b[{self.lines}F" if self.lines else "")
            sys.stdout.write("".join(f"\x1b[2K{line}\n" for line in out))
            sys.stdout.write("\x1b[J")
            sys.stdout.flush()
            self.lines = len(out)


def fetch(url, path, name, prog, stop):
    part = path + ".part"
    for attempt in range(1, RETRIES + 1):
        if stop.is_set():
            return False
        have = os.path.getsize(part) if os.path.exists(part) else 0
        req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:  # server ignored Range: start over
                    have = 0
                total = have + int(r.headers.get("Content-Length", 0))
                prog.update(name, done=have, total=total, status="")
                with open(part, "ab" if have else "wb") as f:
                    while not stop.is_set():
                        buf = r.read(CHUNK)
                        if not buf:
                            break
                        f.write(buf)
                        have += len(buf)
                        prog.update(name, done=have, add=len(buf))
            if stop.is_set():
                return False
            if have == total and total > 0:
                os.replace(part, path)
                return True
            raise IOError(f"short read {have}/{total}")
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:  # requested range past the end: the .part is already complete
                os.replace(part, path)
                return True
            err = f"HTTP {e.code}"
        except Exception as e:
            err = str(e)[:60]
        wait = min(120, 5 * attempt)
        prog.update(name, status=f"retry {attempt}/{RETRIES} in {wait}s ({err})")
        for _ in range(wait):
            if stop.is_set():
                return False
            time.sleep(1)
    prog.update(name, status="FAILED")
    return False


def main():
    out = next((a for a in sys.argv[1:] if not a.startswith("--") and sys.argv[sys.argv.index(a) - 1] not in ("--jobs", "--snapshot", "--mirror")),
               "/mnt/hdd2/wikipedia/dumps")
    jobs, snap = int(arg("--jobs", 2)), arg("--snapshot", "20261025")
    base = BASE.format(host=MIRRORS[arg("--mirror", "yourorg")], snap=snap)
    os.makedirs(out, exist_ok=True)
    names = listing(base)
    todo = [n for n in names if not os.path.exists(os.path.join(out, n)) and not os.path.exists(os.path.join(out, n[:-4]))]
    print(f"{len(names)} parts in snapshot {snap}; {len(names) - len(todo)} already here; fetching {len(todo)} into {out}, {jobs} at a time from {base.split("/other")[0]}\n")
    prog, stop, queue, failed = Progress(todo), threading.Event(), list(todo), []
    qlock = threading.Lock()

    def worker():
        while not stop.is_set():
            with qlock:
                if not queue:
                    return
                name = queue.pop(0)
            ok = fetch(base + name, os.path.join(out, name), name, prog, stop)
            if ok:
                prog.finish(name)
            elif not stop.is_set():
                failed.append(name)
                prog.finish(name)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(jobs)]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            prog.draw()
            time.sleep(1)
        prog.draw()
    except KeyboardInterrupt:
        stop.set()
        print("\nstopping; partial files are kept and resume on the next run")
        for t in threads:
            t.join(timeout=5)
        sys.exit(130)
    print(f"\ndone. failed: {failed or 'none'}" + ("  (rerun to retry)" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

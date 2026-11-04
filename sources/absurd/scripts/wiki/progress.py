"""
Job status for the LAN dashboard (dash.py): each long step writes STATUS_DIR/<name>.json, the page renders every file.

    from progress import Job
    job = Job("label", "Label 3,000 articles", total=3000, unit="articles")
    job.step(); job.metric("agreement", "81%"); job.point("loss", epoch, loss); job.log("..."); job.finish()
"""
import json
import os
import time

STATUS_DIR = os.environ.get("STATUS_DIR", "/mnt/hdd2/wikipedia/status")


class Job:
    def __init__(self, name, title, total=None, unit="items", note=""):
        os.makedirs(STATUS_DIR, exist_ok=True)
        self.path = os.path.join(STATUS_DIR, f"{name}.json")
        self.d = {"name": name, "title": title, "state": "running", "started": time.time(), "updated": time.time(),
                  "done": 0, "total": total, "unit": unit, "note": note, "metrics": {}, "series": {}, "log": []}
        self._last = 0
        self.flush(force=True)

    def flush(self, force=False):
        if not force and time.time() - self._last < 1:  # at most one write a second
            return
        self._last = self.d["updated"] = time.time()
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.d, f)
        os.replace(tmp, self.path)

    def step(self, n=1):
        self.d["done"] += n
        self.flush()

    def set(self, done=None, total=None):
        if done is not None:
            self.d["done"] = done
        if total is not None:
            self.d["total"] = total
        self.flush()

    def metric(self, key, value):
        self.d["metrics"][key] = value
        self.flush()

    def point(self, series, x, y):
        self.d["series"].setdefault(series, []).append([x, y])
        self.flush()

    def log(self, msg):
        print(msg, flush=True)
        self.d["log"] = (self.d["log"] + [f"{time.strftime('%H:%M:%S')}  {msg}"])[-12:]
        self.flush(force=True)

    def finish(self, state="done"):
        self.d["state"] = state
        self.flush(force=True)

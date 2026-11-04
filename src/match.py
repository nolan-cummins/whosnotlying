"""
Per-player topic matching. The admin picks one mode (settings["match_mode"]):
  tags       overlap between a player's chosen tags and a topic's tags
  expertise  cosine similarity between the player's free-text expertise and the topic,
             both embedded by a local Ollama model (vectors cached in DATA_DIR/embeddings.json)
Scores only weight the deal: deal() adds Gumbel noise and assigns greedily, so the
best-aligned player usually wins a contested topic, and nobody is ever locked to their field.
If Ollama is unreachable, expertise matching quietly degrades to random.
"""
import hashlib
import json
import math
import os
import random
import threading
import urllib.request
from typing import Any, Dict, List, Optional

from src import accounts

OLLAMA_URL = os.environ.get("OLLAMA_URL", "").rstrip("/")  # empty: matching by expertise and résumé parsing are off
MODEL = os.environ.get("EMBED_MODEL", "qwen3-embedding:0.6b")
BETA = {"tags": 1.5, "expertise": 1.0}  # match strength vs. the Gumbel noise (scale 1)

_lock = threading.RLock()
_vecs: Dict[str, List[float]] = {}
_cos: Dict[str, Dict[str, float]] = {}  # player text key -> topic key -> cosine
_loaded = False
_status = {"state": "idle", "error": ""}  # idle | working | ready | offline
_worker: Optional[threading.Thread] = None
_draining = [False]  # True while the worker is still picking up _pending (list so tests can reset it)


def _key(text: str) -> str:
    return hashlib.sha1((MODEL + "\n" + text).encode("utf-8")).hexdigest()


def _cache_file() -> str:
    return os.path.join(accounts.DATA_DIR, "embeddings.json")


def _load():
    global _loaded
    with _lock:
        if _loaded:
            return
        _loaded = True
        try:
            with open(_cache_file(), "r", encoding="utf-8") as f:
                _vecs.update(json.load(f))
        except Exception:
            pass


def _save():
    with _lock:
        os.makedirs(accounts.DATA_DIR, exist_ok=True)
        tmp = _cache_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_vecs, f, separators=(",", ":"))
        os.replace(tmp, _cache_file())


def embed(texts: List[str], timeout: float = 30) -> List[List[float]]:
    """Unit-length embeddings from Ollama. Raises on any failure."""
    req = urllib.request.Request(f"{OLLAMA_URL}/api/embed", data=json.dumps({"model": MODEL, "input": texts}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        vecs = json.load(r)["embeddings"]
    out = []
    for v in vecs:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([round(x / n, 5) for x in v])
    return out


def topic_text(t: Dict[str, Any]) -> str:
    return t.get("summary") or " ".join([t.get("topic", ""), t.get("category", ""), t.get("true_statement", ""),
                                        (t.get("true_description") or "").replace("•", "")])


def query_text(expertise: str) -> str:
    """Player side of the match; Qwen3 embeddings retrieve better with a task instruction on the query."""
    e = (expertise or "").strip()
    return e and ("Instruct: Given a description of a person's expertise and interests, "
                  "retrieve trivia topics they could confidently talk about\nQuery: " + e)


def tag_text(tag: str) -> str:
    """Tags are embedded as short phrases, so 'army' lands near 'Military History' and 'War'."""
    return "Topic: " + tag


def _tag_scores(mine: List[str], topics: List[Dict[str, Any]]) -> Optional[List[float]]:
    """Mean over a topic's tags of the best cosine to any of the player's tags; None if not embedded yet."""
    _load()
    pv = [_vecs.get(_key(tag_text(x))) for x in mine]
    pv = [v for v in pv if v]
    if not pv:
        return None
    memo = _cos.setdefault("tags:" + "|".join(sorted(mine)), {})  # one pass per distinct tag (~50), not per topic
    out = []
    for t in topics:
        best = []
        for tag in t.get("tags") or []:
            if tag not in memo:
                tv = _vecs.get(_key(tag_text(tag)))
                memo[tag] = max(sum(a * b for a, b in zip(tv, v)) for v in pv) if tv else None
            if memo[tag] is not None:
                best.append(memo[tag])
        out.append(sum(best) / len(best) if best else None)
    return out


def _zscore(vals: List[Optional[float]]) -> Optional[List[float]]:
    known = [c for c in vals if c is not None]
    if len(known) < 2:
        return None
    mean = sum(known) / len(known)
    sd = math.sqrt(sum((c - mean) ** 2 for c in known) / len(known)) or 1.0
    return [0.0 if c is None else (c - mean) / sd for c in vals]  # same strength whatever the model's cosine baseline


def status() -> Dict[str, Any]:
    with _lock:
        return dict(_status, model=MODEL, cached=len(_vecs))


def warm(texts: List[str]):
    """Embed any texts not cached yet, in the background. Safe to call often."""
    global _worker
    _load()
    with _lock:
        missing = list(dict.fromkeys(x for x in texts if x and _key(x) not in _vecs))
        if not missing:
            if _status["state"] in ("idle", "working"):
                _status["state"] = "ready"
            return
        if _draining[0]:
            _pending.extend(missing)  # the running worker picks these up when its current list is done
            return
        _status["state"] = "working"
        _draining[0] = True

        def run():
            todo = missing
            try:
                while todo:
                    for i in range(0, len(todo), 32):
                        batch = todo[i:i + 32]
                        for text, v in zip(batch, embed(batch, timeout=120)):
                            with _lock:
                                _vecs[_key(text)] = v
                    with _lock:  # stop draining only while holding the lock, so nothing queued is dropped
                        todo = [x for x in dict.fromkeys(_pending) if _key(x) not in _vecs]
                        _pending.clear()
                        _draining[0] = bool(todo)
                _save()
                with _lock:
                    _status.update(state="ready", error="")
            except Exception as e:
                with _lock:
                    _draining[0] = False
                    _status.update(state="offline", error=str(e)[:200])
        _worker = threading.Thread(target=run, daemon=True)
        _worker.start()


def scores(player: Dict[str, Any], topics: List[Dict[str, Any]], mode: str) -> Optional[List[float]]:
    """One score per topic (higher = better fit), or None when this player has nothing to match on."""
    if mode == "tags":
        mine = player.get("tags") or []
        if not mine:
            return None
        sem = _tag_scores(mine, topics)
        if sem is not None:
            return _zscore(sem)
        low = {x.lower() for x in mine}  # Ollama offline / not embedded yet: exact overlap
        return [sum(x.lower() in low for x in t.get("tags") or []) / max(1, len(t.get("tags") or [])) for t in topics]
    if mode == "expertise":
        _load()
        pk = _key(query_text(player.get("expertise")))
        pv = _vecs.get(pk)
        if not pv:
            return None
        memo = _cos.setdefault(pk, {})  # pure-Python dot products: compute each pair once
        cos = []
        for t in topics:
            tk = _key(topic_text(t))
            if tk not in memo and tk in _vecs:
                memo[tk] = sum(a * b for a, b in zip(pv, _vecs[tk]))
            cos.append(memo.get(tk))
        return _zscore(cos)
    return None


def deal(players: List[Dict[str, Any]], topics: List[Dict[str, Any]], mode: str, rng=random) -> Dict[str, Dict[str, Any]]:
    """Give each player a distinct topic. Weighted by match score; never two topics from one paper (group)."""
    beta = BETA.get(mode, 0.0)
    pairs = []
    for p in players:
        s = scores(p, topics, mode) if beta else None
        for i in range(len(topics)):
            pairs.append(((beta * s[i] if s else 0.0) - math.log(-math.log(rng.random() or 1e-12)), p["id"], i))
    pairs.sort(reverse=True)
    # ponytail: greedy over Gumbel-perturbed scores, not an optimal assignment; fine at party sizes.
    out, used, groups = {}, set(), set()
    for _, pid, i in pairs:
        t = topics[i]
        if pid in out or i in used or (t.get("group") and t["group"] in groups):
            continue
        out[pid] = t
        used.add(i)
        if t.get("group"):
            groups.add(t["group"])
        if len(out) == len(players):
            break
    return out


def percent(player: Dict[str, Any], topic: Dict[str, Any], pool: List[Dict[str, Any]], mode: str) -> Optional[int]:
    """How well a dealt topic fits this player: the share of the pool (0-100) it beats. None if unscorable."""
    ids = [t["id"] for t in pool]
    if topic["id"] not in ids:
        return None
    s = scores(player, pool, mode)
    if not s or len(s) < 2:
        return None
    mine = s[ids.index(topic["id"])]
    return round(100 * sum(x < mine for x in s) / (len(s) - 1))


_pending: List[str] = []
_rank_memo: Dict[str, List[str]] = {}


def _ensure(texts: List[str], timeout: float = 8) -> bool:
    """Embed missing texts right now (small sets only, e.g. ~50 tags); False if Ollama is unreachable."""
    _load()
    with _lock:
        missing = [x for x in dict.fromkeys(texts) if x and _key(x) not in _vecs]
    if not missing:
        return True
    try:
        vecs = embed(missing, timeout=timeout)
    except Exception:
        return False
    with _lock:
        for text, v in zip(missing, vecs):
            _vecs[_key(text)] = v
    _save()
    return True


def nearest_tag(tag: str, options: List[str], threshold: float = 0.78) -> Optional[str]:
    """The existing tag closest in meaning to `tag`, if it's close enough; exact (case-insensitive) match wins."""
    exact = {o.lower(): o for o in options}.get(tag.lower())
    if exact or not options or not _ensure([tag_text(tag)] + [tag_text(o) for o in options], timeout=20):
        return exact
    tv = _vecs[_key(tag_text(tag))]
    best = max(options, key=lambda o: sum(a * b for a, b in zip(tv, _vecs[_key(tag_text(o))])))
    cos = sum(a * b for a, b in zip(tv, _vecs[_key(tag_text(best))]))
    return best if cos >= threshold else None


def tag_relevance(expertise: str, tags: List[str]) -> Optional[List[float]]:
    """Cosine of each tag to a player's expertise text; None if Ollama is unreachable."""
    q = query_text(expertise)
    if not q or not _ensure([q] + [tag_text(t) for t in tags], timeout=20):
        return None
    qv = _vecs[_key(q)]
    return [sum(a * b for a, b in zip(qv, _vecs[_key(tag_text(t))])) for t in tags]


def rank_tags(mine: List[str], tags: List[str], expertise: str = "") -> List[str]:
    """Phone "Relevance" order: your tags A-Z, then the rest by closeness in meaning to your tags and expertise
    (A-Z when there's nothing to compare with, or until the embeddings are ready: state polls never block on Ollama)."""
    have = {t.lower() for t in mine}
    rest = sorted((t for t in tags if t.lower() not in have), key=str.lower)
    anchors = [tag_text(t) for t in mine] + ([query_text(expertise)] if (expertise or "").strip() else [])
    key = "\n".join(anchors) + "\0" + "\n".join(rest)
    if key in _rank_memo:
        return _rank_memo[key]
    texts = anchors + [tag_text(t) for t in rest]
    if anchors and not all(_key(x) in _vecs for x in texts):
        warm(texts)
    elif anchors:
        av = [_vecs[_key(a)] for a in anchors]
        score = {t: max(sum(x * y for x, y in zip(_vecs[_key(tag_text(t))], v)) for v in av) for t in rest}
        rest.sort(key=lambda t: -score[t])
        if len(_rank_memo) > 256:
            _rank_memo.clear()
        _rank_memo[key] = sorted(mine, key=str.lower) + rest
        return _rank_memo[key]
    return sorted(mine, key=str.lower) + rest

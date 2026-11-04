"""
Topic packs: every *.json file in PACKS_DIR is a read-only pack, picked up automatically.

v2 schema: {"id", "name", "version": 2, "topics": [{id, category, topic,
  "truth": {"text", "facts": [..]}, "lies": [{"text", "facts": [..]}]}]}
v1 topics (true_statement / true_description / false_statements) are still accepted.
Loaded topics carry both shapes, so game code can read true_statement / false_statements.
The set of enabled packs lives in _settings.json; play history lives in src.accounts.
"""
import json
import os
import random
import threading
from typing import Any, Dict, List, Optional

PACKS_DIR = os.environ.get("PACKS_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "packs"))
_SETTINGS = "_settings.json"  # leading underscore: never loaded as a pack

_lock = threading.RLock()
_cache: Dict[str, Any] = {}  # path -> (mtime_ns, pack)


def _write(path: str, data: Any):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _bullets(desc: Optional[str]) -> List[str]:
    return [ln.strip().lstrip("•").strip() for ln in (desc or "").splitlines() if ln.strip()]


def normalize(t: Dict[str, Any]) -> Dict[str, Any]:
    """Return a topic with both the v2 (truth/lies) and the v1 (true_statement/...) fields."""
    truth = t.get("truth") or {"text": t.get("true_statement") or "", "facts": _bullets(t.get("true_description"))}
    lies = t.get("lies")
    if not lies:
        old = t.get("false_statements") or ([t["false_statement"]] if t.get("false_statement") else [])
        lies = [{"text": s, "facts": []} for s in old]
    return {"id": t["id"], "category": t.get("category", ""), "topic": t.get("topic", ""),
            "truth": truth, "lies": lies,
            "true_statement": truth["text"],
            "true_description": "\n".join("• " + f for f in truth.get("facts", [])),
            "false_statements": [l["text"] for l in lies],
            # optional: matching tags; PhD pack also has group (paper DOI), summary (for embeddings), source
            "tags": [str(x) for x in t.get("tags") or []],
            "group": t.get("group"), "summary": t.get("summary"), "source": t.get("source")}


def _packs() -> Dict[str, Dict[str, Any]]:
    """id -> pack, rescanning the directory (cheap: files reload only when mtime changes)."""
    with _lock:
        seen = {}
        names = sorted(n for n in os.listdir(PACKS_DIR) if n.endswith(".json") and not n.startswith("_")) if os.path.isdir(PACKS_DIR) else []
        for n in names:
            path = os.path.join(PACKS_DIR, n)
            try:
                mt = os.stat(path).st_mtime_ns
                if path not in _cache or _cache[path][0] != mt:
                    with open(path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    pid = str(raw.get("id") or n[:-5])
                    pack = {"id": pid, "name": raw.get("name", pid), "_raw": raw,
                            "topics": [normalize(t) for t in raw.get("topics", [])]}
                    _cache[path] = (mt, pack)
                pack = _cache[path][1]
                seen[pack["id"]] = pack
            except Exception:
                continue  # unreadable / malformed pack: skip it
        for p in [p for p in _cache if os.path.basename(p) not in names]:
            del _cache[p]
        return seen


def _selected_ids(packs) -> List[str]:
    try:
        with open(os.path.join(PACKS_DIR, _SETTINGS), "r", encoding="utf-8") as f:
            sel = [i for i in json.load(f).get("selected", []) if i in packs]
    except Exception:
        sel = []
    # default / nothing valid selected: every pack except opt-in ones ("default_off", e.g. PhD Mode)
    return sel or [i for i, p in packs.items() if not p["_raw"].get("default_off")] or list(packs)


def library() -> List[Dict[str, Any]]:
    """Topics of the enabled packs; ids are namespaced 'pack:topic'."""
    with _lock:
        packs = _packs()
        out = []
        for pid in _selected_ids(packs):
            for t in packs[pid]["topics"]:
                out.append({**t, "id": f"{pid}:{t['id']}", "pack": pid})
        return out


def has_side(t: Dict[str, Any], need: Optional[str]) -> bool:
    """Can this topic serve a truth teller ("truth") or a liar ("lie")? Packs may hold one-sided items."""
    return need is None or bool(t["true_statement"] if need == "truth" else t["false_statements"])


def all_tags() -> List[str]:
    """Every tag used by the enabled packs: the list players pick their interests from."""
    return sorted({x for t in library() for x in t["tags"]})


def statement_keys(t: Dict[str, Any]) -> List[str]:
    """History keys of every statement a (namespaced) topic holds: its truth and each lie."""
    return ([t["id"] + ":t"] if t["true_statement"] else []) + [f"{t['id']}:f{i}" for i in range(len(t["false_statements"]))]


def pack_summaries(used_keys=frozenset()) -> List[Dict[str, Any]]:
    """`used_keys`: statement keys in the history. Counts are statements (truths + lies), not topics."""
    with _lock:
        packs = _packs()
        sel = set(_selected_ids(packs))
        out = []
        for pid, p in packs.items():
            keys = [k for t in p["topics"] for k in statement_keys({**t, "id": f"{pid}:{t['id']}"})]
            out.append({"id": pid, "name": p["name"], "total": len(keys),
                        "used": sum(1 for k in keys if k in used_keys), "selected": pid in sel})
        return out


def set_selected(ids: List[str]) -> bool:
    with _lock:
        packs = _packs()
        ids = [i for i in ids if i in packs]
        if not ids:
            return False
        _write(os.path.join(PACKS_DIR, _SETTINGS), {"selected": ids})
        return True


def statement_key(topic: Dict[str, Any], statement: Optional[str]) -> Optional[str]:
    """'pack:topic:t' for the truth, 'pack:topic:f<N>' for lie N, None if the text isn't in the topic."""
    if not statement:
        return None
    if statement == topic.get("true_statement"):
        return topic["id"] + ":t"
    for i, s in enumerate(topic.get("false_statements", [])):
        if s == statement:
            return f"{topic['id']}:f{i}"
    return None


def lie_info(topic: Dict[str, Any], statement: Optional[str]) -> Dict[str, Any]:
    return next((l for l in topic.get("lies", []) if l["text"] == statement), {})


def lie_facts(topic: Dict[str, Any], statement: Optional[str]) -> List[str]:
    return lie_info(topic, statement).get("facts", [])


def legacy_used_keys() -> List[str]:
    """One-time migration: v1 packs carried 'used'/'used_as' flags; return them as history keys.
    Read-only: the loader ignores those fields, and leaving the file untouched lets a newer
    seeded copy replace it (cp -u compares mtimes)."""
    keys = []
    with _lock:
        for pid, p in _packs().items():
            for t in p["_raw"].get("topics", []):
                if t.get("used"):
                    side = t.get("used_as")
                    keys.append(f"{pid}:{t['id']}:" + ("t" if side == "true" else "f0" if side == "false" else "?"))
    return keys


def get_random_false_statement(topic_dict: Dict[str, Any]) -> str:
    stmts = topic_dict.get("false_statements")
    if stmts and isinstance(stmts, list):
        return random.choice(stmts)
    return topic_dict.get("false_statement", "")

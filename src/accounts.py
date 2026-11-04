"""
Player accounts and topic history, kept outside the pack files (packs are read-only content).

DATA_DIR/accounts.json  {name_lower: {id, name, pw_hash, salt, score_total, rounds, created}}
DATA_DIR/history.json   {"global": [key], "users": {account_id: [key]}, "settings": {...}}

A statement key is "pack:topic_id:t" (the truth) or "pack:topic_id:f<N>" (lie N), so text edits
don't break the record. Seeing either side of a topic spoils the whole topic, so blocking
works on the "pack:topic_id" prefix. Legacy marks without a known side use the suffix "?".
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Set

DATA_DIR = os.environ.get("DATA_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DEFAULT_SETTINGS = {"use_global": True, "use_user": True, "lying_facts": False, "hide_facts": False, "fair_roles": False, "match_mode": "off", "idle_minutes": 60}
CHOICES = {"match_mode": ("off", "tags", "expertise")}  # non-bool settings: allowed values
RANGES = {"idle_minutes": (5, 1440)}  # integer settings: inclusive bounds

_lock = threading.RLock()


def _path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def _read(name: str, default: Any) -> Any:
    try:
        with open(_path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(name: str, data: Any):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, _path(name))


def add_review(entry: Dict[str, Any]):
    """Append one statement review to reviews.jsonl (feedback on generated content; read back when improving packs)."""
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_path("reviews.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def reviews() -> List[Dict[str, Any]]:
    """All reviews, newest first."""
    with _lock:
        try:
            with open(_path("reviews.jsonl"), encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []
    return rows[::-1]


def topic_of(key: str) -> str:
    return key.rsplit(":", 1)[0]


# ---------- passwords ----------

def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
    return h, salt


def check_password(password: str, pw_hash: Optional[str], salt: Optional[str]) -> bool:
    if not pw_hash or not salt:
        return False
    return hmac.compare_digest(hash_password(password or "", salt)[0], pw_hash)


# ---------- accounts ----------

def get_account(name: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return _read("accounts.json", {}).get(name.strip().lower())


def account_by_id(acct_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return next((a for a in _read("accounts.json", {}).values() if a["id"] == acct_id), None)


def create_account(name: str, password: str) -> Dict[str, Any]:
    with _lock:
        accts = _read("accounts.json", {})
        h, salt = hash_password(password)
        acct = {"id": "a_" + secrets.token_hex(6), "name": name.strip(), "pw_hash": h, "salt": salt,
                "score_total": 0, "rounds": 0, "created": int(time.time())}
        accts[name.strip().lower()] = acct
        _write("accounts.json", accts)
        return acct


def set_profile(acct_id: str, tags: List[str], expertise: str):
    """Interests follow a permanent account into every future game."""
    with _lock:
        accts = _read("accounts.json", {})
        for a in accts.values():
            if a["id"] == acct_id:
                a["tags"], a["expertise"] = tags, expertise
                _write("accounts.json", accts)
                return


def _update(acct_id: str, **fields) -> bool:
    with _lock:
        accts = _read("accounts.json", {})
        for a in accts.values():
            if a["id"] == acct_id:
                a.update(fields)
                _write("accounts.json", accts)
                return True
        return False


def request_reset(name: str) -> bool:
    """'Forgot password' on the join page: flags the account for the admin. No secret is involved."""
    acct = get_account(name or "")
    return bool(acct) and _update(acct["id"], reset_requested=int(time.time()))


def reset_password(acct_id: str) -> Optional[str]:
    """Admin hands out a one-time password; the player must replace it at their next login."""
    temp = "-".join(secrets.token_hex(2) for _ in range(3))  # e.g. 3fa1-09bc-7d2e: easy to read out loud
    h, salt = hash_password(temp)
    return temp if _update(acct_id, pw_hash=h, salt=salt, must_change=True, reset_requested=None) else None


def set_password(acct_id: str, password: str) -> bool:
    h, salt = hash_password(password)
    return _update(acct_id, pw_hash=h, salt=salt, must_change=False)


def record_game(account_ids: Iterable[str], winner_ids: Iterable[str]):
    """A finished game: everyone listed played it, the top scorers (ties included) won it."""
    played, won = set(account_ids), set(winner_ids)
    with _lock:
        accts = _read("accounts.json", {})
        for a in accts.values():
            if a["id"] in played:
                a["games"] = a.get("games", 0) + 1
                a["wins"] = a.get("wins", 0) + (a["id"] in won)
        _write("accounts.json", accts)


def leaderboard() -> List[Dict[str, Any]]:
    """Public: saved accounts ranked by games won, then total points."""
    with _lock:
        rows = [{"name": a["name"], "points": a.get("score_total", 0), "wins": a.get("wins", 0),
                 "games": a.get("games", 0), "rounds": a.get("rounds", 0)} for a in _read("accounts.json", {}).values()]
    return sorted(rows, key=lambda r: (-r["wins"], -r["points"], r["name"].lower()))


def list_accounts() -> List[Dict[str, Any]]:
    with _lock:
        users = _read("history.json", {}).get("users", {})
        return [{"id": a["id"], "name": a["name"], "score_total": a.get("score_total", 0),
                 "rounds": a.get("rounds", 0), "wins": a.get("wins", 0), "games": a.get("games", 0),
                 "reset_requested": bool(a.get("reset_requested")), "must_change": bool(a.get("must_change")),
                 "seen": len({topic_of(k) for k in users.get(a["id"], [])})}
                for a in _read("accounts.json", {}).values()]


def delete_account(acct_id: str) -> bool:
    with _lock:
        accts = _read("accounts.json", {})
        keep = {k: a for k, a in accts.items() if a["id"] != acct_id}
        if len(keep) == len(accts):
            return False
        _write("accounts.json", keep)
        clear_user_history(acct_id)
        return True


def add_round_score(acct_id: str, pts: int):
    with _lock:
        accts = _read("accounts.json", {})
        for a in accts.values():
            if a["id"] == acct_id:
                a["score_total"] = a.get("score_total", 0) + pts
                a["rounds"] = a.get("rounds", 0) + 1
                _write("accounts.json", accts)
                return


# ---------- history ----------

def _history() -> Dict[str, Any]:
    h = _read("history.json", {})
    h.setdefault("global", [])
    h.setdefault("users", {})
    h["settings"] = {**DEFAULT_SETTINGS, **h.get("settings", {})}
    return h


def has_history_file() -> bool:
    return os.path.exists(_path("history.json"))


def init_history(legacy_keys: List[str]):
    """Create history.json once, seeded with legacy 'used' marks migrated out of the packs."""
    with _lock:
        if not has_history_file():
            h = _history()
            h["global"] = list(dict.fromkeys(legacy_keys))
            _write("history.json", h)


def settings() -> Dict[str, Any]:
    with _lock:
        return _history()["settings"]


def set_setting(name: str, value: Any) -> bool:
    if name not in DEFAULT_SETTINGS:
        return False
    with _lock:
        h = _history()
        if name in CHOICES:
            if value not in CHOICES[name]:
                return False
            h["settings"][name] = value
        elif name in RANGES:
            try:
                v = int(value)
            except (TypeError, ValueError):
                return False
            if not RANGES[name][0] <= v <= RANGES[name][1]:
                return False
            h["settings"][name] = v
        else:
            h["settings"][name] = bool(value)
        _write("history.json", h)
        return True


def record(keys: Iterable[str], account_ids: Iterable[str]):
    """Append statement keys to the global history and to each listed account's history."""
    keys = [k for k in keys if k]
    if not keys:
        return
    with _lock:
        h = _history()
        targets = [h["global"]] + [h["users"].setdefault(a, []) for a in account_ids]
        changed = False
        for lst in targets:
            have = set(lst)
            for k in keys:
                if k not in have:
                    lst.append(k)
                    have.add(k)
                    changed = True
        if changed:
            _write("history.json", h)


def global_keys() -> List[str]:
    with _lock:
        return list(_history()["global"])


def blocked_topics(account_ids: Iterable[str]) -> Set[str]:
    """Topic ids ('pack:topic') to avoid, honoring the global / per-player toggles."""
    with _lock:
        h = _history()
        keys = list(h["global"]) if h["settings"]["use_global"] else []
        if h["settings"]["use_user"]:
            for a in account_ids:
                keys += h["users"].get(a, [])
        return {topic_of(k) for k in keys}


def reset_global():
    with _lock:
        h = _history()
        h["global"] = []
        _write("history.json", h)


def clear_user_history(acct_id: str):
    with _lock:
        h = _history()
        if h["users"].pop(acct_id, None) is not None:
            _write("history.json", h)


# ---------- "View Used" archive (statements per round, survives restarts) ----------

ARCHIVE_MAX = 1000


def load_archive() -> List[Dict[str, Any]]:
    with _lock:
        return _read("archive.json", [])


def save_archive(entries: List[Dict[str, Any]]):
    with _lock:
        _write("archive.json", entries[-ARCHIVE_MAX:])

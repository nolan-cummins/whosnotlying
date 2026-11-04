"""
Game logic and state management for 'One of These People Is Not Lying'.

Features:
- Dedicated Guesser assigned at round start who has no clues.
- Unique topics per suspect; only the Truth Teller has true statement + detailed description.
- Role swapping in the Admin Console directly sets specific roles for specific players without randomizing.
- Questioning phase is untimed.
- Only the Guesser can cast a vote during the accusation phase.
- Persistent players and persistent used topics history.
"""

import json
import math
import os
import random
import threading
import time
from typing import Dict, List, Optional, Any, Union, Tuple

import secrets

from src import accounts, match, packs
from src.packs import library, get_random_false_statement


PLAYERS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "players.json"))


NEED_NEW_PASSWORD = "That was a temporary password. Choose a new one (4+ characters)."


def find_topic_data(topic_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not topic_name:
        return None
    for t in library():
        if t["topic"].lower() == topic_name.lower():
            return t
    return None


class GameManager:
    def __init__(self, seed_samples: bool = False, players_file: Optional[str] = None, empty_lobby: Optional[bool] = None):
        self.players_file = players_file if players_file is not None else PLAYERS_FILE
        self.phase = "lobby"  # "lobby", "setup", "questioning", "voting", "reveal"
        self.round_number = 1
        self.players: List[Dict[str, Any]] = []
        self.guesser_ids: List[str] = []
        self.voting_guesser_id: Optional[str] = None
        self.truth_teller_ids: List[str] = []
        self.target_guesser_count: int = 1
        self.target_truth_teller_count: int = 1
        self.role_mode = "custom"  # "one_liar" | "custom" | "one_truth"
        self.ready_ids: set = set()
        self._ready_lock = threading.RLock()  # two last "ready" taps at once must advance only once
        self.logs: List[Dict[str, Any]] = []
        if not accounts.has_history_file():
            accounts.init_history(packs.legacy_used_keys())
        self.used_topic_ids: List[str] = []  # topics dealt this session (until reset_game)
        self.used_statements: List[Dict[str, Any]] = accounts.load_archive()
        self.game_id = int(time.time() * 1000)  # tags archive entries; round numbers restart each game
        self.last_round_results: Optional[Dict[str, Any]] = None
        self.last_activity = time.time()  # any player/admin action; an hour of silence ends the game

        # The default behavior is to start without any player in the lobby.
        # If the testbench is launched, the testbench simulates players joining,
        # instead of having players hard-coded as default in the engine.
        if seed_samples:
            self._seed_sample_players()
        else:
            self.players = []
            self.guesser_ids = []
            self.voting_guesser_id = None
            self.truth_teller_ids = []
            self._save_players()

        self.log("Server initialized. Welcome to 'One of These People Is Not Lying'!", level="INFO")
        if self.players:
            if len(self.players) >= 2 and (not self.guesser_ids or not self.truth_teller_ids or set(self.guesser_ids).intersection(set(self.truth_teller_ids))):
                self.assign_round_roles()
            elif len(self.players) >= 2:
                self._ensure_all_suspects_have_content()
            self._record_used_statements()

    @property
    def guesser_id(self) -> Optional[str]:
        return self.voting_guesser_id

    @guesser_id.setter
    def guesser_id(self, val: Optional[str]):
        self.voting_guesser_id = val
        if val is not None:
            if val not in self.guesser_ids:
                self.guesser_ids = [val] + [gid for gid in self.guesser_ids if gid != val]
        else:
            self.guesser_ids = []

    @property
    def truth_teller_id(self) -> Optional[str]:
        return self.truth_teller_ids[0] if self.truth_teller_ids else None

    @truth_teller_id.setter
    def truth_teller_id(self, val: Optional[str]):
        if val is not None:
            if val not in self.truth_teller_ids:
                self.truth_teller_ids = [val] + [tid for tid in self.truth_teller_ids if tid != val]
        else:
            self.truth_teller_ids = []

    @property
    def voting_guesser_name(self) -> str:
        p = next((p for p in self.players if p["id"] == self.voting_guesser_id), None)
        return p["name"] if p else "None"

    @property
    def guesser_name(self) -> str:
        return self.voting_guesser_name

    @property
    def truth_teller_name(self) -> str:
        p = next((p for p in self.players if p["id"] == self.truth_teller_id), None)
        return p["name"] if p else "None"

    def _blocked(self) -> set:
        """Topics not to deal: this session's, plus the global / present accounts' history."""
        accts = [p["account_id"] for p in self.players if p.get("account_id")]
        return set(self.used_topic_ids) | accounts.blocked_topics(accts)

    def _record_history(self):
        """Statements are live (questioning onwards): everyone present has now heard them."""
        keys = []
        for p in self.players:
            t = find_topic_data(p.get("topic"))
            if t and p.get("role") in ("truth_teller", "liar"):
                keys.append(packs.statement_key(t, p.get("statement")) or t["id"] + ":?")
        try:
            accounts.record(keys, [p["account_id"] for p in self.players if p.get("account_id")])
        except OSError as e:
            self.log(f"Warning: could not save topic history: {e}", level="WARN")

    def _seed_sample_players(self):
        """Seeds sample players only when explicitly requested (e.g. for unit test fixtures)."""
        self.players = [
            {"id": "p1", "name": "Alice", "score": 0, "role": "guesser", "is_voting_guesser": True, "topic": None, "statement": None, "detailed_description": None, "voted_for": None},
            {"id": "p2", "name": "Bob", "score": 0, "role": "liar", "is_voting_guesser": False, "topic": None, "statement": None, "detailed_description": None, "voted_for": None},
            {"id": "p3", "name": "Charlie", "score": 0, "role": "truth_teller", "is_voting_guesser": False, "topic": None, "statement": None, "detailed_description": None, "voted_for": None},
            {"id": "p4", "name": "Diana", "score": 0, "role": "liar", "is_voting_guesser": False, "topic": None, "statement": None, "detailed_description": None, "voted_for": None},
        ]
        self.guesser_ids = ["p1"]
        self.voting_guesser_id = "p1"
        self.truth_teller_ids = ["p3"]
        self.target_guesser_count = 1
        self.target_truth_teller_count = 1
        self._save_players()
        return True

    def _load_players(self):
        DEFAULT_PLAYER_NAMES = {
            "alice", "bob", "charlie", "diana",
            "player 1", "player 2", "player 3", "player 4", "player 5", "player 6"
        }
        if self.players_file != ":memory:" and os.path.exists(self.players_file):
            try:
                with open(self.players_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        cleaned = [p for p in data if p.get("name", "").strip().lower() not in DEFAULT_PLAYER_NAMES]
                        if cleaned:
                            self.players = cleaned
                            all_g = [p["id"] for p in self.players if p.get("role") == "guesser"]
                            all_tt = [p["id"] for p in self.players if p.get("role") == "truth_teller"]
                            voter = next((p["id"] for p in self.players if p.get("role") == "guesser" and p.get("is_voting_guesser")), None)
                            self.guesser_ids = all_g
                            self.voting_guesser_id = voter or (all_g[0] if all_g else None)
                            self.truth_teller_ids = all_tt
                            return True
            except Exception:
                pass
        self.players = []
        self.guesser_ids = []
        self.voting_guesser_id = None
        self.truth_teller_ids = []
        self._save_players()
        return False

    def _save_players(self):
        if self.players_file == ":memory:":
            return
        try:
            to_save = []
            for p in self.players:
                to_save.append({
                    "id": p["id"],
                    "name": p["name"],
                    "score": p.get("score", 0),
                    "role": p.get("role", "liar"),
                    "is_voting_guesser": (p["id"] == self.voting_guesser_id),
                    "topic": p.get("topic"),
                    "category": p.get("category"),
                    "statement": p.get("statement"),
                    "detailed_description": p.get("detailed_description"),
                    "voted_for": p.get("voted_for"),
                    "tags": p.get("tags", []),
                    "expertise": p.get("expertise", ""),
                })
            with open(self.players_file, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2)
        except Exception as e:
            self.log(f"Warning: could not save players: {e}", level="WARN")

    def _get_unused_topic(self, exclude_topics: Optional[List[str]] = None, need: Optional[str] = None) -> Dict[str, Any]:
        """A random unplayed topic; need="truth"/"lie" keeps to topics that have that side."""
        exclude = set(exclude_topics or [])
        blocked = self._blocked()
        lib = [t for t in library() if packs.has_side(t, need)] or library()
        groups = {t["group"] for t in library() if t["topic"] in exclude and t.get("group")}  # one paper per round
        available = [t for t in lib if t["id"] not in blocked and t["topic"] not in exclude and t.get("group") not in groups]
        if not available:
            self.log("Topic pool exhausted for this lobby: reusing played topics.", level="WARN")
            available = [t for t in lib if t["topic"] not in exclude]
        if not available:
            available = lib
        chosen = random.choice(available)
        if chosen["id"] not in self.used_topic_ids:
            self.used_topic_ids.append(chosen["id"])
        return chosen

    def _give(self, p: Dict[str, Any], role: str, taken: Optional[set] = None):
        """Fill a suspect's topic + statement for their role, keeping their current topic if it has that side.
        Packs may hold truth-only and lie-only items, so every role change goes through here."""
        need = "truth" if role == "truth_teller" else "lie"
        if taken is None:
            taken = {x["topic"] for x in self.players if x is not p and x.get("topic")}
        t = find_topic_data(p.get("topic"))
        if not t or not packs.has_side(t, need) or p.get("topic") in taken:
            t = self._get_unused_topic(exclude_topics=list(taken), need=need)
        p["topic"], p["category"] = t["topic"], t["category"]
        if t["id"] not in self.used_topic_ids:
            self.used_topic_ids.append(t["id"])
        if need == "truth":
            p["statement"], p["detailed_description"] = t["true_statement"], t["true_description"]
        else:
            if p.get("statement") not in t["false_statements"]:
                p["statement"] = get_random_false_statement(t)
            p["detailed_description"] = None

    def set_packs(self, pack_ids: List[str]) -> bool:
        if not packs.set_selected(pack_ids):
            return False
        self.log(f"Topic packs enabled: {', '.join(pack_ids)}", level="ACTION")
        return True

    def clear_topic_history(self):
        self.used_topic_ids = []
        self.used_statements = []
        accounts.save_archive([])
        accounts.reset_global()
        self.log("Global topic history cleared by Admin. All topics re-enabled!", level="ACTION")

    def _record_used_statements(self):
        if self.phase in ("questioning", "voting", "reveal"):
            self._record_history()
        # Refresh current round's statements to match active players
        self.used_statements = [s for s in self.used_statements
                                if (s.get("game"), s.get("round")) != (self.game_id, self.round_number)]
        for p in self.players:
            stmt = p.get("statement")
            topic = p.get("topic")
            if not stmt or not topic:
                continue
            role = p.get("role")
            if role == "truth_teller":
                self.used_statements.append({
                    "type": "true",
                    "game": self.game_id,
                    "round": self.round_number,
                    "player_id": p["id"],
                    "player_name": p["name"],
                    "topic": topic,
                    "category": p.get("category"),
                    "statement": stmt,
                    "detailed_description": p.get("detailed_description")
                })
            elif role == "liar":
                self.used_statements.append({
                    "type": "false",
                    "game": self.game_id,
                    "round": self.round_number,
                    "player_id": p["id"],
                    "player_name": p["name"],
                    "topic": topic,
                    "category": p.get("category"),
                    "statement": stmt
                })
        try:
            accounts.save_archive(self.used_statements)
        except OSError as e:
            self.log(f"Warning: could not save the statements archive: {e}", level="WARN")

    def log(self, message: str, level: str = "INFO"):
        entry = {
            "timestamp": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.append(entry)
        if len(self.logs) > 250:
            self.logs.pop(0)

    def clear_logs(self):
        self.logs.clear()
        self.log("Server event log cleared by host.", level="INFO")

    def add_player(self, name: str, player_id: Optional[str] = None) -> Dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            clean_name = f"Player {len(self.players) + 1}"

        if player_id:
            existing = next((p for p in self.players if p["id"] == player_id), None)
            if existing:
                existing["name"] = clean_name
                self._ensure_all_suspects_have_content()
                self._save_players()
                self.log(f"Player reconnected: {clean_name} (ID: {player_id})", level="ACTION")
                return existing

        existing_by_name = next((p for p in self.players if p["name"].lower() == clean_name.lower()), None)
        if existing_by_name:
            if player_id:
                existing_by_name["id"] = player_id
            self._ensure_all_suspects_have_content()
            self._save_players()
            self.log(f"Player re-joined: {clean_name} (ID: {existing_by_name['id']})", level="ACTION")
            return existing_by_name

        pid = player_id or f"p_{int(time.time() * 1000) % 1000000}_{random.randint(10, 99)}"
        new_player = {
            "id": pid,
            "name": clean_name,
            "score": 0,
            "role": "liar",
            "topic": None,
            "category": None,
            "statement": None,
            "detailed_description": None,
            "voted_for": None
        }
        self.players.append(new_player)

        # Assign unique topic for new suspect
        self._give(new_player, "liar")

        if not self.guesser_ids or not self.truth_teller_ids:
            self.assign_round_roles()
        else:
            self._ensure_all_suspects_have_content()

        self._save_players()
        self.log(f"Player joined: {clean_name} (ID: {pid})", level="ACTION")
        return new_player

    def sync_player(self, player_id: str, name: str) -> Dict[str, Any]:
        return self.add_player(name=name, player_id=player_id)

    def _renew_password(self, acct: Dict[str, Any], password: str, new_password: str) -> Optional[str]:
        """After an admin reset the temporary password works once: the player must pick their own."""
        if not acct.get("must_change") or not accounts.check_password(password, acct["pw_hash"], acct["salt"]):
            return None
        if len(new_password or "") < 4:
            return NEED_NEW_PASSWORD
        accounts.set_password(acct["id"], new_password)
        self.log(f"Password changed after reset: {acct['name']}", level="ACTION")
        return None

    def join(self, name: str, password: str = "", permanent: bool = False, token: str = "",
             new_password: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Player self-service join / re-login. Returns (player, None) or (None, error)."""
        name = (name or "").strip()[:24]
        if not name:
            return None, "Enter a name."
        p = next((x for x in self.players if x["name"].lower() == name.lower()), None)
        if p:  # re-login to an in-game player
            acct = accounts.account_by_id(p["account_id"]) if p.get("account_id") else None
            ok = (token and p.get("token") and secrets.compare_digest(token, p["token"])) \
                or (acct and accounts.check_password(password, acct["pw_hash"], acct["salt"])) \
                or (p.get("pw_hash") and accounts.check_password(password, p["pw_hash"], p["salt"])) \
                or (not p.get("token") and not acct and not p.get("pw_hash"))  # admin-added, unclaimed
            if not ok:
                return None, "That name is taken. Enter its password to log back in." if (acct or p.get("pw_hash")) else "That name is already in the game."
            err = acct and self._renew_password(acct, password, new_password)
            if err:
                return None, err
            p["token"] = p.get("token") or secrets.token_urlsafe(18)
            self.log(f"Player logged back in: {p['name']}", level="ACTION")
            return p, None
        acct = accounts.get_account(name)
        if acct:
            if not accounts.check_password(password, acct["pw_hash"], acct["salt"]):
                return None, "A saved account uses that name. Wrong password."
            err = self._renew_password(acct, password, new_password)
            if err:
                return None, err
        elif permanent:
            if len(password or "") < 4:
                return None, "Permanent accounts need a password (4+ characters)."
            acct = accounts.create_account(name, password)
            self.log(f"Permanent account created: {acct['name']}", level="ACTION")
        p = self.add_player(acct["name"] if acct else name)
        p["token"] = secrets.token_urlsafe(18)
        if acct:
            p["account_id"] = acct["id"]
            p.setdefault("tags", acct.get("tags", []))
            p.setdefault("expertise", acct.get("expertise", ""))
            # Their history now applies: re-deal anything they've already seen.
            seen = accounts.blocked_topics([acct["id"]])
            t = find_topic_data(p.get("topic"))
            if t and t["id"] in seen and self.phase == "lobby":
                p["topic"] = None
                self._ensure_all_suspects_have_content()
        elif password:
            p["pw_hash"], p["salt"] = accounts.hash_password(password)
        return p, None

    def set_profile(self, player_id: str, tags: List[str], expertise: str) -> bool:
        """A player's interests: tags from the packs' vocabulary, plus free-text expertise for embeddings."""
        p = next((x for x in self.players if x["id"] == player_id), None)
        if not p:
            return False
        clean = []  # pack tags or the player's own; matching is by meaning, so any phrase works
        for t in tags or []:
            t = " ".join(str(t).split())[:32]
            if t and t.lower() not in {c.lower() for c in clean}:
                clean.append(t)
        p["tags"] = clean[:40]
        p["expertise"] = str(expertise or "").strip()[:600]
        if p.get("account_id"):
            accounts.set_profile(p["account_id"], p["tags"], p["expertise"])
        match.warm([match.query_text(p["expertise"])] + [match.tag_text(t) for t in p["tags"]])
        self._save_players()
        return True

    def player_for_token(self, player_id: str, token: str) -> Optional[Dict[str, Any]]:
        p = next((x for x in self.players if x["id"] == player_id), None)
        if p and token and p.get("token") and secrets.compare_digest(str(token), p["token"]):
            return p
        return None

    def remove_player(self, player_id: str) -> bool:
        player = next((p for p in self.players if p["id"] == player_id), None)
        if not player:
            return False
        self.players = [p for p in self.players if p["id"] != player_id]
        if player_id in self.guesser_ids:
            self.guesser_ids.remove(player_id)
        if self.voting_guesser_id == player_id:
            self.voting_guesser_id = self.guesser_ids[0] if self.guesser_ids else None
        if player_id in self.truth_teller_ids:
            self.truth_teller_ids.remove(player_id)
        self.ready_ids.discard(player_id)

        self.log(f"Player removed: {player['name']}", level="ACTION")
        if self.players:
            if not self.guesser_ids or not self.truth_teller_ids:
                self.assign_round_roles()
            else:
                self._ensure_all_suspects_have_content()
                self._save_players()
        else:
            self.guesser_ids = []
            self.voting_guesser_id = None
            self.truth_teller_ids = []
            self._save_players()
        self._advance_if_all_ready()
        return True

    def assign_round_roles(self, roles: bool = True, topics: bool = True):
        """
        Randomizes roles and unique topics for all players based on target_guesser_count
        and target_truth_teller_count:
        - Target guessers (no clues, 1 designated Lead Voter allowed to vote, other guessers deliberate).
        - Target truth tellers (each gets unique topic + true statement + detailed description).
        - All others are Liars (unique topic + false statement ONLY).
        """
        if not self.players:
            self.guesser_ids = []
            self.voting_guesser_id = None
            self.truth_teller_ids = []
            return

        total_players = len(self.players)
        if total_players >= 2:
            g_count = max(1, min(self.target_guesser_count, total_players - 1))
            tt_count = max(1, min(self._target_tt(total_players, g_count), total_players - g_count))
        else:
            g_count = 1
            tt_count = 0

        if not roles and self.guesser_ids and self.truth_teller_ids:
            g_count, tt_count = len(self.guesser_ids), len(self.truth_teller_ids)
        elif accounts.settings().get("fair_roles") and total_players >= 3:
            self.guesser_ids, self.truth_teller_ids = self._fair_deal(g_count, tt_count)
            self.voting_guesser_id = random.choice(self.guesser_ids)
        else:
            shuffled = list(self.players)
            random.shuffle(shuffled)
            self.guesser_ids = [p["id"] for p in shuffled[:g_count]]
            self.voting_guesser_id = self.guesser_ids[0] if self.guesser_ids else None
            self.truth_teller_ids = [p["id"] for p in shuffled[g_count:g_count + tt_count]]

        suspects = [p for p in self.players if p["id"] not in self.guesser_ids]

        dealt = {} if topics else None  # roles only: suspects keep their topic when it has their new side
        blocked = self._blocked() if topics else set()
        unused_topics = [t for t in library() if t["id"] not in blocked]
        if topics and len(unused_topics) < len(suspects):
            self.log("Topic pool exhausted for this lobby: reusing played topics.", level="WARN")
            unused_topics = [t for t in library() if t["id"] not in self.used_topic_ids] or library()

        # Weighted by each player's tags / expertise when the admin turned matching on; plain random otherwise.
        # Two passes: truth tellers from items with a truth, then liars from items with a lie (packs may hold one-sided items).
        mode = accounts.settings().get("match_mode", "off")
        tts = [p for p in suspects if p["id"] in self.truth_teller_ids]
        for p in self.players:  # clear last round's topics so they don't block this round's deal
            if topics or p["id"] in self.guesser_ids:
                p["topic"] = None
        if topics:
            dealt = match.deal(tts, [t for t in unused_topics if packs.has_side(t, "truth")], mode)
            taken = {t["id"] for t in dealt.values()} | {t["group"] for t in dealt.values() if t.get("group")}
            dealt.update(match.deal([p for p in suspects if p not in tts],
                                    [t for t in unused_topics if packs.has_side(t, "lie") and t["id"] not in taken and t.get("group") not in taken], mode))

        for p in self.players:
            p["voted_for"] = None

            if p["id"] in self.guesser_ids:
                p["role"] = "guesser"
                p["is_voting_guesser"] = (p["id"] == self.voting_guesser_id)
                p["topic"] = None
                p["category"] = None
                p["statement"] = None
                p["detailed_description"] = None
            elif p["id"] in self.truth_teller_ids:
                p["role"] = "truth_teller"
                p["is_voting_guesser"] = False
                if dealt is not None:
                    p["topic"], p["statement"] = (dealt[p["id"]]["topic"] if p["id"] in dealt else None), None
                self._give(p, "truth_teller")
            else:
                p["role"] = "liar"
                p["is_voting_guesser"] = False
                if dealt is not None:
                    p["topic"], p["statement"] = (dealt[p["id"]]["topic"] if p["id"] in dealt else None), None
                self._give(p, "liar")

        self._ensure_all_suspects_have_content()
        self._save_players()

        voter_p = next((p for p in self.players if p["id"] == self.voting_guesser_id), None)
        voter_name = voter_p["name"] if voter_p else "None"
        tt_names = ", ".join(p["name"] for p in self.players if p["id"] in self.truth_teller_ids) or "None"
        g_names = ", ".join(p["name"] for p in self.players if p["id"] in self.guesser_ids) or "None"
        self.log(
            f"Round {'roles' if roles else ''}{' & ' if roles and topics else ''}{'topics' if topics else ''} dealt ({g_count} Guesser(s), {tt_count} Truth Teller(s)): "
            f"Guessers = [{g_names}] (Voter: {voter_name}), Truth Teller(s) = [{tt_names}]",
            level="ACTION"
        )

    def _target_tt(self, n: int, g: int) -> int:
        """Truth tellers wanted for n players / g guessers under the current role mode."""
        if self.role_mode == "one_liar":
            return max(1, n - g - 1)
        if self.role_mode == "one_truth":
            return 1
        return max(1, self.target_truth_teller_count)

    def set_role_mode(self, mode: str) -> bool:
        if mode not in ("one_liar", "custom", "one_truth"):
            return False
        self.role_mode = mode
        self.log(f"Role mode: {mode}", level="ACTION")
        if self.phase == "lobby":
            self.assign_round_roles()
        return True

    def _book_round(self):
        """Record the roles just played: 'debt' grows by each role's fair share and drops by 1 for the
        role actually played, so a positive debt means the player is owed that role."""
        n = len(self.players)
        if not n:
            return
        slots = {r: sum(1 for p in self.players if p.get("role") == r) for r in ("guesser", "truth_teller", "liar")}
        for p in self.players:
            debt = p.setdefault("debt", {r: 0.0 for r in slots})
            for r, k in slots.items():
                debt[r] = debt.get(r, 0.0) + k / n
            debt[p.get("role", "liar")] -= 1
            p["last_role"] = p.get("role")

    def _fair_deal(self, g: int, tt: int) -> Tuple[List[str], List[str]]:
        """Scarcest role first, weighted by how owed each player is; nobody repeats last round's role
        unless there aren't enough others. Returns (guesser_ids, truth_teller_ids)."""
        counts = {"guesser": g, "truth_teller": tt, "liar": len(self.players) - g - tt}
        order = sorted(counts, key=counts.get)  # the last (largest) role takes whoever is left
        best, best_score = None, None
        # ponytail: 30 random tries, not an exact matching; finds a zero-repeat deal at party sizes.
        for _ in range(30):
            pool, deal = list(self.players), {}
            for role in order[:-1]:
                for _k in range(counts[role]):
                    cands = [p for p in pool if p.get("last_role") != role] or pool
                    w = [math.exp(2 * p.get("debt", {}).get(role, 0.0)) for p in cands]
                    pick = random.choices(cands, weights=w)[0]
                    pool.remove(pick)
                    deal[pick["id"]] = role
            for p in pool:
                deal[p["id"]] = order[-1]
            score = sum(1 for p in self.players if p.get("last_role") == deal[p["id"]])
            if best is None or score < best_score:
                best, best_score = deal, score
                if not score:
                    break
        ids = lambda r: [p["id"] for p in self.players if best[p["id"]] == r]
        return ids("guesser"), ids("truth_teller")

    def can_ready(self) -> bool:
        return self.phase == "reveal" or (self.phase == "lobby" and self.check_role_requirements()[0])

    def toggle_ready(self, player_id: str) -> bool:
        with self._ready_lock:
            if not self.can_ready() or not any(p["id"] == player_id for p in self.players):
                return False
            self.ready_ids ^= {player_id}
            self._advance_if_all_ready()
            return True

    def _advance_if_all_ready(self):
        with self._ready_lock:
            if not self.players or not self.can_ready() or not {p["id"] for p in self.players} <= self.ready_ids:
                return
            self.log("Everyone is ready.", level="ACTION")
            if self.phase == "lobby":
                self.next_phase()
            else:
                self.next_round()

    def randomize_roles(self):
        """New roles; suspects keep their topics where the new role allows it."""
        self.assign_round_roles(topics=False)

    def new_topics(self, record_old: bool):
        """New topics for everyone, same roles. record_old: count the dropped topics as heard."""
        if record_old:
            self._record_history()
        self.assign_round_roles(roles=False)

    def touch(self):
        self.last_activity = time.time()

    def end_game(self, sign_out_all: bool = False, reason: str = "Admin ended the game"):
        """Book the result (top scorers win, ties included), then start a fresh lobby."""
        if any(p.get("score", 0) > 0 for p in self.players):
            top = max(p.get("score", 0) for p in self.players)
            accts = [p["account_id"] for p in self.players if p.get("account_id")]
            winners = [p for p in self.players if p.get("score", 0) == top]
            accounts.record_game(accts, [p["account_id"] for p in winners if p.get("account_id")])
            self.log(f"{reason}. Winner(s): {', '.join(p['name'] for p in winners)} with {top} pts.", level="ACTION")
        else:
            self.log(f"{reason} (no points scored).", level="ACTION")
        if sign_out_all:
            self.players, self.guesser_ids, self.truth_teller_ids, self.voting_guesser_id = [], [], [], None
        self.reset_game()
        self.touch()

    def add_review(self, p: Dict[str, Any], score: Any, text: Any) -> Optional[str]:
        """Store a 0-10 review of the statement this player holds right now; returns an error message or None."""
        if not p.get("statement"):
            return "You don't hold a statement right now."
        if isinstance(score, bool) or not isinstance(score, (int, float)) or score != int(score) or not 0 <= score <= 10:
            return "Pick a score from 0 to 10."
        text = str(text or "").strip()
        if len(text) > 1000 or len(text.split()) > 100:
            return "Keep the review to 100 words."
        t = find_topic_data(p.get("topic")) or {}
        tt = p["id"] in self.truth_teller_ids
        facts = p.get("detailed_description") if tt else packs.lie_facts(t, p.get("statement"))
        acct = accounts.account_by_id(p["account_id"]) if p.get("account_id") else None
        accounts.add_review({
            "ts": int(time.time()), "game_id": self.game_id, "round": self.round_number,
            "topic_id": t.get("id"), "pack": t.get("pack"), "topic": p.get("topic"), "side": "truth" if tt else "lie",
            "statement": p.get("statement"), "facts": facts, "score": int(score), "text": text,
            "player_name": p.get("name"), "account_id": acct["id"] if acct else None})
        self.log(f"{p.get('name')} reviewed '{p.get('topic')}': {int(score)}/10", level="ACTION")
        return None

    def end_if_idle(self, limit: Optional[float] = None):
        mins = accounts.settings().get("idle_minutes", 60)
        limit = mins * 60 if limit is None else limit
        if time.time() - self.last_activity > limit and (self.players or self.phase != "lobby"):
            self.end_game(sign_out_all=True, reason=f"Game ended after {mins} minutes without activity")

    def check_role_requirements(self) -> Tuple[bool, Optional[str], Dict[str, int]]:
        """
        Validates whether the currently selected role counts satisfy the minimum requirement to successfully run a game:
        - At least 1 Guesser
        - At least 1 Truth Teller
        - At least 1 Liar
        
        Returns:
            (is_valid, error_message, counts_dict)
        """
        total_players = len(self.players)
        target_g = max(1, getattr(self, "target_guesser_count", 1))
        target_tt = self._target_tt(total_players, target_g)

        # Effective role counts based on target counts or manually assigned roles
        actual_g = len(self.guesser_ids)
        actual_tt = len(self.truth_teller_ids)
        eff_g = max(target_g, actual_g) if actual_g > 0 else target_g
        eff_tt = max(target_tt, actual_tt) if actual_tt > 0 else target_tt

        eff_liars = total_players - eff_g - eff_tt
        min_players_needed = max(3, eff_g + eff_tt + 1)

        counts = {
            "players": total_players,
            "guessers": eff_g,
            "truth_tellers": eff_tt,
            "liars": max(0, eff_liars),
            "min_required_players": min_players_needed
        }

        if total_players == 0:
            return (
                False,
                "Cannot start game: No players have joined. At least 1 Guesser, 1 Truth Teller, and 1 Liar are required (minimum 3 players).",
                counts
            )

        if total_players < 3:
            return (
                False,
                f"Cannot start game: At least 1 Guesser, 1 Truth Teller, and 1 Liar are required (minimum 3 players). Only {total_players} player(s) joined. Please wait for more players to join or adjust role counts.",
                counts
            )

        if eff_g < 1:
            return (
                False,
                f"Cannot start game: At least 1 Guesser must be present (currently {eff_g}). Please adjust the number of Guessers to at least 1.",
                counts
            )

        if eff_tt < 1:
            return (
                False,
                f"Cannot start game: At least 1 Truth Teller must be present (currently {eff_tt}). Please adjust the number of Truth Tellers to at least 1.",
                counts
            )

        if eff_liars < 1:
            return (
                False,
                f"Cannot start game: At least 1 Liar must be present. Currently selected: {eff_g} Guesser(s) and {eff_tt} Truth Teller(s), leaving {max(0, eff_liars)} Liar(s) among {total_players} players. Please change the number of each role to allow at least 1 Liar (or add more players).",
                counts
            )

        return True, None, counts

    def set_role_counts(self, guesser_count: int, truth_teller_count: int, apply_now: bool = True) -> bool:
        try:
            g = int(guesser_count)
            tt = int(truth_teller_count)
        except (ValueError, TypeError):
            return False
        if g < 1 or tt < 1:
            return False

        self.target_guesser_count = g
        self.target_truth_teller_count = tt
        self.log(f"Role counts configured: {g} Guesser(s), {tt} Truth Teller(s)", level="ACTION")

        if apply_now and self.phase == "lobby":
            self.assign_round_roles()
        return True

    def set_voting_guesser(self, player_id: str) -> bool:
        target = next((p for p in self.players if p["id"] == player_id), None)
        if not target:
            return False

        if player_id not in self.guesser_ids:
            self.set_player_role(player_id, "guesser", is_voter=True)
        else:
            self.voting_guesser_id = player_id
            for p in self.players:
                p["is_voting_guesser"] = (p["id"] == self.voting_guesser_id)
            self._save_players()

        self.log(f"Designated Lead Voting Guesser: {target['name']}", level="ACTION")
        return True

    def set_player_role(self, player_id: str, new_role: str, is_voter: Optional[bool] = None) -> bool:
        """
        Directly assigns a specific role to a specific player without randomizing.
        Roles: 'guesser', 'truth_teller', 'liar'.
        Guarantees that:
        - At least one Guesser exists (and one is designated voter).
        - At least one Truth Teller exists.
        - Truth Tellers ALWAYS have their true statement and detailed description.
        """
        target = next((p for p in self.players if p["id"] == player_id), None)
        if not target or new_role not in ("guesser", "truth_teller", "liar"):
            return False

        if new_role == "guesser":
            if self.target_guesser_count == 1 and self.voting_guesser_id == player_id and len(self.guesser_ids) == 1:
                return True

            was_tt = (player_id in self.truth_teller_ids)
            if was_tt:
                self.truth_teller_ids.remove(player_id)

            target["role"] = "guesser"
            target["topic"] = None
            target["category"] = None
            target["statement"] = None
            target["detailed_description"] = None

            if self.target_guesser_count == 1:
                # In single guesser mode, demote old guesser(s) to liar
                for gid in list(self.guesser_ids):
                    if gid != player_id:
                        old_g = next((p for p in self.players if p["id"] == gid), None)
                        if old_g:
                            old_g["role"] = "liar"
                            old_g["is_voting_guesser"] = False
                            self._give(old_g, "liar")
                self.guesser_ids = [player_id]
                self.voting_guesser_id = player_id
            else:
                if player_id not in self.guesser_ids:
                    self.guesser_ids.append(player_id)
                if is_voter is None or is_voter is True or not self.voting_guesser_id:
                    self.voting_guesser_id = player_id

            if was_tt and not self.truth_teller_ids:
                candidates = [p for p in self.players if p["id"] not in self.guesser_ids]
                if candidates:
                    cand = candidates[0]
                    self.truth_teller_ids.append(cand["id"])
                    cand["role"] = "truth_teller"

        elif new_role == "truth_teller":
            if self.target_truth_teller_count == 1 and self.truth_teller_id == player_id and len(self.truth_teller_ids) == 1:
                return True

            was_guesser = (player_id in self.guesser_ids)
            if was_guesser:
                self.guesser_ids.remove(player_id)
                if self.voting_guesser_id == player_id:
                    self.voting_guesser_id = self.guesser_ids[0] if self.guesser_ids else None

            if self.target_truth_teller_count == 1:
                # In single truth teller mode, demote old truth teller(s) to liar
                for tid in list(self.truth_teller_ids):
                    if tid != player_id:
                        old_tt = next((p for p in self.players if p["id"] == tid), None)
                        if old_tt:
                            old_tt["role"] = "liar"
                            self._give(old_tt, "liar")
                self.truth_teller_ids = [player_id]
            else:
                if player_id in self.truth_teller_ids:
                    self.truth_teller_ids.remove(player_id)
                self.truth_teller_ids.insert(0, player_id)

            target["role"] = "truth_teller"

            if was_guesser and not self.guesser_ids:
                candidates = [p for p in self.players if p["id"] not in self.truth_teller_ids]
                if candidates:
                    cand = candidates[0]
                    self.guesser_ids.append(cand["id"])
                    self.voting_guesser_id = cand["id"]
                    cand["role"] = "guesser"
                    cand["topic"] = None
                    cand["category"] = None
                    cand["statement"] = None
                    cand["detailed_description"] = None

            self._give(target, "truth_teller")

        elif new_role == "liar":
            was_guesser = (player_id in self.guesser_ids)
            was_tt = (player_id in self.truth_teller_ids)

            if was_guesser:
                self.guesser_ids.remove(player_id)
                if self.voting_guesser_id == player_id:
                    self.voting_guesser_id = self.guesser_ids[0] if self.guesser_ids else None

            if was_tt:
                self.truth_teller_ids.remove(player_id)

            target["role"] = "liar"
            target["detailed_description"] = None

            if not self.guesser_ids:
                candidates = [p for p in self.players if p["id"] != player_id and p["id"] not in self.truth_teller_ids]
                if not candidates:
                    candidates = [p for p in self.players if p["id"] != player_id]
                if candidates:
                    cand = candidates[0]
                    if cand["id"] in self.truth_teller_ids:
                        self.truth_teller_ids.remove(cand["id"])
                    self.guesser_ids.append(cand["id"])
                    self.voting_guesser_id = cand["id"]
                    cand["role"] = "guesser"
                    cand["topic"] = None
                    cand["category"] = None
                    cand["statement"] = None
                    cand["detailed_description"] = None

            if not self.truth_teller_ids:
                candidates = [p for p in self.players if p["id"] != player_id and p["id"] not in self.guesser_ids]
                if candidates:
                    cand = candidates[0]
                    self.truth_teller_ids.append(cand["id"])
                    cand["role"] = "truth_teller"

            target["statement"] = None  # a fresh lie for the new role
            self._give(target, "liar")

        for p in self.players:
            p["is_voting_guesser"] = (p["id"] == self.voting_guesser_id)

        self._ensure_all_suspects_have_content()
        self.target_guesser_count = len(self.guesser_ids)
        self.target_truth_teller_count = len(self.truth_teller_ids)
        self._save_players()
        self.log(f"Role assigned directly: {target['name']} -> {new_role.upper()}", level="ACTION")
        return True

    def set_guessers(self, player_ids: List[str], voter_id: Optional[str] = None) -> bool:
        """
        Directly sets multiple players as Guessers.
        - Guarantees at least 1 player remains as a suspect (truth teller or liar).
        - Designates voter_id as the Lead Voting Guesser (or defaults to the first guesser).
        - Clears guesser properties and topics for guessers.
        - Preserves or reassigns Truth Tellers among remaining players.
        """
        if not player_ids:
            return False

        valid_ids = [pid for pid in player_ids if any(p["id"] == pid for p in self.players)]
        if not valid_ids:
            return False

        if len(valid_ids) >= len(self.players):
            valid_ids = valid_ids[:len(self.players) - 1]
            if not valid_ids:
                return False

        self.target_guesser_count = len(valid_ids)
        self.guesser_ids = list(valid_ids)

        if voter_id and voter_id in self.guesser_ids:
            self.voting_guesser_id = voter_id
        elif self.voting_guesser_id not in self.guesser_ids:
            self.voting_guesser_id = self.guesser_ids[0]

        # Any guesser who was in truth_teller_ids must be removed from truth_teller_ids
        self.truth_teller_ids = [tid for tid in self.truth_teller_ids if tid not in self.guesser_ids]

        # If no truth tellers remain, pick one suspect to be truth teller
        suspects = [p for p in self.players if p["id"] not in self.guesser_ids]
        if not self.truth_teller_ids and suspects:
            self.truth_teller_ids = [suspects[0]["id"]]

        # Update roles for all players
        for p in self.players:
            pid = p["id"]
            if pid in self.guesser_ids:
                p["role"] = "guesser"
                p["is_voting_guesser"] = (pid == self.voting_guesser_id)
                p["topic"] = None
                p["category"] = None
                p["statement"] = None
                p["detailed_description"] = None
            elif pid in self.truth_teller_ids:
                p["role"] = "truth_teller"
                p["is_voting_guesser"] = False
            else:
                p["role"] = "liar"
                p["is_voting_guesser"] = False

        self._ensure_all_suspects_have_content()
        self._save_players()
        self.log(f"Assigned Guesser team: {[p['name'] for p in self.players if p['id'] in self.guesser_ids]} (Lead Voter: {self.voting_guesser_name})", level="ACTION")
        return True

    def set_truth_tellers(self, player_ids: List[str]) -> bool:
        """
        Directly sets multiple players as Truth Tellers.
        - Guarantees at least 1 player remains as a Guesser.
        - Ensures each Truth Teller gets unique topic, true statement, and detailed description.
        - All other suspects become Liars.
        """
        if not player_ids:
            return False

        valid_ids = [pid for pid in player_ids if any(p["id"] == pid for p in self.players)]
        if not valid_ids:
            return False

        if len(valid_ids) >= len(self.players):
            valid_ids = valid_ids[:len(self.players) - 1]
            if not valid_ids:
                return False

        self.target_truth_teller_count = len(valid_ids)
        self.truth_teller_ids = list(valid_ids)

        # Remove truth tellers from guesser_ids
        self.guesser_ids = [gid for gid in self.guesser_ids if gid not in self.truth_teller_ids]

        # If no guessers remain, assign a non-truth-teller as guesser
        if not self.guesser_ids:
            remaining_cands = [p for p in self.players if p["id"] not in self.truth_teller_ids]
            if remaining_cands:
                self.guesser_ids = [remaining_cands[0]["id"]]
                self.voting_guesser_id = self.guesser_ids[0]
        elif self.voting_guesser_id not in self.guesser_ids:
            self.voting_guesser_id = self.guesser_ids[0]

        # Update roles for all players
        for p in self.players:
            pid = p["id"]
            if pid in self.guesser_ids:
                p["role"] = "guesser"
                p["is_voting_guesser"] = (pid == self.voting_guesser_id)
                p["topic"] = None
                p["category"] = None
                p["statement"] = None
                p["detailed_description"] = None
            elif pid in self.truth_teller_ids:
                p["role"] = "truth_teller"
                p["is_voting_guesser"] = False
            else:
                p["role"] = "liar"
                p["is_voting_guesser"] = False

        self._ensure_all_suspects_have_content()
        self._save_players()
        self.log(f"Assigned Truth Teller(s): {[p['name'] for p in self.players if p['id'] in self.truth_teller_ids]}", level="ACTION")
        return True

    def set_guesser(self, player_id_or_ids) -> bool:
        if isinstance(player_id_or_ids, (list, tuple, set)):
            return self.set_guessers(list(player_id_or_ids))
        return self.set_player_role(player_id_or_ids, "guesser", is_voter=True)

    def set_truth_teller(self, player_id_or_ids) -> bool:
        if isinstance(player_id_or_ids, (list, tuple, set)):
            return self.set_truth_tellers(list(player_id_or_ids))
        return self.set_player_role(player_id_or_ids, "truth_teller")

    def set_phase(self, phase: str, force: bool = False) -> bool:
        valid_phases = ["lobby", "setup", "questioning", "voting", "reveal"]
        if phase not in valid_phases:
            return False

        # When round reaches its end (reveal phase), prevent returning to a previous round phase:
        if not force and self.phase == "reveal" and phase in ("setup", "questioning", "voting"):
            self.log(f"Phase change blocked: Round {self.round_number} is completed. Cannot return to previous phase ({phase.upper()}). Please start a new round or terminate game and return to lobby.", level="WARN")
            return False

        # When starting the game (transitioning from lobby to an active phase like setup):
        if not force and self.phase == "lobby" and phase in ("setup", "questioning", "voting", "reveal"):
            valid, err_msg, _ = self.check_role_requirements()
            if not valid:
                self.log(f"Game start blocked: {err_msg}", level="WARN")
                return False

        prev_phase = self.phase
        self.phase = phase
        self.ready_ids = set()
        self.log(f"Game phase changed to: {phase.upper()}", level="ACTION")
        # When leaving lobby into setup, questioning or beyond, guarantee topics and descriptions are assigned
        if phase in ("setup", "questioning", "voting", "reveal"):
            self._ensure_all_suspects_have_content()
        # If entering reveal phase and round results haven't been scored yet, trigger reveal and scoring
        if phase == "reveal" and self.last_round_results is None:
            self.reveal_and_score()
        return True

    def _ensure_all_suspects_have_content(self):
        """Ensures all suspects have unique topics and Truth Tellers have their detailed descriptions."""
        if not self.guesser_ids or not self.voting_guesser_id or not self.truth_teller_ids:
            if len(self.players) >= 2:
                self.assign_round_roles()
                return

        # Clean overlap
        self.truth_teller_ids = [tid for tid in self.truth_teller_ids if tid not in self.guesser_ids]
        if not self.truth_teller_ids:
            cands = [p["id"] for p in self.players if p["id"] not in self.guesser_ids]
            if cands:
                self.truth_teller_ids = [cands[0]]

        if self.voting_guesser_id not in self.guesser_ids and self.guesser_ids:
            self.voting_guesser_id = self.guesser_ids[0]

        assigned_topics = set()
        for p in self.players:
            p["is_voting_guesser"] = (p["id"] == self.voting_guesser_id)

            if p["id"] in self.guesser_ids:
                p["role"] = "guesser"
                p["topic"] = None
                p["category"] = None
                p["statement"] = None
                p["detailed_description"] = None
            elif p["id"] in self.truth_teller_ids:
                p["role"] = "truth_teller"
                self._give(p, "truth_teller", assigned_topics)
                assigned_topics.add(p["topic"])
            else:
                p["role"] = "liar"
                self._give(p, "liar", assigned_topics)
                assigned_topics.add(p["topic"])
        self._record_used_statements()
        self._save_players()

    def next_phase(self) -> str:
        order = ["lobby", "setup", "questioning", "voting", "reveal"]
        try:
            # When a round reaches its end (reveal phase), advance is disabled to prevent
            # confusion or accidentally returning to a previous phase.
            if self.phase == "reveal":
                self.log("Advance blocked: Round is completed. Please start a new round or terminate game and return to lobby.", level="WARN")
                return self.phase

            curr_idx = order.index(self.phase)
            next_idx = (curr_idx + 1) % len(order)
            target_phase = order[next_idx]
            if self.phase == "lobby" and target_phase == "setup":
                valid, err_msg, _ = self.check_role_requirements()
                if not valid:
                    self.log(f"Game start blocked: {err_msg}", level="WARN")
                    return self.phase
            success = self.set_phase(target_phase)
            if not success:
                return self.phase
        except ValueError:
            self.set_phase("lobby")
        return self.phase

    def cast_vote(self, voter_id: str, target_id: Optional[Union[str, List[str]]] = None, target_ids: Optional[Union[str, List[str]]] = None) -> bool:
        if voter_id != self.voting_guesser_id:
            self.log(f"Vote blocked: Player {voter_id} is not the designated Voting Guesser. Only the Voting Guesser can vote!", level="WARN")
            return False

        voter = next((p for p in self.players if p["id"] == self.voting_guesser_id), None)
        if not voter:
            return False

        raw = target_ids if target_ids is not None else target_id
        if raw is None:
            return False

        if isinstance(raw, list):
            target_list = [str(x).strip() for x in raw if str(x).strip()]
        elif isinstance(raw, str):
            target_list = [str(x).strip() for x in raw.split(",") if str(x).strip()]
        else:
            target_list = [str(raw)]

        if not target_list:
            return False

        # Only suspects can be voted for (guessers cannot be accused of being the truth teller)
        valid_targets = [p for p in self.players if p["id"] in target_list and p["id"] not in self.guesser_ids]
        if not valid_targets:
            self.log(f"Vote blocked: No valid suspects found in target list {target_list}!", level="WARN")
            return False

        if len(valid_targets) == 1:
            voter["voted_for"] = valid_targets[0]["id"]
        else:
            voter["voted_for"] = [p["id"] for p in valid_targets]

        self._save_players()
        accused_names = ", ".join(p["name"] for p in valid_targets)
        self.log(f"Lead Guesser's Accusation: {voter['name']} accuses [{accused_names}] of telling the TRUTH!", level="ACTION")
        # Automatically reveal the result after a selection was made by the guesser
        self.reveal_and_score()
        return True

    def clear_votes(self):
        for p in self.players:
            p["voted_for"] = None
        self._save_players()

    def reveal_and_score(self) -> Dict[str, Any]:
        self.phase = "reveal"
        results = {
            "guesser": None,
            "guessers": [],
            "truth_teller": None,
            "truth_tellers": [],
            "liars": [],
            "picked_player": None,
            "picked_players": [],
            "is_correct": False,
            "score_changes": {},
            "standings": []
        }
        voting_guesser = next((p for p in self.players if p["id"] == self.voting_guesser_id), None)
        guesser_players = [p for p in self.players if p["id"] in self.guesser_ids]
        truth_players = [p for p in self.players if p["id"] in self.truth_teller_ids]

        if voting_guesser:
            results["guesser"] = {"id": voting_guesser["id"], "name": voting_guesser["name"], "voted_for": voting_guesser.get("voted_for")}

        for gp in guesser_players:
            results["guessers"].append({
                "id": gp["id"],
                "name": gp["name"],
                "is_voting_guesser": (gp["id"] == self.voting_guesser_id),
                "voted_for": gp.get("voted_for")
            })

        for tp in truth_players:
            results["truth_tellers"].append({
                "id": tp["id"],
                "name": tp["name"],
                "topic": tp["topic"],
                "true_statement": tp["statement"],
                "detailed_description": tp["detailed_description"]
            })
        if truth_players:
            results["truth_teller"] = results["truth_tellers"][0]

        liar_players = [p for p in self.players if p["role"] == "liar"]
        for lp in liar_players:
            results["liars"].append({
                "id": lp["id"],
                "name": lp["name"],
                "topic": lp["topic"],
                "false_statement": lp["statement"]
            })

        # Extract voted player IDs
        voted_raw = voting_guesser.get("voted_for") if voting_guesser else None
        if isinstance(voted_raw, list):
            voted_ids = [str(x) for x in voted_raw if x]
        elif isinstance(voted_raw, str) and voted_raw:
            voted_ids = [voted_raw]
        else:
            voted_ids = []

        picked_players = [p for p in self.players if p["id"] in voted_ids]
        results["picked_players"] = [
            {
                "id": p["id"],
                "name": p["name"],
                "role": p.get("role", "suspect"),
                "is_truth_teller": (p["id"] in self.truth_teller_ids),
                "topic": p.get("topic")
            }
            for p in picked_players
        ]
        results["picked_player"] = results["picked_players"][0] if results["picked_players"] else None

        # Rule check:
        # "If there are more than 1 truthteller, the guesser(s) must identify all of them to receive a point.
        #  Everyone voted as the truthteller will be awarded a point for convincing the guesser, regardless of their actual role"
        actual_tt_ids = set(self.truth_teller_ids)
        voted_ids_set = set(voted_ids)
        is_correct = bool(actual_tt_ids and voted_ids_set == actual_tt_ids)
        results["is_correct"] = is_correct

        # Initialize all score changes to 0
        for p in self.players:
            results["score_changes"][p["name"]] = 0

        # 1. Guesser team gets 1 point each if all truth tellers were correctly identified
        for gp in guesser_players:
            pts = 1 if is_correct else 0
            gp["score"] += pts
            results["score_changes"][gp["name"]] = pts

        # 2. Everyone voted as the truth teller gets 1 point for convincing the guesser, regardless of actual role
        for pp in picked_players:
            pp["score"] += 1
            results["score_changes"][pp["name"]] = results["score_changes"].get(pp["name"], 0) + 1

        g_names = ", ".join(gp["name"] for gp in guesser_players) or "Guessers"
        tt_names = ", ".join(tp["name"] for tp in truth_players) or "Truth Teller"
        picked_names = ", ".join(pp["name"] for pp in picked_players) or "Nobody"

        if is_correct:
            if len(truth_players) > 1:
                self.log(f"Brilliant deduction! Guesser team ({g_names}) correctly identified all {len(truth_players)} Truth Tellers: {picked_names} (+1 pt to Guessers, +1 pt to each Truth Teller)!", level="INFO")
            else:
                self.log(f"Brilliant deduction! Guesser team ({g_names}) correctly identified Truth Teller {picked_names} (+1 pt each)!", level="INFO")
        elif picked_players:
            self.log(f"Bluff successful! Accused player(s) [{picked_names}] convinced Guesser team (+1 pt each). The actual Truth Teller(s) were: {tt_names}!", level="INFO")
        else:
            self.log("Accusation concluded with no selection.", level="WARN")

        for p in self.players:
            if p.get("account_id"):
                accounts.add_round_score(p["account_id"], results["score_changes"].get(p["name"], 0))
        self._save_players()
        self.log(f"REVEAL: {tt_names} told the truth this round!", level="WARN")

        results["standings"] = self.get_standings(pts_map=results["score_changes"])
        self.last_round_results = results
        return results

    def get_standings(self, pts_map: Optional[Dict[str, int]] = None, reveal_roles: bool = False) -> List[Dict[str, Any]]:
        if pts_map is None:
            pts_map = self.last_round_results.get("score_changes", {}) if self.last_round_results else {}
        sorted_players = sorted(self.players, key=lambda x: (-x.get("score", 0), x.get("name", "")))
        standings = []
        is_reveal = (self.phase == "reveal" or reveal_roles)
        for rank, p in enumerate(sorted_players, 1):
            if is_reveal:
                role = p.get("role", "liar")
            else:
                role = "guesser" if p["id"] in self.guesser_ids else "suspect"
            standings.append({
                "rank": rank,
                "id": p["id"],
                "name": p["name"],
                "score": p.get("score", 0),
                "role": role,
                "pts_gained": pts_map.get(p["name"], 0)
            })
        return standings

    def guesser_advance(self, player_id: str) -> bool:
        if player_id not in self.guesser_ids:
            self.log(f"Advance rejected: Player {player_id} is not a Guesser.", level="WARN")
            return False

        if self.phase == "setup":
            self.set_phase("questioning")
            self.log(f"Guesser advanced game to QUESTIONING phase.", level="ACTION")
            return True
        elif self.phase == "questioning":
            self.set_phase("voting")
            self.log(f"Guesser confirmed: All statements heard and understood! Advancing to ACCUSATION phase.", level="ACTION")
            return True
        return False

    def next_round(self) -> bool:
        valid, err_msg, _ = self.check_role_requirements()
        if not valid:
            self.log(f"Cannot start next round: {err_msg}", level="WARN")
            return False
        self.round_number += 1
        self.clear_votes()
        self.last_round_results = None
        self._book_round()
        self.assign_round_roles()
        self.set_phase("setup", force=True)
        self.log(f"--- Started Round {self.round_number} ---", level="INFO")
        return True

    def reset_game(self):
        self.round_number = 1
        self.phase = "lobby"
        self.last_round_results = None
        self.game_id = int(time.time() * 1000)  # new game; the archive keeps earlier games
        self.used_topic_ids = []
        temps = [p["id"] for p in self.players if p.get("token") and not p.get("account_id")]
        self.players = [p for p in self.players if p["id"] not in temps]
        self.guesser_ids = [i for i in self.guesser_ids if i not in temps]
        self.truth_teller_ids = [i for i in self.truth_teller_ids if i not in temps]
        if self.voting_guesser_id in temps:
            self.voting_guesser_id = self.guesser_ids[0] if self.guesser_ids else None
        self.ready_ids = set()
        for p in self.players:
            p["score"] = 0
            p["voted_for"] = None
            p.pop("debt", None)
            p.pop("last_role", None)
        self.clear_votes()
        self.assign_round_roles()
        self.log(f"Game reset to initial state ({len(temps)} temporary player(s) signed out).", level="INFO")

    def adjust_score(self, player_id: str, delta: int) -> bool:
        p = next((x for x in self.players if x["id"] == player_id), None)
        if p:
            p["score"] = max(0, p["score"] + delta)
            self._save_players()
            self.log(f"Adjusted score for {p['name']}: {p['score']} ({'+' if delta > 0 else ''}{delta})", level="ACTION")
            return True
        return False

    def _match_pct(self, p: Dict[str, Any], settings: Dict[str, Any]) -> Optional[int]:
        """Phone badge: how well this suspect's topic fits their tags / expertise, among topics of the same side."""
        mode, t = settings.get("match_mode", "off"), find_topic_data(p.get("topic"))
        if mode == "off" or not t or p.get("role") not in ("truth_teller", "liar"):
            return None
        need = "truth" if p["role"] == "truth_teller" else "lie"
        return match.percent(p, t, [x for x in library() if packs.has_side(x, need)], mode)

    def _match_status(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Admin view of matching; in expertise mode it also keeps the embedding cache topped up."""
        if settings.get("match_mode") == "expertise":
            match.warm([match.topic_text(t) for t in library()] + [match.query_text(p.get("expertise")) for p in self.players])
        elif settings.get("match_mode") == "tags":
            match.warm([match.tag_text(t) for t in packs.all_tags()] + [match.tag_text(t) for p in self.players for t in p.get("tags", [])])
        return {**match.status(), "profiles": sum(1 for p in self.players if p.get("tags") or p.get("expertise"))}

    def get_state(self, is_admin: bool = True, player_id: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        self.end_if_idle()
        # Guarantee all suspects have topics and roles assigned
        needs_content = any(
            p["id"] not in self.guesser_ids and (not p.get("topic") or not p.get("statement"))
            for p in self.players
        )
        if needs_content or not self.guesser_ids or not self.voting_guesser_id or not self.truth_teller_ids:
            self._ensure_all_suspects_have_content()

        settings = accounts.settings()
        guesser = next((p for p in self.players if p["id"] == self.voting_guesser_id), None)
        truth_player = next((p for p in self.players if p["id"] in self.truth_teller_ids), None)

        players_view = []
        for p in self.players:
            is_p_guesser = (p["id"] in self.guesser_ids)
            is_p_voter = (p["id"] == self.voting_guesser_id)
            is_p_tt = (p["id"] in self.truth_teller_ids)

            p_data = {
                "id": p["id"],
                "name": p["name"],
                "score": p["score"],
                "voted_for": p.get("voted_for"),
                "is_guesser": is_p_guesser,
                "is_voting_guesser": is_p_voter,
            }

            if is_admin:
                p_data["account"] = bool(p.get("account_id"))
            if is_admin or self.phase == "reveal":
                p_data["role"] = "guesser" if is_p_guesser else ("truth_teller" if is_p_tt else "liar")
                p_data["is_truth_teller"] = is_p_tt
                p_data["topic"] = p.get("topic")
                p_data["category"] = p.get("category")
                p_data["statement"] = p.get("statement")
                p_data["detailed_description"] = p.get("detailed_description")
                # Paper source (PhD pack): only ever attached to a truth, so it can't leak a liar.
                p_data["source"] = (find_topic_data(p.get("topic")) or {}).get("source") if is_p_tt else None
                if is_admin and p_data["role"] == "liar":  # the admin dossier shows each liar's background facts
                    p_data["lie_facts"] = packs.lie_facts(find_topic_data(p.get("topic")) or {}, p.get("statement"))
            else:
                p_data["role"] = "guesser" if is_p_guesser else "suspect"
                p_data["is_truth_teller"] = None
                p_data["topic"] = p.get("topic")
                p_data["category"] = p.get("category")
                p_data["statement"] = "[Hidden from other players]"
                p_data["detailed_description"] = None

            players_view.append(p_data)

        # For a specific player viewing on mobile
        my_info = None
        if player_id and str(player_id).strip() not in ("undefined", "null", "None", ""):
            pid_str = str(player_id).strip()
            # Match exact ID
            me = next((p for p in self.players if p["id"] == pid_str), None)
            # Match by name fallback (e.g. "name:Alice" or "Alice")
            if not me:
                target_name = pid_str[5:].strip().lower() if pid_str.startswith("name:") else pid_str.lower()
                me = next((p for p in self.players if p["name"].strip().lower() == target_name), None)
            # Private info (role, statement) only for the token holder.
            if me and not is_admin and not self.player_for_token(me["id"], token):
                me = None

            if me:
                is_me_guesser = (me["id"] in self.guesser_ids)
                is_me_voter = (me["id"] == self.voting_guesser_id)
                is_me_tt = (me["id"] in self.truth_teller_ids)
                redact = self.phase in ("questioning", "voting")

                # Self-healing safeguard: Ensure Truth Teller always has topic, statement, and detailed description
                if is_me_tt and (not me.get("detailed_description") or not me.get("statement") or not me.get("topic")):
                    self._give(me, "truth_teller")
                    me["role"] = "truth_teller"
                    self._save_players()
                elif not is_me_guesser and not is_me_tt and (not me.get("statement") or not me.get("topic")):
                    # Self-healing safeguard: Ensure Liar always has topic and false statement
                    self._give(me, "liar")
                    me["role"] = "liar"
                    self._save_players()

                fellow_guessers = [p["name"] for p in self.players if p["id"] in self.guesser_ids and p["id"] != me["id"]]

                my_info = {
                    "id": me["id"],
                    "name": me["name"],
                    "role": "guesser" if is_me_guesser else ("truth_teller" if is_me_tt else "liar"),
                    "is_guesser": is_me_guesser,
                    "is_voting_guesser": is_me_voter,
                    "voting_guesser_name": guesser["name"] if guesser else None,
                    "fellow_guessers": fellow_guessers,
                    "is_truth_teller": is_me_tt,
                    "topic": me.get("topic"),
                    "category": me.get("category"),
                    "statement": me.get("statement"),
                    # Truth teller ALWAYS receives their detailed description
                    "detailed_description": me.get("detailed_description") if is_me_tt else None,
                    "lie_facts": (packs.lie_facts(find_topic_data(me.get("topic")) or {}, me.get("statement"))
                                  if me.get("role") == "liar" and settings["lying_facts"] else []),
                    # Sources are redacted while suspects are being questioned:
                    # everyone holds just a statement, so "some university in Germany" is as good as the real thing.
                    "source": (({"redacted": True} if redact else (find_topic_data(me.get("topic")) or {}).get("source"))
                               if is_me_tt and (find_topic_data(me.get("topic")) or {}).get("source") else None),
                    "match_pct": self._match_pct(me, settings),
                    "tag_order": match.rank_tags(me.get("tags", []), sorted(set(packs.all_tags()) | set(me.get("tags", []))), me.get("expertise", "")),
                    "permanent": bool(me.get("account_id")),
                    "tags": me.get("tags", []),
                    "expertise": me.get("expertise", ""),
                    "has_password": bool(me.get("account_id") or me.get("pw_hash")),
                }

        used_true = [s for s in self.used_statements if s.get("type") == "true"]
        used_false = [s for s in self.used_statements if s.get("type") == "false"]
        gkeys = set(accounts.global_keys())
        lib = library()
        lib_keys = {k for t in lib for k in packs.statement_keys(t)}
        used_keys = gkeys & lib_keys  # only statements of enabled packs that still exist
        counts = {"true": sum(k.endswith(":t") for k in used_keys), "false": sum(not k.endswith(":t") for k in used_keys)}
        current_true = [
            {
                "player_id": p["id"],
                "player_name": p["name"],
                "topic": p.get("topic"),
                "category": p.get("category"),
                "statement": p.get("statement"),
                "detailed_description": p.get("detailed_description")
            }
            for p in self.players if p.get("role") == "truth_teller" and p.get("statement")
        ]
        current_false = [
            {
                "player_id": p["id"],
                "player_name": p["name"],
                "topic": p.get("topic"),
                "category": p.get("category"),
                "statement": p.get("statement")
            }
            for p in self.players if p.get("role") == "liar" and p.get("statement")
        ]

        total_true = sum(1 for t in lib if t["true_statement"])
        total_false = sum(len(t["false_statements"]) for t in lib)

        valid_roles, req_err, req_counts = self.check_role_requirements()

        state = {
            "phase": self.phase,
            "round": self.round_number,
            "role_requirements": {
                "valid": valid_roles,
                "error": req_err,
                "players": req_counts["players"],
                "guessers": req_counts["guessers"],
                "truth_tellers": req_counts["truth_tellers"],
                "liars": req_counts["liars"],
                "min_required_players": req_counts["min_required_players"]
            },
            "guesser_id": self.voting_guesser_id,
            "guesser_name": guesser["name"] if guesser else "None",
            "voting_guesser_id": self.voting_guesser_id,
            "voting_guesser_name": guesser["name"] if guesser else "None",
            "guesser_ids": list(self.guesser_ids),
            "target_guesser_count": self.target_guesser_count,
            "target_truth_teller_count": self.target_truth_teller_count,
            "truth_teller_count": len(self.truth_teller_ids),
            "role_mode": self.role_mode,
            "ready_ids": sorted(self.ready_ids),
            "can_ready": self.can_ready(),
            "truth_teller_id": self.truth_teller_id if (is_admin or self.phase == "reveal") else None,
            "truth_teller_name": truth_player["name"] if (is_admin or self.phase == "reveal") and truth_player else "???",
            "truth_teller_ids": list(self.truth_teller_ids) if (is_admin or self.phase == "reveal") else [],
            "players": players_view,
            "my_info": my_info,
            "standings": self.get_standings(reveal_roles=is_admin),
            "last_results": self.last_round_results,
            "used_topics_count": len({accounts.topic_of(k) for k in used_keys}),
            "blocked_topics_count": len(self._blocked()) if is_admin else 0,
            "settings": settings,
            "all_tags": packs.all_tags(),
            "match_status": self._match_status(settings) if is_admin else None,
            "accounts": accounts.list_accounts() if is_admin else [],
            "total_topics_count": len(lib),
            "packs": packs.pack_summaries(gkeys) if is_admin else [],
            "used_true_statements": used_true if is_admin else [],
            "used_false_statements": used_false if is_admin else [],
            "current_true_statements": current_true if is_admin else [],
            "current_false_statements": current_false if is_admin else [],
            "used_true_count": counts["true"],
            "used_false_count": counts["false"],
            "used_truth_count": counts["true"],
            "used_lies_count": counts["false"],
            "total_true_count": total_true,
            "total_false_count": total_false,
            "total_truth_count": total_true,
            "total_lies_count": total_false,
            "logs": self.logs[-100:] if is_admin else []
        }

        return state

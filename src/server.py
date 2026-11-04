"""
HTTP Server and API router for 'One of These People Is Not Lying'.
"""

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, Optional, Tuple

from src import accounts, packs, resume
from src.game import GameManager, NEED_NEW_PASSWORD
from src.qr import generate_qr_svg, LOGO_24
from src.templates import get_admin_html, get_admin_login_html, get_display_html, get_qr_html, get_join_html, get_stage_control_html

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "notthepassword")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATIC_TYPES = {".css", ".js", ".svg", ".woff2", ".png", ".ico"}
# Offline copies of truth sources (PDFs, saved web pages) plus the pdf.js viewer that shows PDFs on any phone.
ARCHIVE_DIR = os.path.abspath(os.environ.get("ARCHIVE_DIR", "/app/archive"))
ARCHIVE_TYPES = {".pdf": "application/pdf", ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
                 ".mjs": "text/javascript", ".json": "application/json", ".ftl": "text/plain; charset=utf-8",
                 ".bcmap": "application/octet-stream", ".pfb": "application/octet-stream", ".wasm": "application/wasm",
                 ".ttf": "font/ttf", ".icc": "application/vnd.iccprofile", ".map": "application/json",
                 ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8"}
# Actions any browser may send; everything else needs the admin cookie.
PLAYER_ACTIONS = {"join", "cast_vote", "guesser_advance", "toggle_ready", "set_profile", "request_reset", "parse_resume", "auto_tags", "review"}
_secret = None


def _admin_secret() -> bytes:
    """HMAC key for admin cookies, generated once into DATA_DIR so sessions survive restarts."""
    global _secret
    if _secret is None:
        path = os.path.join(accounts.DATA_DIR, "secret.key")
        try:
            with open(path, "rb") as f:
                _secret = f.read()
        except OSError:
            _secret = secrets.token_bytes(32)
            os.makedirs(accounts.DATA_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(_secret)
    return _secret


def make_admin_cookie() -> str:
    exp = str(int(time.time()) + 30 * 86400)
    sig = hmac.new(_admin_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def valid_admin_cookie(value: str) -> bool:
    exp, _, sig = (value or "").partition(".")
    good = hmac.new(_admin_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, good)


# ANSI terminal colors for live monitoring
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_MAGENTA = "\033[35m"
COLOR_CYAN = "\033[36m"
COLOR_RED = "\033[31m"


def get_lan_ip() -> str:
    """Detect local Wi-Fi / LAN IP address for QR code generation."""
    for iface in ("en0", "en1", "en2"):
        try:
            res = subprocess.check_output(
                ["ipconfig", "getifaddr", iface],
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            if res:
                return res
        except Exception:
            pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    return "127.0.0.1"


class GameHTTPRequestHandler(BaseHTTPRequestHandler):
    game_manager: GameManager = None
    server_port: int = 5050
    lan_ip: str = "127.0.0.1"

    def log_message(self, format: str, *args):
        code = str(args[1]) if len(args) > 1 else "200"
        color = COLOR_GREEN if code.startswith("2") else (COLOR_YELLOW if code.startswith("3") else COLOR_RED)
        ts = time.strftime("%H:%M:%S")
        sys.stdout.write(f"{COLOR_DIM}[{ts}]{COLOR_RESET} {COLOR_CYAN}[HTTP]{COLOR_RESET} {args[0]} -> {color}{code}{COLOR_RESET}\n")
        sys.stdout.flush()

        # Stream notable HTTP events into game_manager logs for live monitoring (avoid background polling spam)
        req_line = str(args[0]) if len(args) > 0 else ""
        if self.game_manager and not ("/api/state" in req_line or "/api/qr.svg" in req_line):
            lvl = "WARN" if (code.startswith("4") or code.startswith("5")) else "INFO"
            self.game_manager.log(f"HTTP: {req_line} -> {code}", level=lvl)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_svg(self, svg: str, status: int = 200):
        body = svg.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _is_admin(self) -> bool:
        jar = SimpleCookie(self.headers.get("Cookie", "") if self.headers else "")
        return "liars_admin" in jar and valid_admin_cookie(jar["liars_admin"].value)

    def _redirect(self, location: str, cookie: str = None):
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_static(self, rel: str, root: str = STATIC_DIR, types: Optional[Dict[str, str]] = None):
        path = os.path.normpath(os.path.join(root, unquote(rel)))
        ext = os.path.splitext(path)[1].lower()
        if not path.startswith(root + os.sep) or ext not in (types or STATIC_TYPES) or not os.path.isfile(path):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", (types or {}).get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def _cookie_attrs(self) -> str:
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        return f"Path=/; HttpOnly; SameSite=Lax{secure}"

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _get_base_url(self) -> str:
        # 1. Explicit environment variable override
        env_url = os.environ.get("PUBLIC_URL") or os.environ.get("BASE_URL")
        if env_url:
            return env_url.rstrip("/")

        # 2. Derive dynamically from Host and reverse proxy headers
        host_header = self.headers.get("Host") if self.headers else None
        if host_header:
            proto = self.headers.get("X-Forwarded-Proto")
            if not proto:
                proto = "https" if self.headers.get("X-Forwarded-Ssl") == "on" else "http"
            return f"{proto}://{host_header}".rstrip("/")

        # 3. Fallback to detected LAN IP / port
        return f"http://{self.lan_ip}:{self.server_port}"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        base_url = self._get_base_url()

        if path == "/":
            self._redirect("/join")
        elif path in ("/game", "/control", "/stages", "/stage-control"):
            self._redirect("/admin/control" if path != "/game" else "/admin")
        elif path == "/admin/login":
            self._send_html(get_admin_login_html())
        elif path in ("/admin", "/admin/", "/admin/control"):
            if not self._is_admin():
                self._redirect("/admin/login?next=" + path)
            elif path == "/admin/control":
                self._send_html(get_stage_control_html(self.server_port))
            else:
                self._send_html(get_admin_html(self.server_port, self.lan_ip, base_url=base_url))
        elif path.startswith("/static/"):
            self._send_static(path[len("/static/"):])
        elif path.startswith("/archive/"):
            self._send_static(path[len("/archive/"):], ARCHIVE_DIR, ARCHIVE_TYPES)
        elif path in ("/qr", "/lobby", "/lobby-qr"):
            self._send_html(get_qr_html(self.server_port, self.lan_ip, base_url=base_url))
        elif path in ("/join", "/play"):
            self._send_html(get_join_html(self.server_port))
        elif path in ("/display", "/player"):
            self._send_html(get_display_html(self.server_port))
        elif path == "/api/qr.svg":
            default_url = f"{base_url}/join"
            target_url = query.get("url", [default_url])[0]
            svg = generate_qr_svg(target_url, bg="", logo=LOGO_24)
            self._send_svg(svg)
        elif path == "/api/state":
            is_admin = query.get("role", ["player"])[0] == "admin"
            if is_admin and not self._is_admin():
                self._send_json({"error": "Admin login required."}, status=401)
                return
            player_id = query.get("player_id", [None])[0]
            token = query.get("token", [None])[0]
            state = self.game_manager.get_state(is_admin=is_admin, player_id=player_id, token=token)
            self._send_json(state)
        elif path == "/api/reviews":
            if not self._is_admin():
                self._send_json({"error": "Admin only"}, status=403)
                return
            self._send_json({"reviews": accounts.reviews()})
        elif path == "/api/leaderboard":
            self._send_json({"leaderboard": accounts.leaderboard()})
        elif path == "/health":
            self._send_json({
                "status": "ok",
                "game": "one-of-these-people-is-not-lying",
                "lan_ip": self.lan_ip,
                "port": self.server_port
            })
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/admin/logout":
            self._redirect("/admin/login", cookie=f"liars_admin=; Max-Age=0; {self._cookie_attrs()}")
        elif parsed.path == "/api/admin/login":
            length = int(self.headers.get("Content-Length", 0) or 0)
            form = parse_qs(self.rfile.read(min(length, 4096)).decode("utf-8", "replace"))
            user = form.get("username", [""])[0]
            pw = form.get("password", [""])[0]
            nxt = form.get("next", ["/admin"])[0]
            nxt = nxt if nxt in ("/admin", "/admin/control") else "/admin"
            if hmac.compare_digest(user.encode(), ADMIN_USER.encode()) & hmac.compare_digest(pw.encode(), ADMIN_PASS.encode()):
                self._redirect(nxt, cookie=f"liars_admin={make_admin_cookie()}; Max-Age={30 * 86400}; {self._cookie_attrs()}")
            else:
                time.sleep(1)  # slow down guessing
                self._redirect(f"/admin/login?error=1&next={nxt}")
        elif parsed.path == "/api/action":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json({"error": "Missing request body"}, status=400)
                return
            if content_length > 8_000_000:  # a 5 MB resume PDF, base64-encoded
                self._send_json({"error": "Request too large."}, status=413)
                return

            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception as e:
                self._send_json({"error": f"Invalid JSON: {e}"}, status=400)
                return

            action = payload.get("action")
            self._handle_action(action, payload)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_action(self, action: str, payload: dict):
        game = self.game_manager
        ts = time.strftime("%H:%M:%S")

        sys.stdout.write(f"{COLOR_DIM}[{ts}]{COLOR_RESET} {COLOR_MAGENTA}[ACTION]{COLOR_RESET} {COLOR_BOLD}{action}{COLOR_RESET}\n")
        sys.stdout.flush()

        added_player = None
        is_admin = self._is_admin()
        if action not in PLAYER_ACTIONS and not is_admin:
            self._send_json({"error": "Admin login required."}, status=401)
            return
        token = payload.get("token")
        if action in ("cast_vote", "guesser_advance", "toggle_ready", "set_profile", "parse_resume", "auto_tags", "review") and not is_admin:
            pid = payload.get("voter_id" if action == "cast_vote" else "player_id", "")
            if not game.player_for_token(pid, token):
                self._send_json({"error": "Your session expired. Log back in from the join page."}, status=403)
                return

        game.touch()
        extra = {}
        if action == "join":
            added_player, err = game.join(payload.get("name", ""), payload.get("password", ""),
                                        bool(payload.get("permanent")), payload.get("token", ""),
                                        str(payload.get("new_password") or ""))
            if err:
                self._send_json({"error": err, "need_new_password": err == NEED_NEW_PASSWORD}, status=403)
                return
            token = added_player["token"]
        elif action == "request_reset":
            if accounts.request_reset(str(payload.get("name") or "")):
                game.log(f"Password reset requested: {payload.get('name')}", level="ACTION")
            # same answer either way: don't reveal which names have accounts
            self._send_json({"ok": True})
            return
        elif action == "reset_password":
            temp = accounts.reset_password(payload.get("account_id", ""))
            if not temp:
                self._send_json({"error": "Unknown account."}, status=400)
                return
            game.log("Admin reset a player's password.", level="ACTION")
            extra["temp_password"] = temp
        elif action == "parse_resume":
            try:
                data = base64.b64decode(str(payload.get("pdf") or ""), validate=True)
                if len(data) > resume.MAX_PDF:
                    raise ValueError("That PDF is over 5 MB.")
                extra["draft"] = resume.draft_profile(resume.pdf_text(data), packs.all_tags())
            except ValueError as e:
                self._send_json({"error": str(e) or "That file isn't a PDF."}, status=400)
                return
            except Exception as e:
                game.log(f"Resume parsing failed: {e}", level="WARN")
                self._send_json({"error": "The resume reader is offline right now. Try again later."}, status=503)
                return
        elif action == "review":
            err = game.add_review(game.player_for_token(payload.get("player_id", ""), token) or {}, payload.get("score"), payload.get("text"))
            if err:
                self._send_json({"error": err}, status=400)
                return
        elif action == "auto_tags":
            p = game.player_for_token(payload.get("player_id", ""), token) or {}
            text = str(payload.get("expertise") or p.get("expertise") or "").strip()
            if not text:
                self._send_json({"error": "Write a few lines about your expertise first."}, status=400)
                return
            try:
                extra["tags"] = resume.suggest_tags(text[:600], packs.all_tags())
            except Exception as e:
                game.log(f"Auto tags failed: {e}", level="WARN")
                self._send_json({"error": "The tag helper is offline right now. Try again later."}, status=503)
                return
        elif action == "new_topics":
            game.new_topics(bool(payload.get("record_old")))
        elif action == "end_game":
            game.end_game()
        elif action == "set_setting":
            if not accounts.set_setting(payload.get("name", ""), payload.get("value")):
                self._send_json({"error": "Unknown setting."}, status=400)
                return
            game.log(f"Setting {payload.get('name')} = {accounts.settings().get(payload.get('name'))}", level="ACTION")
        elif action == "delete_account":
            accounts.delete_account(payload.get("account_id", ""))
        elif action == "clear_account_history":
            accounts.clear_user_history(payload.get("account_id", ""))
        elif action == "set_phase":
            target_phase = payload.get("phase", "lobby")
            if game.phase == "reveal" and target_phase in ("setup", "questioning", "voting"):
                self._send_json({"error": f"Round {game.round_number} has completed. Cannot return to {target_phase}. Please start a new round or terminate game and return to lobby."}, status=400)
                return
            if game.phase == "lobby" and target_phase in ("setup", "questioning", "voting", "reveal"):
                valid, err_msg, counts = game.check_role_requirements()
                if not valid:
                    self._send_json({"error": err_msg, "role_counts": counts}, status=400)
                    return
            success = game.set_phase(target_phase)
            if not success and target_phase != game.phase:
                valid, err_msg, counts = game.check_role_requirements()
                self._send_json({"error": err_msg or f"Failed to switch stage to {target_phase}", "role_counts": counts}, status=400)
                return
        elif action == "next_phase":
            if game.phase == "reveal":
                self._send_json({"error": "Round has completed. Advance is disabled. Please start a new round or terminate game and return to lobby."}, status=400)
                return
            if game.phase == "lobby":
                valid, err_msg, counts = game.check_role_requirements()
                if not valid:
                    self._send_json({"error": err_msg, "role_counts": counts}, status=400)
                    return
            game.next_phase()
            if game.phase == "lobby":
                valid, err_msg, counts = game.check_role_requirements()
                if not valid:
                    self._send_json({"error": err_msg, "role_counts": counts}, status=400)
                    return
        elif action == "add_player":
            added_player = game.add_player(payload.get("name", ""), player_id=payload.get("player_id"))
        elif action == "sync_player":
            added_player = game.sync_player(payload.get("player_id", ""), payload.get("name", ""))
        elif action == "remove_player":
            game.remove_player(payload.get("player_id", ""))
        elif action == "set_role":
            game.set_player_role(payload.get("player_id", ""), payload.get("role", "liar"), is_voter=payload.get("is_voter"))
        elif action == "set_guesser":
            p_ids = payload.get("player_ids")
            if p_ids and isinstance(p_ids, list):
                game.set_guessers(p_ids, voter_id=payload.get("voter_id"))
            else:
                game.set_player_role(payload.get("player_id", ""), "guesser", is_voter=payload.get("is_voter", True))
        elif action == "set_guessers":
            game.set_guessers(payload.get("player_ids", []), voter_id=payload.get("voter_id"))
        elif action == "set_truth_teller":
            p_ids = payload.get("player_ids")
            if p_ids and isinstance(p_ids, list):
                game.set_truth_tellers(p_ids)
            else:
                game.set_player_role(payload.get("player_id", ""), "truth_teller")
        elif action == "set_truth_tellers":
            game.set_truth_tellers(payload.get("player_ids", []))
        elif action == "set_role_counts":
            game.set_role_counts(payload.get("guesser_count", 1), payload.get("truth_teller_count", 1), apply_now=payload.get("apply_now", True))
        elif action == "set_role_mode":
            if not game.set_role_mode(payload.get("mode", "")):
                self._send_json({"error": "Unknown role mode."}, status=400)
                return
        elif action == "set_profile":
            tags = payload.get("tags")
            if not isinstance(tags, list) or not game.set_profile(payload.get("player_id", ""), tags, str(payload.get("expertise") or "")):
                self._send_json({"error": "Could not save your interests."}, status=400)
                return
        elif action == "toggle_ready":
            if not game.toggle_ready(payload.get("player_id", "")):
                self._send_json({"error": "Not ready to start yet."}, status=400)
                return
        elif action == "set_voting_guesser":
            game.set_voting_guesser(payload.get("player_id", ""))
        elif action == "randomize_roles":
            game.randomize_roles()
        elif action == "set_packs":
            if not game.set_packs(payload.get("pack_ids", [])):
                self._send_json({"error": "Select at least one existing pack."}, status=400)
                return
        elif action == "clear_topic_history":
            game.clear_topic_history()
        elif action == "cast_vote":
            success = game.cast_vote(
                payload.get("voter_id", ""),
                target_id=payload.get("target_id"),
                target_ids=payload.get("target_ids")
            )
            if not success:
                self._send_json({"error": "Only the designated voting guesser can cast a vote for valid suspect(s)!"}, status=403)
                return
        elif action == "guesser_advance":
            success = game.guesser_advance(payload.get("player_id", ""))
            if not success:
                self._send_json({"error": "Only the Guesser can advance the game stages!"}, status=403)
                return
        elif action == "reveal":
            game.reveal_and_score()
        elif action == "next_round":
            valid, err_msg, counts = game.check_role_requirements()
            if not valid:
                self._send_json({"error": err_msg, "role_counts": counts}, status=400)
                return
            game.next_round()
        elif action == "reset_game":
            game.reset_game()
        elif action == "clear_logs":
            game.clear_logs()
        elif action == "adjust_score":
            game.adjust_score(payload.get("player_id", ""), payload.get("delta", 0))
        else:
            self._send_json({"error": f"Unknown action: {action}"}, status=400)
            return

        me = added_player["id"] if added_player else payload.get("voter_id") or payload.get("player_id")
        state = game.get_state(is_admin=is_admin, player_id=me, token=token)
        if added_player:
            state["joined_player_id"] = added_player["id"]
            state["joined_player_name"] = added_player["name"]
            state["token"] = added_player.get("token")
        self._send_json({**state, **extra})


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Check if the given port is currently bound and in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return False
        except OSError:
            return True


def kill_process_on_port(port: int, max_wait_seconds: float = 3.0) -> bool:
    """Find any process currently listening on the port and terminate it to free the port."""
    current_pid = os.getpid()
    pids = set()

    for cmd in (["lsof", "-ti", f":{port}"], ["/usr/sbin/lsof", "-ti", f":{port}"]):
        try:
            res = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            for line in res.split():
                try:
                    pid = int(line)
                    if pid != current_pid and pid > 0:
                        pids.add(pid)
                except ValueError:
                    pass
            if pids:
                break
        except Exception:
            pass

    if not pids:
        try:
            res = subprocess.check_output(["fuser", f"{port}/tcp"], text=True, stderr=subprocess.DEVNULL).strip()
            for line in res.split():
                try:
                    pid = int(line)
                    if pid != current_pid and pid > 0:
                        pids.add(pid)
                except ValueError:
                    pass
        except Exception:
            pass

    if not pids:
        return False

    for pid in pids:
        ts = time.strftime("%H:%M:%S")
        sys.stdout.write(f"{COLOR_DIM}[{ts}]{COLOR_RESET} {COLOR_YELLOW}[SERVER] Port {port} is occupied by previous session (PID {pid}). Terminating old session to start new one...{COLOR_RESET}\n")
        sys.stdout.flush()
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    # Wait for process to exit and port to be released
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        if not is_port_in_use(port):
            return True
        time.sleep(0.1)

    # Force kill with SIGKILL if still occupying port
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    deadline = time.time() + 1.5
    while time.time() < deadline:
        if not is_port_in_use(port):
            return True
        time.sleep(0.1)

    return not is_port_in_use(port)


def find_free_port(start_port: int = 5050, max_attempts: int = 20) -> int:
    """Ensure start_port is available by terminating any stale session occupying it."""
    if is_port_in_use(start_port):
        kill_process_on_port(start_port)
    return start_port


def create_server(host: str = "0.0.0.0", port: int = 5050, game_manager: GameManager = None) -> Tuple[ThreadingHTTPServer, int, str]:
    if game_manager is None:
        game_manager = GameManager()

    lan_ip = get_lan_ip()

    # The port must not change! If port 5050 is in use, terminate previous session to take over.
    if is_port_in_use(port, host=host):
        kill_process_on_port(port)

    GameHTTPRequestHandler.game_manager = game_manager
    GameHTTPRequestHandler.server_port = port
    GameHTTPRequestHandler.lan_ip = lan_ip

    game_manager.log(f"HTTP Server listening on port {port} (LAN IP: {lan_ip})", level="INFO")

    try:
        server = ThreadingHTTPServer((host, port), GameHTTPRequestHandler)
    except OSError as e:
        # If still busy, do an aggressive kill attempt and retry once more
        ts = time.strftime("%H:%M:%S")
        sys.stdout.write(f"{COLOR_DIM}[{ts}]{COLOR_RESET} {COLOR_RED}[SERVER] Port {port} still busy ({e}). Force terminating lingering sessions on port {port}...{COLOR_RESET}\n")
        sys.stdout.flush()
        kill_process_on_port(port, max_wait_seconds=2.0)
        time.sleep(0.2)
        server = ThreadingHTTPServer((host, port), GameHTTPRequestHandler)

    return server, port, lan_ip

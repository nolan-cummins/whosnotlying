import json
import src.accounts as accounts
from src.game import GameManager, find_topic_data
from tests.test_server import make_mock_handler


def _post(gm, payload, admin=False):
    h = make_mock_handler("POST", "/api/action", body=json.dumps(payload).encode(), gm=gm, admin=admin)
    h.do_POST()
    status = h.send_response.call_args[0][0] if h.send_response.call_args else 200
    return status, json.loads(h.wfile.getvalue() or b"{}")


def _get(gm, path, admin=False):
    h = make_mock_handler("GET", path, gm=gm, admin=admin)
    h.do_GET()
    return h


def test_admin_pages_and_actions_need_login():
    gm = GameManager()
    h = _get(gm, "/")
    assert h.send_header.call_args_list[0][0] == ("Location", "/join")
    h = _get(gm, "/admin")
    assert h.send_header.call_args_list[0][0][1].startswith("/admin/login")
    assert "Admin Console" in _get(gm, "/admin", admin=True).wfile.getvalue().decode()
    assert _get(gm, "/api/state?role=admin").send_response.call_args[0][0] == 401
    assert _post(gm, {"action": "reset_game"})[0] == 401
    assert _post(gm, {"action": "add_player", "name": "X"})[0] == 401


def test_admin_login_sets_cookie_and_rejects_bad_password(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    gm = GameManager()
    for pw, ok in (("wrong", False), ("notthepassword", True)):
        h = make_mock_handler("POST", "/api/admin/login", body=f"username=admin&password={pw}".encode(), gm=gm, admin=False)
        h.do_POST()
        hdrs = dict(c[0] for c in h.send_header.call_args_list)
        assert ("Set-Cookie" in hdrs) == ok
        assert hdrs["Location"] == ("/admin" if ok else "/admin/login?error=1&next=/admin")


def test_player_token_gates_private_state_and_votes():
    gm = GameManager()
    toks = {}
    for n in ("Ann", "Ben", "Cy", "Dee"):
        status, data = _post(gm, {"action": "join", "name": n})
        assert status == 200 and data["token"]
        toks[data["joined_player_id"]] = data["token"]
        assert "logs" not in data or data["logs"] == []  # players never get the admin view
    pid = next(iter(toks))
    assert gm.get_state(is_admin=False, player_id=pid)["my_info"] is None
    assert gm.get_state(is_admin=False, player_id=pid, token=toks[pid])["my_info"]["id"] == pid
    # Someone else can't take the name, or vote as the guesser
    assert _post(gm, {"action": "join", "name": "ann"})[0] == 403
    gm.set_phase("voting", force=True)
    voter = gm.voting_guesser_id
    assert _post(gm, {"action": "cast_vote", "voter_id": voter, "target_id": gm.truth_teller_ids[0]})[0] == 403
    assert _post(gm, {"action": "cast_vote", "voter_id": voter, "target_id": gm.truth_teller_ids[0], "token": toks[voter]})[0] == 200


def test_temp_password_relogin_and_reset_signs_out_temps():
    gm = GameManager()
    p, _ = gm.join("Temp", password="pw12")
    assert gm.join("Temp", password="nope") == (None, "That name is taken. Enter its password to log back in.")
    assert gm.join("Temp", password="pw12")[0] is p
    perm, _ = gm.join("Keeper", password="secret", permanent=True)
    gm.reset_game()
    assert [x["name"] for x in gm.players] == ["Keeper"]


def test_permanent_account_history_blocks_topics_and_toggle():
    gm = GameManager()
    for n in ("A", "B", "C"):
        gm.join(n)
    perm, _ = gm.join("Vet", password="secret", permanent=True)
    assert gm.join("Vet2", password="ab", permanent=True) == (None, "Permanent accounts need a password (4+ characters).")
    gm.set_phase("questioning", force=True)
    acct = perm["account_id"]
    seen = accounts.blocked_topics([acct])
    assert len(seen) == 3  # three suspects' statements were heard

    # A new game later, global history off: only Vet's own history blocks topics
    accounts.set_setting("use_global", False)
    gm2 = GameManager()
    for n in ("X", "Y", "Z"):
        gm2.join(n)
    assert gm2.join("Vet", password="wrong")[1] == "A saved account uses that name. Wrong password."
    gm2.join("Vet", password="secret")
    for _ in range(20):
        gm2.assign_round_roles()
        dealt = {find_topic_data(p["topic"])["id"] for p in gm2.players if p.get("topic")}
        assert not dealt & seen
    accounts.set_setting("use_user", False)
    assert gm2._blocked() == set(gm2.used_topic_ids)


def test_lying_facts_toggle_reaches_only_liars():
    gm = GameManager()
    toks = {}
    for n in ("A", "B", "C", "D"):
        p, _ = gm.join(n)
        toks[p["id"]] = p["token"]
    liar = next(p for p in gm.players if p["role"] == "liar")
    t = find_topic_data(liar["topic"])
    t_lie = next(l for l in t["lies"] if l["text"] == liar["statement"])
    t_lie["facts"] = ["grounding fact"]  # library() copies are shallow: this edits the cached pack
    me = lambda: gm.get_state(is_admin=False, player_id=liar["id"], token=toks[liar["id"]])["my_info"]
    assert me()["lie_facts"] == []
    accounts.set_setting("lying_facts", True)
    assert me()["lie_facts"] == ["grounding fact"]
    assert all("lie_facts" not in p for p in gm.get_state(is_admin=False)["players"])


def test_view_used_archive_survives_restart_and_reset():
    gm = GameManager()
    for n in ("A", "B", "C"):
        gm.join(n)
    gm.set_phase("questioning", force=True)
    n = len(gm.used_statements)
    assert n == 2  # two suspects' statements this round
    gm.reset_game()
    assert len(GameManager().used_statements) == n  # a restarted server still has them
    gm.clear_topic_history()
    assert GameManager().used_statements == []


def test_forgot_password_reset_flow():
    gm = GameManager()
    assert _post(gm, {"action": "join", "name": "Ann", "password": "old1", "permanent": True})[0] == 200
    gm.players = []  # Ann's phone lost the session and the lobby moved on
    assert _post(gm, {"action": "request_reset", "name": "ann"})[1] == {"ok": True}
    assert _post(gm, {"action": "request_reset", "name": "nobody"})[1] == {"ok": True}  # no account enumeration
    acct = next(a for a in accounts.list_accounts() if a["name"] == "Ann")
    assert acct["reset_requested"]
    assert _post(gm, {"action": "reset_password", "account_id": acct["id"]})[0] == 401
    temp = _post(gm, {"action": "reset_password", "account_id": acct["id"]}, admin=True)[1]["temp_password"]
    assert _post(gm, {"action": "join", "name": "Ann", "password": "old1"})[0] == 403
    st, body = _post(gm, {"action": "join", "name": "Ann", "password": temp})
    assert st == 403 and body["need_new_password"]
    assert _post(gm, {"action": "join", "name": "Ann", "password": temp, "new_password": "new1"})[0] == 200
    gm.players = []
    assert _post(gm, {"action": "join", "name": "Ann", "password": "new1"})[0] == 200
    assert not next(a for a in accounts.list_accounts() if a["name"] == "Ann")["reset_requested"]


def test_end_game_books_winner_and_idle_timeout():
    gm = GameManager()
    for n in ("Ann", "Bob", "Cy"):
        _post(gm, {"action": "join", "name": n, "password": "pw12", "permanent": True})
    gm.players[0]["score"], gm.players[1]["score"] = 5, 2
    _post(gm, {"action": "end_game"}, admin=True)
    board = {r["name"]: r for r in json.loads(_get(gm, "/api/leaderboard").wfile.getvalue())["leaderboard"]}
    assert (board["Ann"]["wins"], board["Ann"]["games"], board["Bob"]["wins"], board["Bob"]["games"]) == (1, 1, 0, 1)
    assert len(gm.players) == 3 and all(p["score"] == 0 for p in gm.players)  # admin end keeps who's in the room
    gm.players[2]["score"] = 1
    gm.last_activity -= 3601
    gm.get_state(is_admin=False)
    assert gm.players == []  # an hour of silence: everyone is signed out, /join starts a new lobby
    assert {r["name"]: (r["wins"], r["games"]) for r in accounts.leaderboard()} == {"Ann": (1, 2), "Bob": (0, 2), "Cy": (1, 2)}


def test_roles_and_topics_are_separate_buttons():
    gm = GameManager()
    for n in "ABCDE":
        gm.add_player(n)
    gm.assign_round_roles()
    roles = {p["id"]: p["role"] for p in gm.players}
    topics = {p["id"]: p["topic"] for p in gm.players}
    gm.new_topics(record_old=True)
    assert {p["id"]: p["role"] for p in gm.players} == roles
    assert all(p["topic"] != topics[p["id"]] for p in gm.players if p["role"] != "guesser")
    assert len(accounts.global_keys()) == 4  # the 4 dropped statements count as heard
    topics = {p["id"]: p["topic"] for p in gm.players}
    for _ in range(5):
        gm.randomize_roles()
        kept = [p for p in gm.players if p["role"] != "guesser" and topics[p["id"]]]
        assert all(p["topic"] == topics[p["id"]] for p in kept)  # trivia topics have both sides: kept
        topics = {p["id"]: p["topic"] for p in gm.players}


def test_sources_redacted_during_questioning():
    gm = GameManager()
    assert gm.set_packs(["phd-mode"])
    for n in "ABCDE":
        gm.add_player(n)
    gm.assign_round_roles()
    tt = next(p for p in gm.players if p["role"] == "truth_teller")
    liar = next(p for p in gm.players if p["role"] == "liar")
    me = lambda p: gm.get_state(is_admin=False, player_id=p["id"], token=p.setdefault("token", "t" + p["id"]))["my_info"]
    assert me(tt)["source"]["institution"]
    gm.set_phase("questioning", force=True)
    assert me(tt)["source"] == {"redacted": True} and "venue" not in me(liar)


def test_reviews_saved_tagged_and_validated():
    gm = GameManager()
    assert gm.set_packs(["phd-mode"])
    st, r = _post(gm, {"action": "join", "name": "Rae", "password": "pw123456", "permanent": True})
    assert st == 200
    for n in "BCDE":
        gm.add_player(n)
    gm.assign_round_roles()
    rae = next(p for p in gm.players if p["name"] == "Rae")
    base = {"action": "review", "player_id": rae["id"], "token": rae["token"]}
    for _ in range(50):  # make sure Rae is a suspect holding a statement (guessers hold none)
        if rae["role"] != "guesser":
            break
        assert _post(gm, {**base, "score": 5})[0] == 400
        gm.randomize_roles()
    assert rae["statement"]
    assert _post(gm, {**base, "score": 11, "text": "x"})[0] == 400
    assert _post(gm, {**base, "score": 7, "text": "word " * 101})[0] == 400
    assert _post(gm, {**base, "score": 7, "text": "Clear, but fact 2 is vague."})[0] == 200
    assert _post(gm, {**base, "score": 3})[0] == 200  # several reviews allowed
    assert _post(gm, {"action": "review", "player_id": rae["id"], "token": "wrong", "score": 5})[0] == 403
    rows = accounts.reviews()
    assert [x["score"] for x in rows] == [3, 7]
    assert rows[1]["account_id"] and rows[1]["player_name"] == "Rae" and rows[1]["statement"] == rae["statement"]
    assert rows[1]["topic_id"].startswith("phd-mode:") and rows[1]["facts"]
    assert _get(gm, "/api/reviews").send_response.call_args[0][0] == 403
    assert json.loads(_get(gm, "/api/reviews", admin=True).wfile.getvalue())["reviews"][0]["score"] == 3

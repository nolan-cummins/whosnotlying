"""
Unit tests for HTTP server handlers using mock streams (no network required).
"""

import io
import json
from unittest.mock import MagicMock
from src.game import GameManager
from tests.test_game import _tok
from src.server import GameHTTPRequestHandler, make_admin_cookie


def make_mock_handler(method: str, path: str, body: bytes = b"", gm: GameManager = None, admin: bool = True):
    if gm is not None:
        GameHTTPRequestHandler.game_manager = gm
    else:
        GameHTTPRequestHandler.game_manager = GameManager(seed_samples=True)
    GameHTTPRequestHandler.server_port = 5050
    GameHTTPRequestHandler.lan_ip = "192.168.0.100"

    handler = GameHTTPRequestHandler.__new__(GameHTTPRequestHandler)
    handler.command = method
    handler.path = path
    handler.request_version = "HTTP/1.1"
    handler.headers = {"Content-Length": str(len(body))}
    if admin:
        handler.headers["Cookie"] = "liars_admin=" + make_admin_cookie()
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.send_error = MagicMock()
    return handler


def test_gm_dashboard_get():
    handler = make_mock_handler("GET", "/admin")
    handler.do_GET()
    output = handler.wfile.getvalue().decode("utf-8")
    assert "Admin Console" in output
    assert "One of These People Is Not Lying" in output


def test_qr_page_get():
    handler = make_mock_handler("GET", "/qr")
    handler.do_GET()
    output = handler.wfile.getvalue().decode("utf-8")
    assert "Scan to Join Game" in output
    assert "Join Lobby - QR Code" in output


def test_join_page_get():
    handler = make_mock_handler("GET", "/join")
    handler.do_GET()
    output = handler.wfile.getvalue().decode("utf-8")
    assert "Join The Game" in output


def test_qr_svg_api():
    handler = make_mock_handler("GET", "/api/qr.svg?url=http://192.168.0.100:5050/join")
    handler.do_GET()
    output = handler.wfile.getvalue().decode("utf-8")
    assert "<svg" in output
    assert "</svg>" in output


def test_api_state_gm():
    handler = make_mock_handler("GET", "/api/state?role=admin")
    handler.do_GET()
    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert "truth_teller_id" in data
    assert "guesser_id" in data
    assert "used_topics_count" in data
    assert "total_topics_count" in data


def test_api_action_sync_player():
    payload = json.dumps({"action": "sync_player", "player_id": "test_id_999", "name": "SyncedPlayer"}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload)
    handler.do_POST()
    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    matching = [p for p in data["players"] if p["id"] == "test_id_999"]
    assert len(matching) == 1
    assert matching[0]["name"] == "SyncedPlayer"


def test_api_action_clear_topic_history():
    payload = json.dumps({"action": "clear_topic_history"}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload)
    handler.do_POST()
    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data["used_topics_count"] == 0


def test_api_action_set_role():
    # Setup players
    handler = make_mock_handler("GET", "/api/state?role=admin")
    handler.do_GET()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    players = data["players"]
    target_id = players[1]["id"]

    # Assign target_id to truth_teller
    payload = json.dumps({"action": "set_role", "player_id": target_id, "role": "truth_teller"}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload)
    handler.do_POST()
    output = handler.wfile.getvalue().decode("utf-8")
    res = json.loads(output)
    assert res["truth_teller_id"] == target_id
    tt_player = next(p for p in res["players"] if p["id"] == target_id)
    assert tt_player["is_truth_teller"] is True
    assert tt_player["detailed_description"] is not None

    # Assign target_id to guesser
    payload2 = json.dumps({"action": "set_role", "player_id": target_id, "role": "guesser"}).encode("utf-8")
    handler2 = make_mock_handler("POST", "/api/action", body=payload2)
    handler2.do_POST()
    output2 = handler2.wfile.getvalue().decode("utf-8")
    res2 = json.loads(output2)
    assert res2["guesser_id"] == target_id
    guesser_player = next(p for p in res2["players"] if p["id"] == target_id)
    assert guesser_player["is_guesser"] is True


def test_api_action_set_guesser_and_truth_teller_endpoints():
    handler = make_mock_handler("GET", "/api/state?role=admin")
    handler.do_GET()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    players = data["players"]
    p_a = players[0]["id"]
    p_b = players[1]["id"]

    # Dedicated Guesser selection
    payload_g = json.dumps({"action": "set_guesser", "player_id": p_a}).encode("utf-8")
    handler_g = make_mock_handler("POST", "/api/action", body=payload_g)
    handler_g.do_POST()
    res_g = json.loads(handler_g.wfile.getvalue().decode("utf-8"))
    assert res_g["guesser_id"] == p_a

    # Dedicated Truth Teller selection
    payload_tt = json.dumps({"action": "set_truth_teller", "player_id": p_b}).encode("utf-8")
    handler_tt = make_mock_handler("POST", "/api/action", body=payload_tt)
    handler_tt.do_POST()
    res_tt = json.loads(handler_tt.wfile.getvalue().decode("utf-8"))
    assert res_tt["truth_teller_id"] == p_b
    tt_player = next(p for p in res_tt["players"] if p["id"] == p_b)
    assert tt_player["is_truth_teller"] is True
    assert tt_player["topic"] is not None
    assert tt_player["statement"] is not None
    assert tt_player["detailed_description"] is not None


def test_api_action_randomize_roles_picks_unused_topics():
    handler = make_mock_handler("GET", "/api/state?role=admin")
    handler.do_GET()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    used_before = data["used_topics_count"]

    payload = json.dumps({"action": "randomize_roles"}).encode("utf-8")
    handler_rand = make_mock_handler("POST", "/api/action", body=payload)
    handler_rand.do_POST()
    res = json.loads(handler_rand.wfile.getvalue().decode("utf-8"))

    # Every suspect has a topic
    for p in res["players"]:
        if p["id"] != res["guesser_id"]:
            assert p["topic"] is not None and len(p["topic"]) > 0
            assert p["statement"] is not None and len(p["statement"]) > 0

    assert res["guesser_id"] is not None
    assert res["truth_teller_id"] is not None
    assert res["guesser_id"] != res["truth_teller_id"]


def test_player_client_topics_always_present():
    handler = make_mock_handler("GET", "/api/state?role=admin")
    handler.do_GET()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    suspects = [p for p in data["players"] if p["id"] != data["guesser_id"]]
    assert len(suspects) > 0

    # Query player state for a suspect
    s_id = suspects[0]["id"]
    handler_p = make_mock_handler("GET", f"/api/state?role=player&player_id={s_id}&token={_tok(handler.game_manager, s_id)}", gm=handler.game_manager)
    handler_p.do_GET()
    p_data = json.loads(handler_p.wfile.getvalue().decode("utf-8"))

    # Topic in my_info
    assert p_data["my_info"] is not None
    assert p_data["my_info"]["topic"] is not None and len(p_data["my_info"]["topic"]) > 0

    # Suspect topics in public roster
    for p in p_data["players"]:
        if not p["is_guesser"]:
            assert p["topic"] is not None and len(p["topic"]) > 0


def test_setup_and_secrets_phase_transitions_reveals_topics():
    gm = GameManager(seed_samples=True)
    gm.set_phase("lobby")

    # Transition to setup phase
    gm.set_phase("setup")
    assert gm.phase == "setup"

    # Truth teller client state
    tt_id = gm.truth_teller_id
    handler_tt = make_mock_handler("GET", f"/api/state?role=player&player_id={tt_id}&token={_tok(gm, tt_id)}", gm=gm)
    handler_tt.do_GET()
    data_tt = json.loads(handler_tt.wfile.getvalue().decode("utf-8"))
    assert data_tt["phase"] == "setup"
    assert data_tt["my_info"]["role"] == "truth_teller"
    assert data_tt["my_info"]["topic"] is not None and len(data_tt["my_info"]["topic"]) > 0
    assert data_tt["my_info"]["statement"] is not None and len(data_tt["my_info"]["statement"]) > 0
    assert data_tt["my_info"]["detailed_description"] is not None and len(data_tt["my_info"]["detailed_description"]) > 0

    # Liar client state
    liar = next(p for p in gm.players if p["id"] not in (gm.truth_teller_id, gm.guesser_id))
    handler_liar = make_mock_handler("GET", f"/api/state?role=player&player_id={liar['id']}&token={_tok(gm, liar['id'])}", gm=gm)
    handler_liar.do_GET()
    data_liar = json.loads(handler_liar.wfile.getvalue().decode("utf-8"))
    assert data_liar["phase"] == "setup"
    assert data_liar["my_info"]["role"] == "liar"
    assert data_liar["my_info"]["topic"] is not None and len(data_liar["my_info"]["topic"]) > 0
    assert data_liar["my_info"]["statement"] is not None and len(data_liar["my_info"]["statement"]) > 0
    assert data_liar["my_info"]["detailed_description"] is None

    # Transition to questioning phase
    gm.set_phase("questioning")
    assert gm.phase == "questioning"
    handler_tt2 = make_mock_handler("GET", f"/api/state?role=player&player_id={tt_id}&token={_tok(gm, tt_id)}", gm=gm)
    handler_tt2.do_GET()
    data_tt2 = json.loads(handler_tt2.wfile.getvalue().decode("utf-8"))
    assert data_tt2["phase"] == "questioning"
    assert data_tt2["my_info"]["topic"] == data_tt["my_info"]["topic"]
    assert data_tt2["my_info"]["detailed_description"] == data_tt["my_info"]["detailed_description"]


def test_player_name_fallback_and_no_cache_headers():
    gm = GameManager(seed_samples=True)
    GameHTTPRequestHandler.game_manager = gm
    first_player = gm.players[0]
    p_name = first_player["name"]

    tok = gm.join(p_name)[0]["token"]  # an unclaimed (admin-added) player can be claimed by name
    handler = make_mock_handler("GET", f"/api/state?role=player&player_id=name:{p_name}&token={tok}", gm=gm, admin=False)
    handler.do_GET()

    # Check anti-cache headers
    headers_dict = {call[0][0]: call[0][1] for call in handler.send_header.call_args_list}
    assert "Cache-Control" in headers_dict
    assert "no-cache" in headers_dict["Cache-Control"]
    assert "no-store" in headers_dict["Cache-Control"]

    # Check fallback player matching
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert data["my_info"] is not None
    assert data["my_info"]["name"].lower() == p_name.lower()


def test_escape_html_present_in_join_template():
    handler = make_mock_handler("GET", "/join")
    handler.do_GET()
    html = handler.wfile.getvalue().decode("utf-8")
    assert "function escapeHtml" in html
    assert "escapeHtml(str)" in html


def test_api_action_guesser_advance():
    gm = GameManager(seed_samples=True)
    gm.set_phase("questioning")
    guesser_id = gm.guesser_id

    # Guesser advances to voting
    payload = json.dumps({"action": "guesser_advance", "player_id": guesser_id}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert data["phase"] == "voting"

    # Non-guesser fails to advance
    liar = next(p for p in gm.players if p["id"] != guesser_id)
    payload_bad = json.dumps({"action": "guesser_advance", "player_id": liar["id"]}).encode("utf-8")
    handler_bad = make_mock_handler("POST", "/api/action", body=payload_bad, gm=gm)
    handler_bad.do_POST()
    assert handler_bad.send_response.called or handler_bad.send_error.called


def test_gm_dashboard_masks_topics_by_default():
    handler = make_mock_handler("GET", "/admin")
    handler.do_GET()
    html = handler.wfile.getvalue().decode("utf-8")
    # Verify GM dashboard has button-controlled topic reveal functions
    assert "toggleTopic" in html
    assert "toggleAllTopics" in html
    assert "Show Topic" in html
    assert "Topic &amp; Summary Hidden" in html or "Topic & Summary Hidden" in html


def test_auto_reveal_via_server_vote_action():
    gm = GameManager(seed_samples=True)
    guesser_id = gm.guesser_id
    tt_id = gm.truth_teller_id

    payload = json.dumps({"action": "cast_vote", "voter_id": guesser_id, "target_id": tt_id}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))

    # Verify auto-reveal occurred
    assert data["phase"] == "reveal"
    assert "standings" in data
    assert len(data["standings"]) > 0
    assert "last_results" in data
    assert data["last_results"]["is_correct"] is True


def test_stage_controller_page_get():
    # Test both /control and /stages endpoints
    for path in ("/admin/control",):
        handler = make_mock_handler("GET", path)
        handler.do_GET()
        html = handler.wfile.getvalue().decode("utf-8")
        assert "Stage Controller" in html
        assert "Blind Host Participation" in html
        assert "Jump to Any Game Stage" in html
        assert "Advance to Next Stage" in html
        assert "ctrl-guesser-count" in html
        assert "ctrl-truth-count" in html
        assert "updateRoleCounts" in html
        assert "Role Quantities" in html
        # Zero spoilers guarantee: no player dossier or secret topics in template
        assert "admin-select-guesser" not in html
        assert "admin-select-tt" not in html
        assert "Secret Dossier" not in html


def test_auto_reveal_on_set_phase_reveal():
    gm = GameManager(seed_samples=True)
    assert gm.last_round_results is None
    # Transition to reveal via action
    payload = json.dumps({"action": "set_phase", "phase": "reveal"}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))

    assert data["phase"] == "reveal"
    assert data["last_results"] is not None
    assert len(data["standings"]) > 0


def test_all_clients_have_standings_components():
    from src.templates import get_join_html, get_display_html, get_qr_html, get_stage_control_html
    join_html = get_join_html(5050)
    display_html = get_display_html(5050)
    qr_html = get_qr_html(5050, "192.168.1.5")
    stage_html = get_stage_control_html(5050)

    # Player mobile client has standings in reveal & preview in join
    assert "join-standings-preview" in join_html
    assert "Current Standings" in join_html
    assert "Round" in join_html

    # Display has large standings scoreboard
    assert "Standings" in display_html
    assert "state.standings" in display_html

    # QR page has standings card for lobby monitoring
    assert "qr-standings-card" in qr_html

    # Stage control tab controls stages without spoiling secrets
    assert "Stage Controller" in stage_html
    assert "nextPhase" in stage_html
    assert "nextRound" in stage_html


def test_is_port_in_use_and_kill_process_on_port():
    import socket
    import subprocess
    import sys
    import time
    from src.server import is_port_in_use, kill_process_on_port

    test_port = 5898
    assert not is_port_in_use(test_port)

    # Spawn a background process that listens on test_port
    code = f"""
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', {test_port}))
s.listen(1)
time.sleep(30)
"""
    proc = subprocess.Popen([sys.executable, "-c", code])
    try:
        # Wait until process is listening
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_port_in_use(test_port):
                break
            time.sleep(0.05)

        assert is_port_in_use(test_port), "Test process should be occupying test_port"

        # Kill process occupying test_port
        killed = kill_process_on_port(test_port, max_wait_seconds=2.0)
        assert killed is True
        assert not is_port_in_use(test_port), "Port should now be free"
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            pass


def test_create_server_preserves_port_and_kills_existing():
    import socket
    import subprocess
    import sys
    import time
    from src.server import create_server, is_port_in_use

    test_port = 5899

    # Spawn an old session process that occupies test_port
    code = f"""
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', {test_port}))
s.listen(1)
time.sleep(30)
"""
    proc = subprocess.Popen([sys.executable, "-c", code])
    try:
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if is_port_in_use(test_port):
                break
            time.sleep(0.05)

        assert is_port_in_use(test_port)

        # create_server should kill the old session and keep test_port (not test_port + 1)
        server, active_port, lan_ip = create_server(host="0.0.0.0", port=test_port)
        try:
            assert active_port == test_port, f"Expected port {test_port}, got {active_port}"
        finally:
            server.server_close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            pass


def test_api_action_set_role_counts():
    gm = GameManager(seed_samples=True)
    # Add players so counts are valid
    for i in range(5, 9):
        gm.add_player(f"ServerPlayer_{i}", player_id=f"sp_{i}")

    payload = json.dumps({"action": "set_role_counts", "guesser_count": 2, "truth_teller_count": 2, "apply_now": True}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()
    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data["target_guesser_count"] == 2
    assert data["target_truth_teller_count"] == 2
    assert len(data["guesser_ids"]) == 2
    assert len(data["truth_teller_ids"]) == 2


def test_api_action_set_voting_guesser():
    gm = GameManager(seed_samples=True)
    for i in range(5, 9):
        gm.add_player(f"ServerPlayer_{i}", player_id=f"sp_{i}")
    gm.set_role_counts(2, 2, apply_now=True)
    gm.assign_round_roles()

    voter_before = gm.voting_guesser_id
    consultant = next(gid for gid in gm.guesser_ids if gid != voter_before)

    # Set consultant as the new voting guesser
    payload = json.dumps({"action": "set_voting_guesser", "player_id": consultant}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()
    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data["voting_guesser_id"] == consultant
    assert data["guesser_id"] == consultant


def test_api_action_non_voting_guesser_vote_forbidden():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"ServerPlayer_{i}", player_id=f"sp_{i}")
    gm.set_role_counts(2, 1, apply_now=True)
    gm.assign_round_roles()

    voter_id = gm.voting_guesser_id
    consultant_id = next(gid for gid in gm.guesser_ids if gid != voter_id)
    tt_id = gm.truth_teller_ids[0]

    # Consultant attempts to vote -> should be rejected with 403
    payload_bad = json.dumps({"action": "cast_vote", "voter_id": consultant_id, "target_id": tt_id}).encode("utf-8")
    handler_bad = make_mock_handler("POST", "/api/action", body=payload_bad, gm=gm)
    handler_bad.do_POST()
    output_bad = handler_bad.wfile.getvalue().decode("utf-8")
    assert "error" in output_bad
    assert "voting guesser" in output_bad.lower()

    # Lead voter votes -> succeeds
    payload_good = json.dumps({"action": "cast_vote", "voter_id": voter_id, "target_id": tt_id}).encode("utf-8")
    handler_good = make_mock_handler("POST", "/api/action", body=payload_good, gm=gm)
    handler_good.do_POST()
    output_good = handler_good.wfile.getvalue().decode("utf-8")
    data = json.loads(output_good)
    assert data["phase"] == "reveal"
    assert data["last_results"]["is_correct"] is True


def test_gm_dashboard_has_role_count_inputs():
    from src.templates import get_admin_html
    html = get_admin_html(5050, "192.168.1.10")
    assert "admin-guesser-count" in html
    assert "admin-truth-count" in html
    assert "updateRoleCounts" in html
    assert "Lead Guesser (Designated Voter)" in html


def test_api_action_set_guessers_multi():
    gm = GameManager(seed_samples=True)
    for i in range(5, 9):
        gm.add_player(f"ServerPlayer_{i}", player_id=f"sp_{i}")

    p_ids = [p["id"] for p in gm.players]
    target_guessers = [p_ids[0], p_ids[1]]

    payload = json.dumps({
        "action": "set_guessers",
        "player_ids": target_guessers,
        "voter_id": target_guessers[1]
    }).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()

    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert set(data["guesser_ids"]) == set(target_guessers)
    assert data["voting_guesser_id"] == target_guessers[1]
    assert data["target_guesser_count"] == 2


def test_api_action_set_truth_tellers_multi():
    gm = GameManager(seed_samples=True)
    for i in range(5, 9):
        gm.add_player(f"ServerPlayer_{i}", player_id=f"sp_{i}")

    p_ids = [p["id"] for p in gm.players]
    target_tts = [p_ids[2], p_ids[3]]

    payload = json.dumps({
        "action": "set_truth_tellers",
        "player_ids": target_tts
    }).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()

    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert set(data["truth_teller_ids"]) == set(target_tts)
    assert data["target_truth_teller_count"] == 2


def test_gm_dashboard_has_multi_select_role_assignment_elements():
    from src.templates import get_admin_html
    html = get_admin_html(5050, "192.168.1.10")
    # Verify multi-select support elements & scripts in GM console
    assert "role-multi-select" in html
    assert "admin-guesser-select-holder" in html
    assert "admin-truth-select-holder" in html
    assert "onGuesserMultiChange" in html
    assert "onTruthTellerMultiChange" in html
    assert "chooseLeadVoter" in html
    assert "attachToggleBehavior" in html
    assert "admin-lead-voter-subcard" in html


def test_server_default_game_manager_boots_with_zero_players():
    gm = GameManager()
    assert len(gm.players) == 0
    assert gm.guesser_ids == []
    assert gm.voting_guesser_id is None
    assert gm.truth_teller_ids == []


def test_api_action_multi_truth_teller_voting():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"ServerPlayer_{i}", player_id=f"sp_{i}")
    gm.set_role_counts(1, 2, apply_now=True)
    gm.assign_round_roles()

    voter_id = gm.voting_guesser_id
    tt1 = gm.truth_teller_ids[0]
    tt2 = gm.truth_teller_ids[1]
    liar = next(p for p in gm.players if p["role"] == "liar")

    # 1. Full correct accusation via target_ids
    for p in gm.players:
        p["score"] = 0
    payload_correct = json.dumps({"action": "cast_vote", "voter_id": voter_id, "target_ids": [tt1, tt2]}).encode("utf-8")
    handler1 = make_mock_handler("POST", "/api/action", body=payload_correct, gm=gm)
    handler1.do_POST()
    data1 = json.loads(handler1.wfile.getvalue().decode("utf-8"))
    assert data1["phase"] == "reveal"
    assert data1["last_results"]["is_correct"] is True
    # Guesser gets +1, both truth tellers get +1, liar gets 0
    sc1 = data1["last_results"]["score_changes"]
    voter_name = next(p["name"] for p in gm.players if p["id"] == voter_id)
    tt1_name = next(p["name"] for p in gm.players if p["id"] == tt1)
    tt2_name = next(p["name"] for p in gm.players if p["id"] == tt2)
    assert sc1[voter_name] == 1
    assert sc1[tt1_name] == 1
    assert sc1[tt2_name] == 1
    assert sc1[liar["name"]] == 0

    # 2. Partial accusation (voter identifies tt1 and liar)
    for p in gm.players:
        p["score"] = 0
    gm.phase = "voting"
    payload_partial = json.dumps({"action": "cast_vote", "voter_id": voter_id, "target_ids": [tt1, liar["id"]]}).encode("utf-8")
    handler2 = make_mock_handler("POST", "/api/action", body=payload_partial, gm=gm)
    handler2.do_POST()
    data2 = json.loads(handler2.wfile.getvalue().decode("utf-8"))
    assert data2["last_results"]["is_correct"] is False
    sc2 = data2["last_results"]["score_changes"]
    # Guesser gets 0, tt1 and liar get +1 each, unpicked tt2 gets 0
    assert sc2[voter_name] == 0
    assert sc2[tt1_name] == 1
    assert sc2[liar["name"]] == 1
    assert sc2[tt2_name] == 0


def test_gm_dashboard_has_separate_display_for_true_and_false_statements_used():
    from src.templates import get_admin_html
    html = get_admin_html(5050, "192.168.1.10")

    # Verify Statement Used History card has been removed
    assert "statements-used-card" not in html
    assert "Statements Used History" not in html

    # Verify Topic History in Secret Dossier displays Truth and Lies separately
    assert "Topic History:" in html
    assert "used-truth-count" in html
    assert "total-truth-count" in html
    assert "used-lies-count" in html
    assert "total-lies-count" in html
    assert "used-topics-count" in html
    assert "total-topics-count" in html
    assert "Truth:" in html
    assert "Lies:" in html

    # Verify reset button and drawer toggle are present
    assert "clearTopicHistory" in html
    assert "toggleTopicHistoryDetails" in html
    assert "topic-history-drawer" in html
    assert "renderTopicHistoryDrawer" in html


def test_gm_dashboard_live_terminal_and_server_logs_card():
    from src.templates import get_admin_html
    html = get_admin_html(5050, "192.168.1.10")

    # Verify card element exists and has proper title and container
    assert "Live Terminal & Server Logs" in html
    assert 'id="logs-card"' in html
    assert 'id="logs-list"' in html
    assert 'id="logs-count"' in html

    # Verify log console styling exists
    assert ".logs-console" in html
    assert ".log-entry" in html
    assert ".log-badge" in html
    assert ".log-action" in html
    assert ".log-info" in html
    assert ".log-warn" in html

    # Verify JavaScript logic renders state.logs into logs-list
    assert 'logsContainer = document.getElementById("logs-list")' in html
    assert "state.logs" in html
    assert "logsUserScrolled" in html


def test_clear_logs_action():
    gm = GameManager(seed_samples=False)
    gm.log("Test log entry 1")
    gm.log("Test log entry 2")
    assert len(gm.logs) >= 3

    payload = json.dumps({"action": "clear_logs"}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload, gm=gm)
    handler.do_POST()

    output = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "logs" in output
    assert len(output["logs"]) == 1
    assert "cleared" in output["logs"][0]["message"].lower()


def test_server_log_message_records_notable_http():
    gm = GameManager(seed_samples=False)
    handler = make_mock_handler("GET", "/join", gm=gm)
    handler.log_message("%s", "GET /join HTTP/1.1", "200")

    logged_msgs = [l["message"] for l in gm.logs]
    assert any("HTTP: GET /join HTTP/1.1 -> 200" in m for m in logged_msgs)


def test_server_enforces_minimum_role_requirements_to_start():
    """
    Validates that the server API rejects starting the game (via set_phase or next_phase)
    with a 400 status code and helpful error message when the minimum requirement
    (at least 1 Guesser, 1 Truth Teller, 1 Liar) is not satisfied.
    """
    gm = GameManager(seed_samples=False)
    p1 = gm.add_player("Player 1")
    p2 = gm.add_player("Player 2")

    # 1. Only 2 players connected -> attempting to set phase to setup returns 400
    payload_setup = json.dumps({"action": "set_phase", "phase": "setup"}).encode("utf-8")
    handler = make_mock_handler("POST", "/api/action", body=payload_setup, gm=gm)
    handler.do_POST()

    handler.send_response.assert_called_with(400)
    data = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "error" in data
    assert "at least 1" in data["error"].lower()
    assert gm.phase == "lobby"

    # 2. next_phase from lobby with 2 players also returns 400
    payload_next = json.dumps({"action": "next_phase"}).encode("utf-8")
    handler2 = make_mock_handler("POST", "/api/action", body=payload_next, gm=gm)
    handler2.do_POST()

    handler2.send_response.assert_called_with(400)
    data2 = json.loads(handler2.wfile.getvalue().decode("utf-8"))
    assert "error" in data2
    assert gm.phase == "lobby"

    # 3. Add 3rd player, but configure roles as 2 Guessers and 1 Truth Teller (0 Liars)
    p3 = gm.add_player("Player 3")
    gm.set_role_counts(guesser_count=2, truth_teller_count=1)

    handler3 = make_mock_handler("POST", "/api/action", body=payload_setup, gm=gm)
    handler3.do_POST()

    handler3.send_response.assert_called_with(400)
    data3 = json.loads(handler3.wfile.getvalue().decode("utf-8"))
    assert "at least 1 liar" in data3["error"].lower()
    assert gm.phase == "lobby"

    # 4. Configure roles to 1 Guesser and 1 Truth Teller (leaving 1 Liar) -> Successfully starts!
    gm.set_role_counts(guesser_count=1, truth_teller_count=1)

    handler4 = make_mock_handler("POST", "/api/action", body=payload_setup, gm=gm)
    handler4.do_POST()

    handler4.send_response.assert_called_with(200)
    data4 = json.loads(handler4.wfile.getvalue().decode("utf-8"))
    assert data4["phase"] == "setup"
    assert gm.phase == "setup"


def test_server_blocks_advance_and_previous_phases_at_round_end():
    """
    Validates that at round end (reveal phase):
    - next_phase returns 400 error.
    - set_phase to setup, questioning, or voting returns 400 error.
    - next_round returns 200 and advances to setup.
    - reset_game returns 200 and terminates to lobby.
    """
    gm = GameManager(seed_samples=True)
    gm.set_phase("setup")
    gm.set_phase("voting")
    gm.set_phase("reveal")
    assert gm.phase == "reveal"

    # 1. next_phase during reveal is rejected with 400
    payload_next = json.dumps({"action": "next_phase"}).encode("utf-8")
    handler1 = make_mock_handler("POST", "/api/action", body=payload_next, gm=gm)
    handler1.do_POST()
    handler1.send_response.assert_called_with(400)
    data1 = json.loads(handler1.wfile.getvalue().decode("utf-8"))
    assert "error" in data1
    assert "completed" in data1["error"].lower() or "disabled" in data1["error"].lower()
    assert gm.phase == "reveal"

    # 2. set_phase back to questioning during reveal is rejected with 400
    payload_prev = json.dumps({"action": "set_phase", "phase": "questioning"}).encode("utf-8")
    handler2 = make_mock_handler("POST", "/api/action", body=payload_prev, gm=gm)
    handler2.do_POST()
    handler2.send_response.assert_called_with(400)
    data2 = json.loads(handler2.wfile.getvalue().decode("utf-8"))
    assert "error" in data2
    assert gm.phase == "reveal"

    # 3. next_round is allowed
    payload_nr = json.dumps({"action": "next_round"}).encode("utf-8")
    handler3 = make_mock_handler("POST", "/api/action", body=payload_nr, gm=gm)
    handler3.do_POST()
    handler3.send_response.assert_called_with(200)
    data3 = json.loads(handler3.wfile.getvalue().decode("utf-8"))
    assert data3["phase"] == "setup"
    assert gm.phase == "setup"
    assert gm.round_number == 2

    # Put back in reveal
    gm.set_phase("reveal")
    assert gm.phase == "reveal"

    # 4. reset_game terminates game and returns to lobby
    payload_reset = json.dumps({"action": "reset_game"}).encode("utf-8")
    handler4 = make_mock_handler("POST", "/api/action", body=payload_reset, gm=gm)
    handler4.do_POST()
    handler4.send_response.assert_called_with(200)
    data4 = json.loads(handler4.wfile.getvalue().decode("utf-8"))
    assert data4["phase"] == "lobby"
    assert gm.phase == "lobby"


def test_client_join_html_streamlined_mobile_presentation():
    from src.templates import get_join_html
    html = get_join_html(5050)

    # Clean mobile UI classes
    assert "player-bar" in html
    assert "team-banner" in html
    assert "goal-pill" in html
    assert "facts-drawer" in html
    assert "leaderboard-card" in html
    assert "leader-row" in html
    assert "verdict-card" in html
    assert "toggleDrawer" in html

    # Collapsible facts for phone readability & state persistence
    assert "<details" in html
    assert "<summary" in html
    assert "detailsFoldState" in html
    assert "recordToggle" in html
    assert "tt-facts-drawer" in html
    assert "lie-facts-drawer" in html
    assert "renderedHtml" in html

    # Overcrowded repetitive walls of text were removed
    assert "You have NOT been assigned any topic or statement" not in html
    assert "Interrogation & Deliberation in Progress" not in html
    assert "You have NO detailed facts description!" not in html
    assert "Consensus Deliberation Time" not in html
















def test_archive_serves_offline_copies_but_nothing_outside(tmp_path, monkeypatch):
    import src.server as srv
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4 x")
    (tmp_path / "secret.key").write_bytes(b"no")
    monkeypatch.setattr(srv, "ARCHIVE_DIR", str(tmp_path))
    h = make_mock_handler("GET", "/archive/paper.pdf")
    h.do_GET()
    assert h.send_response.call_args[0][0] == 200 and h.wfile.getvalue() == b"%PDF-1.4 x"
    assert ("Content-Type", "application/pdf") in [c[0] for c in h.send_header.call_args_list]
    for bad in ("/archive/secret.key", "/archive/../server.py", "/archive/%2e%2e/%2e%2e/etc/passwd"):
        h = make_mock_handler("GET", bad)
        h.do_GET()
        assert h.wfile.getvalue() != b"no" and h.send_error.call_args[0][0] == 404, bad

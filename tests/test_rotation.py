import random
from collections import Counter

from src import accounts
from src.game import GameManager


def _game(n, g=1, tt=1, fair=True):
    accounts.set_setting("fair_roles", fair)
    gm = GameManager()
    for i in range(n):
        gm.add_player(f"P{i}")
    gm.set_role_counts(g, tt)
    return gm


def _roles(gm):
    return {p["id"]: p["role"] for p in gm.players}


def test_fair_rotation_ten_players():
    random.seed(7)  # the long-wait bound is a tail check; keep it deterministic
    gm = _game(10, g=1, tt=8)  # 1 guesser, 8 truth tellers, 1 liar
    seen, last, since = Counter(), _roles(gm), {}
    for rnd in range(300):
        gm._book_round()
        gm.assign_round_roles()
        now = _roles(gm)
        for pid, role in now.items():
            if role in ("guesser", "liar"):
                assert last[pid] != role, f"round {rnd}: {pid} repeated {role}"
                seen[pid, role] += 1
                since[pid, role] = rnd
            elif rnd - since.get((pid, "guesser"), 0) > 30 or rnd - since.get((pid, "liar"), 0) > 30:
                raise AssertionError(f"{pid} waited over 30 rounds for a role")
        last = now
    for p in gm.players:
        for role in ("guesser", "liar"):
            assert 18 <= seen[p["id"], role] <= 42, (p["name"], role, seen[p["id"], role])


def test_small_game_never_repeats():
    gm = _game(4, g=1, tt=1)  # 1 guesser, 1 truth teller, 2 liars
    last = _roles(gm)
    for _ in range(100):
        gm._book_round()
        gm.assign_round_roles()
        now = _roles(gm)
        assert not [p for p in now if now[p] == last[p] and now[p] != "liar"]
        last = now


def test_role_modes():
    gm = _game(6, fair=False)
    gm.set_role_mode("one_liar")
    c = Counter(_roles(gm).values())
    assert (c["guesser"], c["truth_teller"], c["liar"]) == (1, 4, 1)
    assert gm.check_role_requirements()[0]
    gm.set_role_mode("one_truth")
    c = Counter(_roles(gm).values())
    assert (c["guesser"], c["truth_teller"], c["liar"]) == (1, 1, 4)
    assert not gm.set_role_mode("bogus")


def test_ready_up():
    gm = _game(2)
    assert not gm.toggle_ready(gm.players[0]["id"])  # under 3 players: nothing to ready for
    gm.add_player("P2")
    ids = [p["id"] for p in gm.players]
    for pid in ids:
        gm.toggle_ready(pid)
    assert gm.phase == "setup" and not gm.ready_ids

    gm.set_phase("reveal", force=True)
    gm.toggle_ready(ids[0])
    gm.toggle_ready(ids[0])  # tap again: un-ready
    assert gm.ready_ids == set()
    gm.add_player("P3")
    for pid in ids:
        gm.toggle_ready(pid)
    assert gm.round_number == 1  # P3 isn't ready yet
    gm.remove_player(gm.players[-1]["id"])  # kicking the last holdout starts the round
    assert gm.round_number == 2 and gm.phase == "setup"

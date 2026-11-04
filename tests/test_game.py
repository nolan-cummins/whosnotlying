"""
Unit tests for 'One of These People Is Not Lying' game engine.
"""

import json
import os
import src.game
from src.game import GameManager, PLAYERS_FILE
from src.packs import library

TOPIC_LIBRARY = library()
ALL_TRUE_STATEMENTS = [t["true_statement"] for t in TOPIC_LIBRARY]
ALL_FALSE_STATEMENTS = [fs for t in TOPIC_LIBRARY for fs in t["false_statements"]]



def _tok(gm, pid):
    """Session token for a player (tests skip the join flow)."""
    p = next(p for p in gm.players if p["id"] == pid)
    return p.setdefault("token", "tok_" + pid)

def test_expanded_topics():
    # Database expansion requirements: one true and one false statement per topic, all unique
    N = len(TOPIC_LIBRARY)
    assert N >= 400
    assert len(TOPIC_LIBRARY) == N
    assert len(ALL_TRUE_STATEMENTS) == N
    assert len(ALL_FALSE_STATEMENTS) == N
    assert len(set(ALL_TRUE_STATEMENTS)) == N
    assert len(set(ALL_FALSE_STATEMENTS)) == N
    assert set(ALL_TRUE_STATEMENTS).isdisjoint(set(ALL_FALSE_STATEMENTS))

    # Ensure uniqueness of IDs, topics, and true statements
    ids = [t["id"] for t in TOPIC_LIBRARY]
    assert len(ids) == len(set(ids)), "Duplicate topic IDs found"
    
    topics = [t["topic"] for t in TOPIC_LIBRARY]
    assert len(topics) == len(set(topics)), "Duplicate topics found"

    true_stmts = [t["true_statement"] for t in TOPIC_LIBRARY]
    assert len(true_stmts) == len(set(true_stmts)), "Duplicate true statements found"

    # Ensure every topic has required fields and structure
    for t in TOPIC_LIBRARY:
        assert t["id"] and isinstance(t["id"], str)
        assert t["topic"] and isinstance(t["topic"], str)
        assert t["category"] and isinstance(t["category"], str)
        assert t["true_statement"] and isinstance(t["true_statement"], str)
        assert t["true_description"] and isinstance(t["true_description"], str)
        assert t["false_statements"] and all(isinstance(x, str) and x for x in t["false_statements"])
        assert "false_statements" in t
        assert isinstance(t["false_statements"], list)
        assert len(t["false_statements"]) >= 1
        # Check that false statements within the topic are non-empty strings
        for fs in t["false_statements"]:
            assert isinstance(fs, str) and len(fs.strip()) > 0


def test_empty_lobby_on_boot_without_samples():
    gm = GameManager(seed_samples=False)
    assert len(gm.players) == 0
    assert gm.guesser_id is None
    assert gm.truth_teller_id is None
    assert gm.voting_guesser_id is None
    assert gm.phase == "lobby"


def test_liar_false_statements_pool():
    gm = GameManager(seed_samples=True)
    # Check that liars have statements from the false_statements pool
    liars = [p for p in gm.players if p["role"] == "liar"]
    assert len(liars) >= 1
    for liar in liars:
        topic_name = liar.get("topic")
        assert topic_name is not None
        # Find topic in library
        t_data = next((t for t in TOPIC_LIBRARY if t["topic"] == topic_name), None)
        assert t_data is not None
        valid_false_stmts = t_data.get("false_statements", [t_data.get("false_statement")])
        assert liar.get("statement") in valid_false_stmts


def test_initial_state_guesser_and_truthteller():
    gm = GameManager(seed_samples=True)
    assert gm.phase == "lobby"
    assert len(gm.players) >= 3
    assert gm.guesser_id is not None
    assert gm.truth_teller_id is not None
    assert gm.guesser_id != gm.truth_teller_id

    # 1 Guesser with NO clues or topic
    guesser = next(p for p in gm.players if p["id"] == gm.guesser_id)
    assert guesser["topic"] is None
    assert guesser["statement"] is None
    assert guesser["detailed_description"] is None

    # 1 Truth Teller with true statement + detailed description
    tt = next(p for p in gm.players if p["id"] == gm.truth_teller_id)
    assert tt["topic"] is not None
    assert tt["statement"] is not None
    assert tt["detailed_description"] is not None


def test_unique_topics_for_suspects():
    gm = GameManager(seed_samples=True)
    suspects = [p for p in gm.players if p["id"] != gm.guesser_id]
    topics = [p["topic"] for p in suspects]
    assert len(topics) == len(set(topics)), "Each suspect must have a unique topic!"


def test_only_guesser_can_vote():
    gm = GameManager(seed_samples=True)
    guesser_id = gm.guesser_id
    tt_id = gm.truth_teller_id
    liars = [p for p in gm.players if p["id"] not in (guesser_id, tt_id)]

    # Non-guesser (liar) attempts to vote -> should be rejected!
    res_liar = gm.cast_vote(liars[0]["id"], tt_id)
    assert res_liar is False, "Non-guesser must not be allowed to cast vote!"

    # Guesser votes -> accepted!
    res_guesser = gm.cast_vote(guesser_id, tt_id)
    assert res_guesser is True
    guesser = next(p for p in gm.players if p["id"] == guesser_id)
    assert guesser["voted_for"] == tt_id


def test_topic_history_persistence_and_clearing():
    gm = GameManager(seed_samples=True)
    gm.clear_topic_history()
    assert len(gm.used_topic_ids) == 0

    gm.assign_round_roles()
    # Used topics should now be tracked
    used_count = len(gm.used_topic_ids)
    assert used_count > 0

    # Statements are recorded to the global history once they go live
    import src.accounts
    assert src.accounts.global_keys() == []
    gm.set_phase("questioning", force=True)
    assert len({src.accounts.topic_of(k) for k in src.accounts.global_keys()}) == used_count

    # Next round should not reuse those same topics
    old_used = set(gm.used_topic_ids)
    gm.next_round()
    new_used = set(gm.used_topic_ids)
    assert len(new_used) > len(old_used)

    # Clear history
    gm.clear_topic_history()
    assert len(gm.used_topic_ids) == 0


def test_player_reconnect_sync():
    gm = GameManager()
    p = gm.add_player("TestUser123")
    pid = p["id"]

    # Reconnect with same ID and name (simulating server restart / revisit)
    p2 = gm.sync_player(player_id=pid, name="TestUser123")
    assert p2["id"] == pid

    # Player count shouldn't duplicate
    matching = [x for x in gm.players if x["name"] == "TestUser123"]
    assert len(matching) == 1


def test_untimed_phases():
    gm = GameManager(seed_samples=True)
    # Verify timer has been completely removed
    assert not hasattr(gm, "timer_seconds")
    assert not hasattr(gm, "timer_running")
    state = gm.get_state()
    assert "timer_seconds" not in state
    assert "timer" not in state

    # Transitions are manual
    gm.set_phase("questioning")
    assert gm.phase == "questioning"
    gm.set_phase("voting")
    assert gm.phase == "voting"


def test_direct_role_assignment():
    gm = GameManager(seed_samples=True)
    initial_guesser = gm.guesser_id
    initial_tt = gm.truth_teller_id
    liars = [p for p in gm.players if p["id"] not in (initial_guesser, initial_tt)]
    assert len(liars) > 0
    target_player = liars[0]["id"]

    # 1. Assign target_player to Guesser
    success = gm.set_player_role(target_player, "guesser")
    assert success is True
    assert gm.guesser_id == target_player
    p_obj = next(p for p in gm.players if p["id"] == target_player)
    assert p_obj["role"] == "guesser"
    assert p_obj["statement"] is None
    assert p_obj["detailed_description"] is None

    # 2. Assign target_player to Truth Teller
    success = gm.set_player_role(target_player, "truth_teller")
    assert success is True
    assert gm.truth_teller_id == target_player
    p_obj = next(p for p in gm.players if p["id"] == target_player)
    assert p_obj["role"] == "truth_teller"
    assert p_obj["statement"] is not None
    assert p_obj["detailed_description"] is not None
    # Guesser should have been re-assigned to another player
    assert gm.guesser_id != target_player
    assert gm.guesser_id is not None


def test_truth_teller_mobile_state_and_description():
    gm = GameManager(seed_samples=True)
    gm.set_phase("questioning")
    tt_id = gm.truth_teller_id
    guesser_id = gm.guesser_id
    liar = next(p for p in gm.players if p["id"] not in (tt_id, guesser_id))

    # Truth Teller phone view
    state_tt = gm.get_state(is_admin=False, player_id=tt_id, token=_tok(gm, tt_id))
    my_tt = state_tt["my_info"]
    assert my_tt is not None
    assert my_tt["role"] == "truth_teller"
    assert my_tt["is_truth_teller"] is True
    assert my_tt["is_guesser"] is False
    assert my_tt["topic"] is not None and len(my_tt["topic"]) > 0
    assert my_tt["statement"] is not None and len(my_tt["statement"]) > 0
    assert my_tt["detailed_description"] is not None and len(my_tt["detailed_description"]) > 0

    # Liar phone view
    state_liar = gm.get_state(is_admin=False, player_id=liar["id"], token=_tok(gm, liar["id"]))
    my_liar = state_liar["my_info"]
    assert my_liar is not None
    assert my_liar["role"] == "liar"
    assert my_liar["is_truth_teller"] is False
    assert my_liar["is_guesser"] is False
    assert my_liar["statement"] is not None
    assert my_liar["detailed_description"] is None, "Liars must never receive detailed descriptions!"

    # Guesser phone view
    state_guesser = gm.get_state(is_admin=False, player_id=guesser_id, token=_tok(gm, guesser_id))
    my_guesser = state_guesser["my_info"]
    assert my_guesser is not None
    assert my_guesser["role"] == "guesser"
    assert my_guesser["is_guesser"] is True
    assert my_guesser["topic"] is None
    assert my_guesser["statement"] is None
    assert my_guesser["detailed_description"] is None


def test_new_scoring_system_correct_guess():
    gm = GameManager(seed_samples=True)
    # Reset all scores to 0
    for p in gm.players:
        p["score"] = 0

    guesser = next(p for p in gm.players if p["id"] == gm.guesser_id)
    tt = next(p for p in gm.players if p["id"] == gm.truth_teller_id)
    liar = next(p for p in gm.players if p["id"] not in (gm.guesser_id, gm.truth_teller_id))

    # Guesser correctly guesses the truth teller
    res = gm.cast_vote(guesser["id"], tt["id"])
    assert res is True
    # Auto-reveal triggered
    assert gm.phase == "reveal"

    # Guesser gets 1 pt, TT gets 1 pt, liar gets 0
    assert guesser["score"] == 1
    assert tt["score"] == 1
    assert liar["score"] == 0


def test_new_scoring_system_incorrect_guess():
    gm = GameManager(seed_samples=True)
    for p in gm.players:
        p["score"] = 0

    guesser = next(p for p in gm.players if p["id"] == gm.guesser_id)
    tt = next(p for p in gm.players if p["id"] == gm.truth_teller_id)
    liar = next(p for p in gm.players if p["id"] not in (gm.guesser_id, gm.truth_teller_id))

    # Guesser incorrectly chooses a liar
    res = gm.cast_vote(guesser["id"], liar["id"])
    assert res is True
    assert gm.phase == "reveal"

    # Guesser gets 0, picked liar gets 1, TT gets 0
    assert guesser["score"] == 0
    assert liar["score"] == 1
    assert tt["score"] == 0


def test_guesser_advance_stages():
    gm = GameManager(seed_samples=True)
    gm.set_phase("setup")
    guesser_id = gm.guesser_id
    other_id = gm.truth_teller_id

    # Non-guesser cannot advance
    assert gm.guesser_advance(other_id) is False
    assert gm.phase == "setup"

    # Guesser advances setup -> questioning
    assert gm.guesser_advance(guesser_id) is True
    assert gm.phase == "questioning"

    # Guesser advances questioning -> voting (all statements heard)
    assert gm.guesser_advance(guesser_id) is True
    assert gm.phase == "voting"


def test_standings_structure_and_order():
    gm = GameManager(seed_samples=True)
    gm.players[0]["score"] = 3
    gm.players[1]["score"] = 1
    gm.players[2]["score"] = 5
    standings = gm.get_standings()

    # Must be ordered by score descending
    assert standings[0]["score"] >= standings[1]["score"] >= standings[2]["score"]
    assert standings[0]["rank"] == 1
    assert standings[1]["rank"] == 2
    assert standings[2]["rank"] == 3


def test_multi_guesser_and_truth_teller_role_counts():
    gm = GameManager(seed_samples=True)
    # Add players to simulate a larger party (8 players total)
    for i in range(5, 9):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    assert len(gm.players) >= 8

    # Configure 2 Guessers and 2 Truth Tellers
    assert gm.set_role_counts(2, 2, apply_now=True) is True
    assert gm.target_guesser_count == 2
    assert gm.target_truth_teller_count == 2

    gm.assign_round_roles()

    assert len(gm.guesser_ids) == 2
    assert len(gm.truth_teller_ids) == 2
    assert gm.voting_guesser_id is not None
    assert gm.voting_guesser_id in gm.guesser_ids

    # Exactly 1 guesser has is_voting_guesser True
    voter_players = [p for p in gm.players if p.get("is_voting_guesser")]
    assert len(voter_players) == 1
    assert voter_players[0]["id"] == gm.voting_guesser_id

    # The other guesser has is_voting_guesser False
    other_guessers = [p for p in gm.players if p["id"] in gm.guesser_ids and p["id"] != gm.voting_guesser_id]
    assert len(other_guessers) == 1
    assert other_guessers[0]["is_voting_guesser"] is False

    # Liars count is 8 - 2 - 2 = 4
    liars = [p for p in gm.players if p["role"] == "liar"]
    assert len(liars) == len(gm.players) - 4


def test_only_designated_voter_can_cast_vote_in_multi_guesser_game():
    gm = GameManager(seed_samples=True)
    # Ensure 6 players
    for i in range(5, 7):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    gm.set_role_counts(2, 1, apply_now=True)
    gm.assign_round_roles()

    voter_id = gm.voting_guesser_id
    consultant_id = next(gid for gid in gm.guesser_ids if gid != voter_id)
    tt_id = gm.truth_teller_ids[0]
    liar = next(p for p in gm.players if p["role"] == "liar")

    # 1. Consultant guesser attempts to vote -> BLOCKED
    res_consultant = gm.cast_vote(consultant_id, tt_id)
    assert res_consultant is False, "Consultant guesser must not be allowed to cast vote!"

    # 2. Liar attempts to vote -> BLOCKED
    res_liar = gm.cast_vote(liar["id"], tt_id)
    assert res_liar is False, "Suspect must not be allowed to cast vote!"

    # 3. Designated voter attempts to vote -> ACCEPTED
    res_voter = gm.cast_vote(voter_id, tt_id)
    assert res_voter is True
    assert gm.phase == "reveal"


def test_multi_guesser_team_scoring_on_correct_and_incorrect_guess():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    gm.set_role_counts(2, 2, apply_now=True)
    gm.assign_round_roles()

    for p in gm.players:
        p["score"] = 0

    voter_id = gm.voting_guesser_id
    consultant_id = next(gid for gid in gm.guesser_ids if gid != voter_id)
    tt1 = gm.truth_teller_ids[0]
    tt2 = gm.truth_teller_ids[1]
    liars = [p for p in gm.players if p["role"] == "liar"]
    liar1 = liars[0]
    liar2 = liars[1]

    voter_p = next(p for p in gm.players if p["id"] == voter_id)
    consultant_p = next(p for p in gm.players if p["id"] == consultant_id)
    tt1_p = next(p for p in gm.players if p["id"] == tt1)
    tt2_p = next(p for p in gm.players if p["id"] == tt2)

    # --- Scenario 1: Correct Guess (Voter identifies ALL truth tellers) ---
    res = gm.cast_vote(voter_id, target_ids=[tt1, tt2])
    assert res is True
    assert gm.last_round_results["is_correct"] is True

    # Both guessers get 1 pt each for identifying all truth tellers
    assert voter_p["score"] == 1
    assert consultant_p["score"] == 1

    # Everyone voted as the truth teller gets 1 pt
    assert tt1_p["score"] == 1
    assert tt2_p["score"] == 1

    # Unpicked liars get 0 pts
    assert liar1["score"] == 0
    assert liar2["score"] == 0

    # --- Scenario 2: Partial Guess (Voter identifies 1 truth teller and 1 liar) ---
    for p in gm.players:
        p["score"] = 0
    gm.phase = "voting"
    res_partial = gm.cast_vote(voter_id, target_ids=[tt1, liar1["id"]])
    assert res_partial is True
    assert gm.last_round_results["is_correct"] is False

    # Guessers failed to identify all truth tellers -> 0 pts
    assert voter_p["score"] == 0
    assert consultant_p["score"] == 0

    # Everyone voted as truth teller gets 1 pt for convincing guesser, regardless of actual role
    assert tt1_p["score"] == 1
    assert liar1["score"] == 1

    # Unpicked truth teller and unpicked liar get 0 pts
    assert tt2_p["score"] == 0
    assert liar2["score"] == 0

    # --- Scenario 3: Single target provided when 2 truth tellers exist ---
    for p in gm.players:
        p["score"] = 0
    gm.phase = "voting"
    res_single = gm.cast_vote(voter_id, tt1)
    assert res_single is True
    assert gm.last_round_results["is_correct"] is False
    assert voter_p["score"] == 0
    assert consultant_p["score"] == 0
    assert tt1_p["score"] == 1
    assert tt2_p["score"] == 0

    # --- Scenario 4: All Liars (Voter picks 2 liars) ---
    for p in gm.players:
        p["score"] = 0
    gm.phase = "voting"
    res_liars = gm.cast_vote(voter_id, target_ids=[liar1["id"], liar2["id"]])
    assert res_liars is True
    assert gm.last_round_results["is_correct"] is False
    assert voter_p["score"] == 0
    assert consultant_p["score"] == 0
    assert liar1["score"] == 1
    assert liar2["score"] == 1
    assert tt1_p["score"] == 0
    assert tt2_p["score"] == 0


def test_multi_truth_teller_unique_topics_and_descriptions():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    gm.set_role_counts(1, 3, apply_now=True)
    gm.assign_round_roles()

    assert len(gm.truth_teller_ids) == 3
    tt_players = [p for p in gm.players if p["id"] in gm.truth_teller_ids]

    # Every truth teller has a unique topic and statement
    topics = [p["topic"] for p in tt_players]
    assert len(topics) == 3
    assert len(set(topics)) == 3, "Each truth teller must have a distinct unique topic!"

    for p in tt_players:
        assert p["statement"] is not None and len(p["statement"]) > 0
        assert p["detailed_description"] is not None and len(p["detailed_description"]) > 0

    # All suspects (truth tellers + liars) must have unique topics
    suspects = [p for p in gm.players if p["id"] not in gm.guesser_ids]
    suspect_topics = [p["topic"] for p in suspects]
    assert len(suspect_topics) == len(set(suspect_topics))


def test_mobile_state_for_lead_voter_and_consultant_guessers():
    gm = GameManager(seed_samples=True)
    for i in range(5, 7):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    gm.set_role_counts(2, 1, apply_now=True)
    gm.assign_round_roles()

    voter_id = gm.voting_guesser_id
    consultant_id = next(gid for gid in gm.guesser_ids if gid != voter_id)

    # Lead Voter Mobile View
    voter_state = gm.get_state(is_admin=False, player_id=voter_id, token=_tok(gm, voter_id))
    v_info = voter_state["my_info"]
    assert v_info["is_guesser"] is True
    assert v_info["is_voting_guesser"] is True
    assert v_info["voting_guesser_name"] == v_info["name"]
    assert len(v_info["fellow_guessers"]) == 1

    # Consultant Guesser Mobile View
    consultant_state = gm.get_state(is_admin=False, player_id=consultant_id, token=_tok(gm, consultant_id))
    c_info = consultant_state["my_info"]
    assert c_info["is_guesser"] is True
    assert c_info["is_voting_guesser"] is False
    assert c_info["voting_guesser_name"] == v_info["name"]
    assert v_info["name"] in c_info["fellow_guessers"]


def test_set_guessers_multi_assignment():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    p_ids = [p["id"] for p in gm.players]
    target_guessers = [p_ids[0], p_ids[1]]

    # Assign multiple guessers directly
    success = gm.set_guessers(target_guessers, voter_id=target_guessers[1])
    assert success is True
    assert set(gm.guesser_ids) == set(target_guessers)
    assert gm.voting_guesser_id == target_guessers[1]
    assert gm.target_guesser_count == 2

    # Verify player attributes
    for p in gm.players:
        if p["id"] in target_guessers:
            assert p["role"] == "guesser"
            assert p["topic"] is None
            if p["id"] == target_guessers[1]:
                assert p["is_voting_guesser"] is True
            else:
                assert p["is_voting_guesser"] is False
        else:
            assert p["role"] in ("truth_teller", "liar")

    # At least 1 truth teller must exist
    assert len(gm.truth_teller_ids) >= 1
    for tid in gm.truth_teller_ids:
        assert tid not in gm.guesser_ids


def test_set_truth_tellers_multi_assignment():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    p_ids = [p["id"] for p in gm.players]
    # Set 2 guessers first
    gm.set_guessers([p_ids[0], p_ids[1]])

    # Set 2 truth tellers among the remaining
    target_tts = [p_ids[2], p_ids[3]]
    success = gm.set_truth_tellers(target_tts)
    assert success is True
    assert set(gm.truth_teller_ids) == set(target_tts)
    assert gm.target_truth_teller_count == 2

    # Verify each truth teller has valid content
    for p in gm.players:
        if p["id"] in target_tts:
            assert p["role"] == "truth_teller"
            assert p["statement"] is not None
            assert p["detailed_description"] is not None
        elif p["id"] in gm.guesser_ids:
            assert p["role"] == "guesser"
        else:
            assert p["role"] == "liar"
            assert p["detailed_description"] is None

    # Topics must be distinct between truth tellers
    tt_topics = [p["topic"] for p in gm.players if p["id"] in target_tts]
    assert len(tt_topics) == len(set(tt_topics))


def test_set_guesser_and_truth_teller_backward_compatibility():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")

    p_ids = [p["id"] for p in gm.players]

    # Can accept list or single string
    assert gm.set_guesser([p_ids[0], p_ids[1]]) is True
    assert len(gm.guesser_ids) == 2

    assert gm.set_truth_teller([p_ids[2], p_ids[3]]) is True
    assert len(gm.truth_teller_ids) == 2

    # Single string still works
    assert gm.set_guesser(p_ids[4]) is True
    assert gm.guesser_id == p_ids[4]


def test_used_true_and_false_statements_tracked_and_separated():
    gm = GameManager(seed_samples=True)
    for i in range(5, 8):
        gm.add_player(f"Player_{i}", player_id=f"p_{i}")
    gm.set_role_counts(1, 2, apply_now=True)
    gm.clear_topic_history()  # counts are cumulative across rounds; start this check from zero
    gm.assign_round_roles()

    # Verify used_statements has recorded both types
    true_stmts = [s for s in gm.used_statements if s["type"] == "true"]
    false_stmts = [s for s in gm.used_statements if s["type"] == "false"]

    assert len(true_stmts) == 2, "There must be 2 true statements used for 2 truth tellers"
    assert len(false_stmts) == len(gm.players) - 1 - 2, "Remaining suspects must be liars with false statements"

    for ts in true_stmts:
        assert ts["statement"] is not None and len(ts["statement"]) > 0
        assert ts["detailed_description"] is not None and len(ts["detailed_description"]) > 0
        assert ts["topic"] is not None

    for fs in false_stmts:
        assert fs["statement"] is not None and len(fs["statement"]) > 0
        assert fs["topic"] is not None
        assert "detailed_description" not in fs or fs["detailed_description"] is None

    # State checks for GM (history counters fill once statements are live)
    gm.set_phase("questioning", force=True)
    gm_state = gm.get_state(is_admin=True)
    assert len(gm_state["used_true_statements"]) == 2
    assert len(gm_state["used_false_statements"]) == len(false_stmts)
    assert gm_state["used_true_count"] == 2
    assert gm_state["used_false_count"] == len(false_stmts)
    assert gm_state["used_truth_count"] == 2
    assert gm_state["used_lies_count"] == len(false_stmts)
    assert gm_state["total_truth_count"] == len(TOPIC_LIBRARY)
    assert gm_state["total_lies_count"] == len(TOPIC_LIBRARY)

    # State checks for Player client (must not leak used secret statements)
    p_id = gm.players[0]["id"]
    player_state = gm.get_state(is_admin=False, player_id=p_id, token=_tok(gm, p_id))
    assert player_state["used_true_statements"] == []
    assert player_state["used_false_statements"] == []

    # Clear topic history clears used statements
    gm.clear_topic_history()
    assert len(gm.used_statements) == 0
    assert gm.get_state(is_admin=True)["used_true_count"] == 0
    assert gm.get_state(is_admin=True)["used_false_count"] == 0

    # Multi-round accumulation test
    gm.assign_round_roles()
    round1_count = len(gm.used_statements)
    assert round1_count > 0
    gm.next_round()
    round2_count = len(gm.used_statements)
    assert round2_count > 0
    assert round2_count > round1_count, "Statements used should accumulate across rounds"
    rounds_recorded = set(s["round"] for s in gm.used_statements)
    assert 1 in rounds_recorded and 2 in rounds_recorded


def test_live_terminal_and_server_logs_logging_and_privacy():
    gm = GameManager(seed_samples=False)
    # 1. Startup log present
    assert len(gm.logs) >= 1
    assert "Server initialized" in gm.logs[0]["message"]
    assert gm.logs[0]["level"] == "INFO"

    # 2. Add players and actions logs events
    p1 = gm.add_player("Tester 1")
    p2 = gm.add_player("Tester 2")
    p3 = gm.add_player("Tester 3")
    gm.set_phase("setup")
    
    recent_msgs = [l["message"] for l in gm.logs]
    assert any("Tester 1" in m for m in recent_msgs)
    assert any("SETUP" in m for m in recent_msgs)

    # 3. GM state receives logs, player state receives empty logs (spoiler protection)
    gm_state = gm.get_state(is_admin=True)
    assert "logs" in gm_state
    assert len(gm_state["logs"]) >= 3
    assert all("timestamp" in l and "level" in l and "message" in l for l in gm_state["logs"])

    player_state = gm.get_state(is_admin=False, player_id=p1["id"], token=_tok(gm, p1["id"]))
    assert player_state["logs"] == []

    # 4. Clear logs clears the buffer
    gm.clear_logs()
    assert len(gm.logs) == 1
    assert "cleared" in gm.logs[0]["message"].lower()


def test_game_start_minimum_role_requirements():
    """
    Validates the requirement that starting the game requires at least 1 Guesser,
    1 Truth Teller, and 1 Liar. Starting must be blocked with an informative error
    if any of these three roles cannot be satisfied.
    """
    gm = GameManager(seed_samples=False)

    # 1. 0 players: Cannot start
    valid, err, counts = gm.check_role_requirements()
    assert valid is False
    assert "No players have joined" in err
    assert gm.set_phase("setup") is False
    assert gm.phase == "lobby"
    assert gm.next_phase() == "lobby"
    assert gm.phase == "lobby"

    # 2. 1 player: Cannot start
    p1 = gm.add_player("Alice")
    valid, err, counts = gm.check_role_requirements()
    assert valid is False
    assert "minimum 3 players" in err
    assert gm.set_phase("setup") is False
    assert gm.phase == "lobby"

    # 3. 2 players: Cannot start (with 2 players, 1 Guesser + 1 Truth Teller leaves 0 Liars)
    p2 = gm.add_player("Bob")
    valid, err, counts = gm.check_role_requirements()
    assert valid is False
    assert "minimum 3 players" in err or "0 Liar" in err
    assert gm.set_phase("setup") is False
    assert gm.phase == "lobby"
    assert gm.next_phase() == "lobby"
    assert gm.phase == "lobby"

    # 4. 3 players, but target roles configured as 2 Guessers and 1 Truth Teller -> leaves 0 Liars!
    p3 = gm.add_player("Charlie")
    gm.set_role_counts(guesser_count=2, truth_teller_count=1)
    valid, err, counts = gm.check_role_requirements()
    assert valid is False
    assert "at least 1 Liar" in err
    assert counts["guessers"] == 2
    assert counts["truth_tellers"] == 1
    assert counts["liars"] == 0
    # Attempting to start the game must fail and stay in lobby
    assert gm.set_phase("setup") is False
    assert gm.phase == "lobby"
    assert gm.next_phase() == "lobby"
    assert gm.phase == "lobby"

    # 5. 3 players, but target roles configured as 1 Guesser and 2 Truth Tellers -> leaves 0 Liars!
    gm.set_role_counts(guesser_count=1, truth_teller_count=2)
    valid, err, counts = gm.check_role_requirements()
    assert valid is False
    assert "at least 1 Liar" in err
    assert counts["guessers"] == 1
    assert counts["truth_tellers"] == 2
    assert counts["liars"] == 0
    assert gm.set_phase("setup") is False
    assert gm.phase == "lobby"

    # 6. 4 players, with 2 Guessers and 2 Truth Tellers -> leaves 0 Liars!
    p4 = gm.add_player("Dave")
    gm.set_role_counts(guesser_count=2, truth_teller_count=2)
    valid, err, counts = gm.check_role_requirements()
    assert valid is False
    assert "at least 1 Liar" in err
    assert counts["guessers"] == 2
    assert counts["truth_tellers"] == 2
    assert counts["liars"] == 0
    assert gm.set_phase("setup") is False
    assert gm.phase == "lobby"

    # 7. 4 players, with 1 Guesser and 1 Truth Teller -> leaves 2 Liars -> Valid!
    gm.set_role_counts(guesser_count=1, truth_teller_count=1)
    valid, err, counts = gm.check_role_requirements()
    assert valid is True
    assert err is None
    assert counts["guessers"] == 1
    assert counts["truth_tellers"] == 1
    assert counts["liars"] == 2
    assert gm.set_phase("setup") is True
    assert gm.phase == "setup"

    # 8. State exposes role_requirements
    state = gm.get_state(is_admin=True)
    assert "role_requirements" in state
    assert state["role_requirements"]["valid"] is True
    assert state["role_requirements"]["players"] == 4
    assert state["role_requirements"]["guessers"] == 1
    assert state["role_requirements"]["truth_tellers"] == 1
    assert state["role_requirements"]["liars"] == 2


def test_round_end_blocks_advance_and_previous_phases():
    """
    Validates that when a round reaches its end (reveal phase):
    - Advancing (next_phase) is disabled and blocked to prevent confusion/wrap-around.
    - Jumping back to previous phases (setup, questioning, voting) is blocked.
    - The only valid actions are starting a new round (next_round) or returning/terminating to lobby.
    """
    gm = GameManager(seed_samples=True)
    gm.set_phase("setup")
    gm.set_phase("questioning")
    gm.set_phase("voting")
    gm.set_phase("reveal")
    assert gm.phase == "reveal"

    # 1. Calling next_phase() when in reveal is blocked and keeps phase as reveal
    assert gm.next_phase() == "reveal"
    assert gm.phase == "reveal"

    # 2. Returning to previous phases (setup, questioning, voting) is blocked
    assert gm.set_phase("voting") is False
    assert gm.phase == "reveal"

    assert gm.set_phase("questioning") is False
    assert gm.phase == "reveal"

    assert gm.set_phase("setup") is False
    assert gm.phase == "reveal"

    # 3. Starting a new round is allowed and advances to Round 2 Setup
    assert gm.next_round() is True
    assert gm.phase == "setup"
    assert gm.round_number == 2

    # Move Round 2 to reveal
    gm.set_phase("voting")
    gm.set_phase("reveal")
    assert gm.phase == "reveal"

    # 4. Terminating the game and returning to lobby is allowed
    assert gm.set_phase("lobby") is True
    assert gm.phase == "lobby"


def test_normal_launch_starts_with_empty_lobby_and_no_default_players(tmp_path):
    """
    Validates that when the game is launched normally (not via the testbench):
    - It does not initialize with any default or sample players.
    - It starts with an empty lobby (0 players) so the GM does not have to manually remove players.
    - Even if a players.json file on disk contained test bench or sample players, normal launch discards them.
    """
    # Create a dummy players file with leftover test bench and default players
    leftover_file = str(tmp_path / "leftover_players.json")
    with open(leftover_file, "w", encoding="utf-8") as f:
        json.dump([
            {"id": "p1", "name": "Player 1", "role": "guesser"},
            {"id": "p2", "name": "Player 2", "role": "truth_teller"},
            {"id": "p3", "name": "Player 3", "role": "liar"},
            {"id": "p4", "name": "Alice", "role": "liar"},
            {"id": "p5", "name": "Bob", "role": "liar"}
        ], f)

    # 1. Default GameManager() starts with 0 players in lobby
    gm_default = GameManager()
    assert len(gm_default.players) == 0
    assert gm_default.guesser_ids == []
    assert gm_default.voting_guesser_id is None
    assert gm_default.truth_teller_ids == []
    assert gm_default.phase == "lobby"

    # 2. Even if a players.json file previously existed with default/sample players,
    # default initialization starts without any players in the lobby.
    gm2 = GameManager(seed_samples=False, players_file=leftover_file)
    assert len(gm2.players) == 0
    assert gm2.guesser_ids == []
    assert gm2.truth_teller_ids == []
    assert gm2.phase == "lobby"

    # 3. Simulate players joining dynamically (as test bench does via API)
    for i in range(1, 7):
        gm2.sync_player(f"p_{i}", f"Player {i}")
    assert len(gm2.players) == 6
    assert [p["name"] for p in gm2.players] == [f"Player {i}" for i in range(1, 7)]









import random
from collections import Counter

from src import match


def _topics(n=40):
    tags = ["Physics", "Art", "Sports", "Medicine"]
    return [{"id": f"t{i}", "topic": f"T{i}", "tags": [tags[i % 4]], "group": None} for i in range(n)]


def test_tags_bias_but_not_lock():
    topics, rng = _topics(), random.Random(1)
    hits = Counter()
    for _ in range(500):
        got = match.deal([{"id": "a", "tags": ["Physics"]}, {"id": "b"}], topics, "tags", rng)
        hits[got["a"]["tags"][0]] += 1
        assert got["a"] is not got["b"]
    assert hits["Physics"] > 250 and sum(hits.values()) - hits["Physics"] > 25, hits  # chance would be 125


def test_no_profile_is_uniform():
    topics, rng = _topics(), random.Random(2)
    hits = Counter(match.deal([{"id": "a"}], topics, "tags", rng)["a"]["tags"][0] for _ in range(2000))
    assert all(400 < n < 600 for n in hits.values()), hits


def test_one_topic_per_paper_group():
    topics = [{"id": f"t{i}", "topic": f"T{i}", "tags": [], "group": f"doi{i // 3}"} for i in range(9)]
    for seed in range(200):
        got = match.deal([{"id": c} for c in "abc"], topics, "off", random.Random(seed))
        assert len({t["group"] for t in got.values()}) == 3


def test_expertise_prefers_nearest(monkeypatch):
    topics = [{"id": f"t{i}", "topic": f"T{i}", "summary": f"s{i}", "tags": []} for i in range(30)]
    vec = lambda i: [1.0, 0.0] if i < 10 else [0.0, 1.0]
    monkeypatch.setattr(match, "_vecs", {match._key(f"s{i}"): vec(i) for i in range(30)} | {match._key(match.query_text("cats")): [1.0, 0.0]})
    monkeypatch.setattr(match, "_cos", {})
    monkeypatch.setattr(match, "_loaded", True)
    rng = random.Random(3)
    near = sum(int(match.deal([{"id": "a", "expertise": "cats"}], topics, "expertise", rng)["a"]["id"][1:]) < 10 for _ in range(500))
    assert near > 250, near  # chance would be ~167


def test_one_sided_items_go_to_the_right_role(tmp_path):
    """Packs may hold truth-only and lie-only items; truth tellers and liars must each get their kind."""
    import json
    from src import packs
    from src.game import GameManager
    items = [{"id": f"t{i}", "category": "C", "topic": f"Truth {i}", "truth": {"text": f"real {i}", "facts": ["a", "b", "c"]}} for i in range(6)]
    items += [{"id": f"l{i}", "category": "C", "topic": f"Lie {i}", "lies": [{"text": f"fake {i}", "facts": ["a", "b"]}]} for i in range(12)]
    with open(f"{packs.PACKS_DIR}/split.json", "w") as f:
        json.dump({"id": "split", "name": "Split", "version": 2, "topics": items}, f)
    gm = GameManager()
    assert gm.set_packs(["split"])
    for n in range(5):
        gm.add_player(f"P{n}")
    for _ in range(20):
        gm.randomize_roles()
        for p in gm.players:
            if p["role"] == "truth_teller":
                assert p["topic"].startswith("Truth") and p["statement"].startswith("real")
            elif p["role"] == "liar":
                assert p["topic"].startswith("Lie") and p["statement"].startswith("fake")
    liar = next(p for p in gm.players if p["role"] == "liar")
    gm.set_player_role(liar["id"], "truth_teller")  # a role swap re-deals from the truth pool
    assert liar["topic"].startswith("Truth") and liar["statement"].startswith("real")


def test_tags_match_by_meaning(monkeypatch):
    """A custom tag ('army') pulls topics tagged with a different but related tag ('Military History')."""
    topics = [{"id": f"t{i}", "topic": f"T{i}", "tags": ["Military History" if i < 10 else "Cooking"]} for i in range(30)]
    vec = {"army": [0.9, 0.1], "Military History": [1.0, 0.0], "Cooking": [0.0, 1.0]}
    monkeypatch.setattr(match, "_vecs", {match._key(match.tag_text(k)): v for k, v in vec.items()})
    monkeypatch.setattr(match, "_cos", {})
    monkeypatch.setattr(match, "_loaded", True)
    rng = random.Random(4)
    mil = sum(match.deal([{"id": "a", "tags": ["army"]}], topics, "tags", rng)["a"]["tags"][0] == "Military History" for _ in range(500))
    assert mil > 250, mil  # chance would be ~167


def test_percent_ranks_topic_within_pool():
    topics = [{"id": f"t{i}", "topic": f"T{i}", "tags": ["Physics" if i == 0 else "Art" if i < 5 else "Sports"]} for i in range(11)]
    p = {"tags": ["Physics"]}
    assert match.percent(p, topics[0], topics, "tags") == 100
    assert match.percent(p, topics[10], topics, "tags") == 0
    assert match.percent({}, topics[0], topics, "tags") is None


def test_rank_tags_puts_mine_first_then_alphabetical_without_embeddings():
    assert match.rank_tags(["Zoo"], ["Art", "Zoo", "Bees"]) == ["Zoo", "Art", "Bees"]


def test_rank_tags_relevance_mine_az_then_by_meaning(monkeypatch):
    # Stub embeddings: 2-d unit vectors; "Robots" and the robot-ish expertise point along x, "Cooking" along y.
    vec = {"Zoo": [0, 1], "Robots": [1, 0], "Engineering": [0.9, 0.436], "Cooking": [0, 1], "Art": [0.6, 0.8]}
    def fake_embed(texts, timeout=30):
        return [vec[t.split(": ", 1)[1]] if t.startswith("Topic: ") else [1, 0] for t in texts]
    monkeypatch.setattr(match, "embed", fake_embed)
    tags = ["Art", "Cooking", "Engineering", "Robots", "Zoo"]
    assert match.rank_tags(["Zoo", "Robots"], tags) == ["Robots", "Zoo", "Art", "Cooking", "Engineering"]  # not embedded yet: A-Z
    match.warm([match.tag_text(t) for t in tags] + [match.query_text("I build industrial robots")])
    match._worker.join()
    assert match.rank_tags(["Zoo", "Robots"], tags) == ["Robots", "Zoo", "Cooking", "Engineering", "Art"]
    # Expertise alone (no tags selected) still ranks by meaning, not A-Z
    assert match.rank_tags([], tags, "I build industrial robots") == ["Robots", "Engineering", "Art", "Cooking", "Zoo"]
    assert match.nearest_tag("robots", ["Robots", "Cooking"]) == "Robots"  # exact, case-insensitive
    assert match.nearest_tag("Engineering", ["Art", "Robots"]) == "Robots"  # 0.9 cosine: an existing tag wins
    assert match.nearest_tag("Cooking", ["Robots"]) is None  # unrelated: stays a custom tag


def test_warm_queued_during_drain_is_not_dropped(monkeypatch):
    """A text queued while the worker is finishing must still get embedded (the _draining handoff)."""
    import time
    monkeypatch.setattr(match, "embed", lambda texts, timeout=30: [time.sleep(0.02) or [1, 0] for _ in texts])
    match.warm(["Topic: First"])          # worker starts on "First"
    time.sleep(0.01)                      # ...and is mid-embed, so this call queues instead of starting a worker
    match.warm(["Topic: Second"])
    for _ in range(200):                  # whichever worker owns it, the text must land in the cache
        if match._key("Topic: Second") in match._vecs:
            break
        time.sleep(0.01)
    assert match._key("Topic: Second") in match._vecs

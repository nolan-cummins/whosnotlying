import json
import os
import src.packs as packs
from src.game import GameManager


def _add_pack(pid, n=3):
    topics = [{"id": f"t{i}", "category": "c", "topic": f"{pid} topic {i}", "true_statement": f"{pid} true {i}",
               "true_description": "- d", "false_statements": [f"{pid} false {i}"]} for i in range(n)]
    with open(os.path.join(packs.PACKS_DIR, f"{pid}.json"), "w") as f:
        json.dump({"id": pid, "name": pid, "topics": topics}, f)


def test_new_pack_autoloads_selects_and_resets():
    gm = GameManager(seed_samples=True)
    shipped = {p["id"] for p in packs.pack_summaries()}
    assert "ai-hallucinations-1" in shipped
    _add_pack("extra")
    assert {p["id"] for p in packs.pack_summaries()} == shipped | {"extra"}

    assert gm.set_packs(["extra"])
    assert not gm.set_packs(["nope"])  # invalid selection is rejected, previous one kept
    assert {t["pack"] for t in packs.library()} == {"extra"}

    gm.assign_round_roles()
    from src.game import find_topic_data
    assert all(find_topic_data(p["topic"])["pack"] == "extra" for p in gm.players if p.get("topic"))
    gm.set_phase("questioning", force=True)
    assert {p["id"]: p["used"] for p in packs.pack_summaries(
        set(__import__("src.accounts").accounts.global_keys()))}["extra"] == 3

    gm.clear_topic_history()
    assert __import__("src.accounts").accounts.global_keys() == []


def test_v1_used_flags_migrate_to_history():
    import src.accounts as accounts
    path = os.path.join(packs.PACKS_DIR, "ai-hallucinations-1.json")
    raw = json.load(open(path))
    for t in raw["topics"][:2]:
        t["true_statement"] = t["truth"]["text"] if "truth" in t else t["true_statement"]
    raw["topics"][0].update(used=True, used_as="true")
    raw["topics"][1].update(used=True)
    json.dump(raw, open(path, "w"))
    GameManager()
    tid0, tid1 = raw["topics"][0]["id"], raw["topics"][1]["id"]
    assert accounts.global_keys() == [f"ai-hallucinations-1:{tid0}:t", f"ai-hallucinations-1:{tid1}:?"]
    assert "used" not in packs.library()[0]  # flags in the file are ignored by the loader


def test_statement_keys_and_v2_schema():
    with open(os.path.join(packs.PACKS_DIR, "v2.json"), "w") as f:
        json.dump({"id": "v2", "topics": [{"id": "a", "category": "c", "topic": "T",
                   "truth": {"text": "true one", "facts": ["f1"]},
                   "lies": [{"text": "lie one", "facts": ["g1"]}, {"text": "lie two", "facts": []}]}]}, f)
    t = next(t for t in packs.library() if t["pack"] == "v2")
    assert t["true_description"] == "• f1" and t["false_statements"] == ["lie one", "lie two"]
    assert packs.statement_key(t, "true one") == "v2:a:t"
    assert packs.statement_key(t, "lie two") == "v2:a:f1"
    assert packs.lie_facts(t, "lie one") == ["g1"]

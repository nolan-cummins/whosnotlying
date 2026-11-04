import os
import shutil
import pytest
import src.accounts
import src.game
import src.packs

REAL_PACKS = src.packs.PACKS_DIR


@pytest.fixture(autouse=True)
def clean_players_file(tmp_path):
    # Isolated players.json and an isolated copy of the packs (used flags are written back to them)
    packs_dir = tmp_path / "packs"
    shutil.copytree(REAL_PACKS, packs_dir)

    orig_players = src.game.PLAYERS_FILE
    orig_packs = src.packs.PACKS_DIR

    src.game.PLAYERS_FILE = str(tmp_path / "players.json")
    src.packs.PACKS_DIR = str(packs_dir)
    src.packs._cache.clear()
    orig_data = src.accounts.DATA_DIR
    src.accounts.DATA_DIR = str(tmp_path / "data")

    yield

    src.accounts.DATA_DIR = orig_data
    src.game.PLAYERS_FILE = orig_players
    src.packs.PACKS_DIR = orig_packs
    src.packs._cache.clear()


@pytest.fixture(autouse=True)
def no_ollama(monkeypatch):
    # Tests never reach the real embedding server; each starts with an empty vector cache.
    import src.match as m
    monkeypatch.setattr(m, "OLLAMA_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(m, "_vecs", {})
    monkeypatch.setattr(m, "_cos", {})
    monkeypatch.setattr(m, "_loaded", True)
    monkeypatch.setattr(m, "_status", {"state": "idle", "error": ""})
    monkeypatch.setattr(m, "_rank_memo", {})
    monkeypatch.setattr(m, "_pending", [])
    monkeypatch.setattr(m, "_worker", None)
    monkeypatch.setattr(m, "_draining", [False])

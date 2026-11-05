"""Unit-length embeddings from a local Ollama server (the game's src/match.ts does the same; this keeps the
research scripts in this folder self-contained now that the game itself is TypeScript)."""
import json
import math
import os
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("EMBED_MODEL", "qwen3-embedding:0.6b")


def embed(texts, timeout=30):
    req = urllib.request.Request(f"{OLLAMA_URL}/api/embed", data=json.dumps({"model": MODEL, "input": texts}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        vecs = json.load(r)["embeddings"]
    out = []
    for v in vecs:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([round(x / n, 5) for x in v])
    return out

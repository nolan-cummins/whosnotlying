"""
"Upload resume": PDF -> text (pdftotext) -> a local Ollama chat model drafts the player's expertise and tags.
Nothing is stored: the PDF lives in a temp file for the length of one request.
"""
import json
import os
import subprocess
import tempfile
import urllib.request
from typing import Any, Dict, List

from src import match
from src.match import OLLAMA_URL

MODEL = os.environ.get("RESUME_MODEL", "qwen3-vl:4b")
MAX_PDF = 5 * 1024 * 1024


def pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF"):
        raise ValueError("That file isn't a PDF.")
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        out = subprocess.run(["pdftotext", "-q", "-layout", f.name, "-"], capture_output=True, text=True, timeout=30).stdout
    text = " ".join(out.split())
    if len(text) < 100:
        raise ValueError("Couldn't read any text in that PDF (is it a scanned image?).")
    return text[:12000]


def _chat(prompt: str) -> Dict[str, Any]:
    body = {"model": MODEL, "stream": False, "format": "json", "think": False, "options": {"temperature": 0.2},
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        msg = json.load(r)["message"]
    # ponytail: with think=false, Ollama returns qwen3-vl's answer in "thinking" rather than "content"; take either.
    return json.loads(msg.get("content") or msg.get("thinking") or "{}")


def suggest_tags(expertise: str, vocabulary: List[str]) -> List[str]:
    """Tags for a player's expertise text: existing game tags where one means the same thing, else short custom tags."""
    out = _chat("For a trivia party game, pick 6-12 short topic tags for what this person could confidently talk about.\n"
                "Return JSON only: {\"tags\": [\"...\"]}. Use tags from this list whenever one fits, "
                "and only invent a short new tag (1-3 words) for something the list doesn't cover. "
                "Tags are subjects (\"Robotics\", \"Military History\"), never roles or traits (\"Hobbyist\", \"Expert\"): "
                + ", ".join(vocabulary) + "\n\nEXPERTISE:\n" + expertise[:2000])
    picked = []
    for t in out.get("tags") or []:
        t = " ".join(str(t).split())[:32]
        t = (match.nearest_tag(t, vocabulary) or t) if t else ""  # 0.78: WWII History -> Military History, Cooking -> Food & Drink; Plastics stays custom
        if t and t.lower() not in {x.lower() for x in picked}:
            picked.append(t)
    # The model sometimes grabs a list tag on a word clash ("Plants" for factory plants): drop picks far less related
    # to the expertise than the best pick (calibrated: engineer -> Plants 0.24 vs CNC 0.48; chef -> Sports 0.25 vs Food 0.32).
    rel = match.tag_relevance(expertise, picked) if picked else None
    if rel:
        picked = [t for t, r in zip(picked, rel) if r >= 0.6 * max(rel)]
    known = {v.lower() for v in vocabulary}
    return sorted(picked, key=lambda t: t.lower() not in known)[:12]  # existing tags first


def draft_profile(text: str, vocabulary: List[str]) -> Dict[str, Any]:
    """Ask the model for {"expertise": str, "tags": [str]}; tags prefer the game's existing vocabulary."""
    prompt = ("Below is a resume. For a trivia party game, describe what this person could confidently talk about.\n"
              "Return JSON only: {\"expertise\": \"5-8 short bullet lines starting with '- ', under 550 characters: "
              "their field, specialties, tools, hobbies\", \"tags\": [\"6-12 short topic tags\"]}.\n"
              "Prefer tags from this list when they fit: " + ", ".join(vocabulary) + "\n\nRESUME:\n" + text)
    out = _chat(prompt)
    exp = out.get("expertise")
    exp = "\n".join(exp) if isinstance(exp, list) else str(exp or "")
    tags = [str(t) for t in out.get("tags") or [] if str(t).strip()]
    return {"expertise": exp.strip()[:600], "tags": tags[:12]}

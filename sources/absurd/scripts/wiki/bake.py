"""
Model bake-off for the article gate and fact extraction (OpenRouter or any OpenAI-compatible server).

    python3 -I bake.py D sample                       # pick articles -> D/exp/bake/sample.json
    python3 -I bake.py D run gate|extract MODEL...    # 2 runs each -> D/exp/bake/<task>__<model>.jsonl
    python3 -I bake.py D report                       # table vs D/exp/bake/gold.json -> appended to REPORT.md
BASE_URL / API_KEY env override the endpoint (e.g. a local llama-server); default OpenRouter + key file.
"""
import concurrent.futures as cf
import glob
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import load

BASE = os.environ.get("BASE_URL", "https://openrouter.ai/api/v1")
KEY = os.environ.get("API_KEY") or open(os.path.expanduser("~/Projects/openrouter_claude.txt")).read().strip()
GATE_CHARS, EXTRACT_CHARS = 3000, 40000

GATE = ("You screen Wikipedia articles for a party trivia game. Decide whether this article is worth mining: does it contain "
        "enough concrete facts, events or details that a writer could plausibly find at least one interesting, non-obvious fact "
        "for a general audience? Not minable: stubs, disambiguation, pure lists or results tables, bare taxonomy, routine "
        "biographies or places described only by dates, positions and statistics.\n"
        "richness: 0 nothing usable, 1 thin, 2 at least one interesting fact, 3 several surprising or memorable facts.\n\n"
        "TITLE: {title}\n\n{text}")
GATE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["minable", "richness", "reason"],
               "properties": {"minable": {"type": "boolean"}, "richness": {"type": "integer", "enum": [0, 1, 2, 3]},
                              "reason": {"type": "string"}}}
EXTRACT = ("From this Wikipedia article, extract up to 8 facts that would surprise or delight a general audience at a trivia "
           "party. Skip common knowledge and dry data (dates of office, statistics, taxonomy). For each: quote = one sentence "
           "copied verbatim from the article; claim = the fact restated plainly in at most 25 words; surprise 0-3; "
           "absurd = true if it is bizarre or funny, not just interesting. Return an empty list if nothing qualifies.\n\n"
           "TITLE: {title}\n\n{text}")
EXTRACT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {"facts": {
    "type": "array", "maxItems": 8, "items": {"type": "object", "additionalProperties": False,
                                              "required": ["quote", "claim", "surprise", "absurd"],
                                              "properties": {"quote": {"type": "string"}, "claim": {"type": "string"},
                                                             "surprise": {"type": "integer", "enum": [0, 1, 2, 3]},
                                                             "absurd": {"type": "boolean"}}}}}}
EXTRACT2 = """You are a researcher for "Liars", a party game. Each round a player reads one fact aloud and the others must decide
whether it is true or invented. The best facts are true but sound made up: obscure, specific and surprising, so that an
educated adult has almost certainly never heard them and would hesitate before believing them.

Below is a Wikipedia article split into numbered sentences. Extract the facts from it that would work in the game.

A good fact:
- is surprising, funny, ironic, counter-intuitive or oddly specific (a goat that held office, a law nobody repealed,
  a disaster caused by something trivial, a record set in a ridiculous way);
- is self-contained: it makes sense to someone who has never heard of the article's subject;
- is stated in the text itself, not inferred. Never add details, motives or numbers the text does not give.
Not a good fact: routine biography (born, studied, appointed, died), dates of office, sports results, plot summaries,
geography, taxonomy, statistics without a twist, anything most people already know, or anything only a specialist
would find interesting.

Read carefully: words have period and domain meanings (a "computer" in 1900 was a person who did calculations; a ship
"lost with all hands" sank, it was not mislaid). If you are unsure what a sentence means, skip it.

For each fact return:
- ids: the number(s) of the sentence(s) that state it (usually one; at most three, consecutive);
- claim: the fact in plain English, at most 25 words, faithful to the text, understandable without the article;
- surprise: 1 = mildly interesting, 2 = most people would be surprised, 3 = most people would doubt it is true.
  Be strict: reserve 3 for facts that genuinely sound invented. Superlatives about local statistics are 1.
- absurd: true only if the fact is bizarre or funny, not merely interesting.
Return at most 6 facts, best first. Return an empty list if the article has nothing that qualifies; that is common and fine.

TITLE: {title}

{text}"""
EXTRACT2_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {"facts": {
    "type": "array", "maxItems": 6, "items": {"type": "object", "additionalProperties": False,
                                              "required": ["ids", "claim", "surprise", "absurd"],
                                              "properties": {"ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 3},
                                                             "claim": {"type": "string"},
                                                             "surprise": {"type": "integer", "enum": [1, 2, 3]},
                                                             "absurd": {"type": "boolean"}}}}}}


def numbered(text):
    """Reference list stripped, sentences numbered: the model cites ids instead of copying quotes."""
    from trim import sentences, strip_refs
    return "\n".join(f"[{i}] {x}" for i, x in enumerate(sentences(strip_refs(text)), 1))


TASKS = {"gate": (GATE, GATE_SCHEMA, GATE_CHARS), "extract": (EXTRACT, EXTRACT_SCHEMA, EXTRACT_CHARS),
         "extract2": (EXTRACT2, EXTRACT2_SCHEMA, EXTRACT_CHARS)}


def ask(model, prompt, schema):
    body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt + os.environ.get("SUFFIX", "")}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "strict": True, "schema": schema}}}
    if "openrouter" in BASE:
        body.update(usage={"include": True})
        if not model.endswith(":free"):  # free endpoints rarely advertise every parameter; validity is measured instead
            body["provider"] = {"require_parameters": True}
        if "gpt-oss" in model:
            body["reasoning"] = {"effort": "low"}
    body.update(json.loads(os.environ.get("EXTRA", "{}")))  # e.g. provider order, reasoning off
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(4):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=int(os.environ.get("TIMEOUT", 120))))
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code == 429 and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            return {"error": f"{e.code} {msg}", "secs": time.time() - t0, "r429": e.code == 429}
        except Exception as e:
            return {"error": f"net {e}", "secs": time.time() - t0}
    out = {"secs": time.time() - t0, "usage": r.get("usage", {}), "provider": r.get("provider"), "retries": attempt}
    try:
        out["ans"] = json.loads(r["choices"][0]["message"]["content"])
    except Exception as e:
        out["error"] = f"parse {e}: {str(r)[:200]}"
    return out


def sample(d):
    meta, text = load(d)
    ok = [m["id"] for m in meta.values() if 10 <= m["pct"] < 90 and m["chars"] > 600
          and not text[m["id"]]["title"].startswith("List of") and "may refer to" not in text[m["id"]]["text"][:400]]
    rng = random.Random(23)
    gate = rng.sample(ok, 40)
    extract = rng.sample([i for i in gate if meta[i]["chars"] > 2500], 15)
    json.dump({"gate": gate, "extract": extract}, open(os.path.join(d, "exp", "bake", "sample.json"), "w"))
    print(len(gate), len(extract))


def run(d, task, models):
    _, text = load(d)
    s = json.load(open(os.path.join(d, "exp", "bake", "sample.json")))
    tmpl, schema, cap = TASKS[task]
    for model in models:
        jobs = [(i, k) for i in s[task.rstrip("2")] for k in (0, 1)]
        workers = 2 if model.endswith(":free") else 8
        tag = os.environ.get("TAG", "")
        t0 = time.time()
        with cf.ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(lambda j: (j, ask(model, tmpl.replace("{title}", text[j[0]]["title"]).replace("{text}", (numbered if task == "extract2" else str)(text[j[0]]["text"][:cap])), schema)), jobs))
        wall = time.time() - t0
        path = os.path.join(d, "exp", "bake", f"{task}__{model.replace('/', '_')}{tag}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for (i, k), r in res:
                f.write(json.dumps({"id": i, "run": k, "wall": wall, **r}, ensure_ascii=False) + "\n")
        ok = sum("ans" in r for _, r in res)
        cost = sum((r.get("usage") or {}).get("cost") or 0 for _, r in res)
        errs = {r["error"][:90] for _, r in res if "error" in r}
        print(f"{task} {model}: {ok}/{len(res)} ok, ${cost:.4f}, wall {wall:.0f}s {list(errs)[:2]}", flush=True)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def report(d):
    _, text = load(d)
    B = os.path.join(d, "exp", "bake")
    gold = json.load(open(os.path.join(B, "gold.json"))) if os.path.exists(os.path.join(B, "gold.json")) else {}
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(len(xs) * p))] if xs else 0
    out = ["## T7. Model bake-off", "",
           "### Gate (first 3k chars, 40 articles x 2 runs)", "",
           "| model | ok | p50 s | p95 s | out tok/s | $/article | $ for 4M gates | run agree (minable) | richness agree | acc vs my labels | richness MAE |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for path in sorted(glob.glob(os.path.join(B, "gate__*.jsonl"))):
        model = os.path.basename(path)[6:-6]
        rows = [json.loads(x) for x in open(path, encoding="utf-8")]
        good = [r for r in rows if isinstance(r.get("ans"), dict) and {"minable", "richness"} <= r["ans"].keys()]  # free endpoints skip the schema
        lat = [r["secs"] for r in good]
        tps = [r["usage"].get("completion_tokens", 0) / r["secs"] for r in good if r.get("usage") and r["secs"] > 0]
        cost = statistics.mean([(r.get("usage") or {}).get("cost") or 0 for r in good]) if good else 0
        by = {}
        for r in good:
            by.setdefault(r["id"], {})[r["run"]] = r["ans"]
        pairs = [v for v in by.values() if len(v) == 2]
        agree = statistics.mean(v[0]["minable"] == v[1]["minable"] for v in pairs) if pairs else 0
        ragree = statistics.mean(v[0]["richness"] == v[1]["richness"] for v in pairs) if pairs else 0
        g = [(by[int(i)][0], gv) for i, gv in gold.get("gate", {}).items() if 0 in by.get(int(i), {})]
        acc = statistics.mean(a["minable"] == gv["minable"] for a, gv in g) if g else 0
        mae = statistics.mean(abs(a["richness"] - gv["richness"]) for a, gv in g) if g else 0
        out.append(f"| {model} | {len(good)}/{len(rows)} | {q(lat, .5):.1f} | {q(lat, .95):.1f} | {statistics.median(tps) if tps else 0:.0f} | "
                   f"{cost:.6f} | {cost * 4e6:,.0f} | {100 * agree:.0f}% | {100 * ragree:.0f}% | {100 * acc:.0f}% | {mae:.2f} |")
    out += ["", "### Extract (full text up to 40k chars, 15 articles x 2 runs)", "",
            "| model | ok | p50 s | p95 s | out tok/s | $/article | $ for 100k | facts/article | verbatim quotes | run overlap (quotes) | absurd flagged | my rating good/meh/bad |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    grades = gold.get("extract", {})
    for path in sorted(glob.glob(os.path.join(B, "extract__*.jsonl"))):
        model = os.path.basename(path)[9:-6]
        rows = [json.loads(x) for x in open(path, encoding="utf-8")]
        good = [r for r in rows if "ans" in r]
        lat = [r["secs"] for r in good]
        tps = [r["usage"].get("completion_tokens", 0) / r["secs"] for r in good if r.get("usage") and r["secs"] > 0]
        cost = statistics.mean([(r.get("usage") or {}).get("cost") or 0 for r in good]) if good else 0
        facts = [f for r in good for f in r["ans"]["facts"]]
        verb = [norm(f["quote"]) in norm(text[r["id"]]["text"]) for r in good for f in r["ans"]["facts"]]
        by = {}
        for r in good:
            by.setdefault(r["id"], {})[r["run"]] = {norm(f["quote"]) for f in r["ans"]["facts"]}
        ov = [len(v[0] & v[1]) / max(1, len(v[0] | v[1])) for v in by.values() if len(v) == 2]
        gr = grades.get(model, {})
        gtxt = f"{gr.get('good', 0)}/{gr.get('meh', 0)}/{gr.get('bad', 0)}" if gr else "-"
        out.append(f"| {model} | {len(good)}/{len(rows)} | {q(lat, .5):.1f} | {q(lat, .95):.1f} | {statistics.median(tps) if tps else 0:.0f} | "
                   f"{cost:.5f} | {cost * 1e5:,.0f} | {len(facts) / max(1, len(good)):.1f} | {100 * statistics.mean(verb) if verb else 0:.0f}% | "
                   f"{100 * statistics.mean(ov) if ov else 0:.0f}% | {sum(f['absurd'] for f in facts)} | {gtxt} |")
    with open(os.path.join(d, "exp", "REPORT.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n\n")
    print("\n".join(out))


if __name__ == "__main__":
    d, cmd = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(d, "exp", "bake"), exist_ok=True)
    {"sample": lambda: sample(d), "run": lambda: run(d, sys.argv[3], sys.argv[4:]), "report": lambda: report(d)}[cmd]()

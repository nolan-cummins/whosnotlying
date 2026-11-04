"""
T6: ask OpenRouter models the yes/no boringness questions about full article texts, twice each.

    python3 -I llm.py D N MODEL...        # N random articles (pct 10-90); results -> D/exp/llm/<model>.jsonl, section in REPORT.md
Key: OPENROUTER_KEY_FILE (default ~/Projects/openrouter_claude.txt). Never printed.
"""
import concurrent.futures as cf
import json
import os
import random
import statistics
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import load

KEY = open(os.environ.get("OPENROUTER_KEY_FILE", os.path.expanduser("~/Projects/openrouter_claude.txt"))).read().strip()
Q = {
    "mass_produced": "Is the subject one of many near-identical entities of its kind (a town, species, sports season, election, road, asteroid, ship of a class)?",
    "mostly_data": "Is the text mostly numbers, dates, statistics or lists?",
    "templated": "Could this article be produced by filling names and numbers into a standard template?",
    "has_event": "Does it describe something that happened, rather than only a static thing?",
    "unpredictable": "Does anything occur that a reader could not predict from the title alone?",
    "role_violation": "Does a person, animal, object or institution act contrary to its normal role?",
    "mishap": "Is there a mistake, accident, dispute, lawsuit or unintended consequence?",
    "anecdote": "Is there a concrete anecdote: a named actor doing a specific thing at a specific time?",
    "domain_clash": "Does it bring together two domains that rarely meet?",
    "administrative": "Is its significance purely administrative or bureaucratic?",
    "specialist_only": "Would it interest only a specialist?",
    "record": "Is there a record or superlative (first, only, oldest, largest)?",
    "deception": "Does it involve a hoax, prank, misunderstanding or deception?",
    "ironic": "Is an outcome ironic, or the opposite of what was intended?",
    "stub": "Is it a stub (fewer than 3 substantive sentences)?",
    "dyk_hook": "Does it contain a fact that would make a good, surprising 'Did you know...' hook for a general audience?",
}
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": list(Q) + ["most_absurd_sentence"],
          "properties": {**{k: {"type": "boolean"} for k in Q},
                         "most_absurd_sentence": {"type": "string", "description": "copied verbatim from the article"}}}
PROMPT = ("Answer each question about the Wikipedia article below with true or false, judging the whole article. "
          "Then copy, verbatim, the single most surprising or absurd sentence in it.\n\n"
          + "\n".join(f"{k}: {v}" for k, v in Q.items()) + "\n\nARTICLE TITLE: {title}\n\n{text}")


def ask(model, title, text):
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT.replace("{title}", title).replace("{text}", text)}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "answers", "strict": True, "schema": SCHEMA}},
            "provider": {"require_parameters": True}, "usage": {"include": True}}
    if "gpt-oss" in model:
        body["reasoning"] = {"effort": "low"}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        return {"error": f"{e.code} {e.read()[:200]!r}", "secs": time.time() - t0}
    out = {"secs": time.time() - t0, "usage": r.get("usage", {}), "provider": r.get("provider")}
    try:
        out["ans"] = json.loads(r["choices"][0]["message"]["content"])
    except Exception as e:
        out["error"] = f"parse: {e}: {str(r)[:200]}"
    return out


def run(d, n, models):
    meta, text = load(d)
    rng = random.Random(11)
    ids = rng.sample([m["id"] for m in meta.values() if 10 <= m["pct"] < 90 and 300 < m["chars"] < 60000], n)
    os.makedirs(os.path.join(d, "exp", "llm"), exist_ok=True)
    rep = ["## T6. LLM yes/no questions, full article text, temperature 0, asked twice", "",
           f"{n} random articles from the 10-90 percentile band (300-60k chars).", "",
           "| model | valid JSON | run agreement | cost $ | cost per 1M articles $ | p50 latency s | quote verbatim | dyk_hook true |",
           "|---|---|---|---|---|---|---|---|"]
    per_q, rows_by = {}, {}
    for model in models:
        jobs = [(i, k) for i in ids for k in (0, 1)]
        with cf.ThreadPoolExecutor(16) as ex:
            res = list(ex.map(lambda j: (j, ask(model, text[j[0]]["title"], text[j[0]]["text"])), jobs))
        rows = {}
        with open(os.path.join(d, "exp", "llm", model.replace("/", "_") + ".jsonl"), "w", encoding="utf-8") as f:
            for (i, k), r in res:
                f.write(json.dumps({"id": i, "run": k, **r}, ensure_ascii=False) + "\n")
                rows.setdefault(i, {})[k] = r
        ok = [r for (_, r) in res if "ans" in r]
        pairs = [(v[0]["ans"], v[1]["ans"]) for v in rows.values() if all("ans" in v.get(k, {}) for k in (0, 1))]
        agree = statistics.mean(a[q] == b[q] for a, b in pairs for q in Q) if pairs else 0
        per_q[model] = {q: statistics.mean(a[q] == b[q] for a, b in pairs) for q in Q} if pairs else {}
        cost = sum((r.get("usage") or {}).get("cost") or 0 for _, r in res)
        verb = [r["ans"]["most_absurd_sentence"].strip() in text[i]["text"] for (i, _), r in res if "ans" in r]
        hooks = sum(v[0].get("ans", {}).get("dyk_hook") is True for v in rows.values())
        rep.append(f"| {model} | {len(ok)}/{len(res)} | {100 * agree:.1f}% | {cost:.4f} | {cost / len(res) * 1e6:,.0f} | "
                   f"{statistics.median(r['secs'] for _, r in res):.1f} | {100 * statistics.mean(verb) if verb else 0:.0f}% | {hooks}/{n} |")
        rows_by[model] = rows
        errs = [r["error"] for _, r in res if "error" in r][:3]
        if errs:
            rep.append(f"| errors: {' / '.join(e[:120] for e in errs)} |||||||")
    rep += ["", "### Run-to-run agreement per question", "", "| question | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for q in Q:
        rep.append(f"| {q} | " + " | ".join(f"{100 * per_q[m].get(q, 0):.0f}%" for m in models) + " |")
    rep += ["", "### Cross-model agreement (run 0) per question", ""]
    if len(models) > 1:
        a, b = models[0], models[1:]
        for m in b:
            common = [i for i in ids if "ans" in rows_by[a].get(i, {}).get(0, {}) and "ans" in rows_by[m].get(i, {}).get(0, {})]
            if common:
                rep.append(f"- {a} vs {m}: " + ", ".join(
                    f"{q} {100 * statistics.mean(rows_by[a][i][0]['ans'][q] == rows_by[m][i][0]['ans'][q] for i in common):.0f}%" for q in Q))
    rep += ["", "### Articles flagged dyk_hook by every model (run 0), with each model's quoted sentence"]
    for i in ids:
        got = [rows_by[m].get(i, {}).get(0, {}).get("ans") for m in models]
        if all(g and g["dyk_hook"] for g in got):
            rep.append(f"- **{text[i]['title']}**")
            rep += [f"  - {m}: {g['most_absurd_sentence'][:220]}" for m, g in zip(models, got)]
    with open(os.path.join(d, "exp", "REPORT.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n\n")
    print("\n".join(rep))


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]), sys.argv[3:])

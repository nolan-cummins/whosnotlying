#!/usr/bin/env python3
"""Render a human review document for a set of batches: python3 -I review_doc.py <out.md> <batch id>...
Each item shows the PhD Mode version, the Simple version, the checker's verdict with its evidence, and a line to mark."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(HERE, "work", "batches")
pack = json.load(open(os.path.join(ROOT, "packs", "phd-mode.json"), encoding="utf-8"))
orig = {t["id"]: t for t in pack["topics"]}
out_path, batches = sys.argv[1], sys.argv[2:]
lines = []
n = 0
for b in batches:
    out = json.load(open(os.path.join(B, b + ".out.json"), encoding="utf-8"))
    cp = os.path.join(B, b + ".check.json")
    checks = {c["id"]: c for c in (json.load(open(cp, encoding="utf-8")).get("items", []) if os.path.exists(cp) else [])}
    for it in out["items"]:
        n += 1
        o = orig[it["id"]]
        truth = "truth" in o
        side = o["truth"] if truth else o["lies"][0]
        c = checks.get(it["id"], {})
        lines.append(f"## {n}. `{it['id']}` · {o['topic']} · {'truth' if truth else 'lie'} · {o['category']}\n")
        if truth:
            s = o["source"]
            lines.append(f"*{s['journal']} {s['year']} · {s['institution']} · <{s['url']}>*\n")
        lines.append("**PhD Mode**\n")
        lines.append(f"> {side['text']}\n")
        for f in side["facts"]:
            lines.append(f"> - {f}")
        lines.append("\n**Simple**\n")
        lines.append(f"> {it['statement']}\n")
        for f in it["facts"]:
            lines.append(f"> - {f}")
        if not truth and it.get("venues"):
            lines.append(f"> \n> Journals that publish this kind of work: {' · '.join(it['venues'])}")
        if truth and it.get("key_findings"):
            lines.append("\n<details><summary>Writer's key findings from the paper</summary>\n")
            for k in it["key_findings"]:
                lines.append(f"- {k}")
            lines.append("\n</details>\n")
        if it.get("notes"):
            lines.append(f"\n*Writer's note: {it['notes']}*\n")
        if c:
            lines.append(f"\n**Checker: {c.get('verdict', '?')}**" + (f" (statement {c.get('statement_verdict')})" if truth else ""))
            if truth:
                if c.get("statement_evidence"):
                    lines.append(f"\n- statement: {c['statement_evidence']}")
                for fc in c.get("facts", []):
                    lines.append(f"- {fc.get('verdict')}: \"{fc.get('fact')}\" ← {fc.get('evidence')}")
                if c.get("all_claims_in_abstract") is not None:
                    lines.append(f"- all claims in abstract: {c['all_claims_in_abstract']}")
            else:
                lines.append(f"\n- absurd number: {c.get('absurd_number')} · facts help the lie: {c.get('facts_help_the_lie')} · accidentally-true risk: {c.get('accidentally_true_risk')} · plausibility: {c.get('plausibility')}")
            for i in c.get("issues", []) or []:
                lines.append(f"- issue: {i}")
            if c.get("suggested_edits"):
                lines.append(f"- suggested edits: `{json.dumps(c['suggested_edits'], ensure_ascii=False)}`")
            if c.get("notes"):
                lines.append(f"- note: {c['notes']}")
        lines.append("\n**Your call:** 👍 / 👎 · comments:\n\n---\n")
open(out_path, "w", encoding="utf-8").write("\n".join(lines))
print(n, "items ->", out_path)

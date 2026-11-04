#!/usr/bin/env python3
"""
Validate topic packs (v2 schema, see sources/CONVERTING.md).

    python3 scripts/lint_packs.py packs/*.json        # errors exit 1, warnings are printed
    python3 scripts/lint_packs.py --quiet packs/*.json # errors only
    python3 scripts/lint_packs.py --check-archive packs/*.json  # also: every offline copy exists in $ARCHIVE_DIR

Errors: broken schema, duplicate ids / titles / statements, missing or oversized facts.
Warnings are heuristics for a human pass: a title word that only one side mentions, length
mismatch between truth and lie, a number on one side only.
"""
import json
import os
import re
import sys

ARCHIVE = os.environ.get("ARCHIVE_DIR", "/mnt/hdd2/liars-archive")

STOP = set("""a an the of and or to in on at by for with from into over under vs about after before
their his her its was were is are be been this that these those who what when where why how one
first last most more than""".split())
TRUTH_FACTS = (3, 5)
LIE_FACTS = (2, 4)
MAX_FACT_WORDS = 14
JOURNAL_FACT_WORDS = 20
# Hedges ("legend says...") on one side only tell guessers which statement is which.
HEDGE = re.compile(r"\b(legend(?:s|arily)?|reportedly|allegedly|according to|claim\w*|said to|rumou?r\w*|myth\w*|supposedly)\b", re.I)


def words(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def stem(w):
    return w[:5]  # crude: "pirates"/"piracy" -> "pirat"


def lint(paths, check_archive=False):
    errors, warnings = [], []
    titles, texts = {}, {}
    for path in paths:
        try:
            pack = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            errors.append(f"{path}: unreadable ({e})")
            continue
        if not pack.get("id") or not isinstance(pack.get("topics"), list):
            errors.append(f"{path}: needs 'id' and a 'topics' list")
            continue
        ids = set()
        papers = any((t.get("source") or {}).get("doi") for t in pack["topics"])  # a PhD-style pack: invented lies name journals to bluff with
        for t in pack["topics"]:
            where = f"{pack['id']}:{t.get('id')}"
            err = lambda m: errors.append(f"{where}: {m}")
            warn = lambda m: warnings.append(f"{where}: {m}")
            if not t.get("id") or t["id"] in ids:
                err("missing or duplicate id")
            ids.add(t.get("id"))
            if "used" in t or "used_as" in t:
                err("'used' flags don't belong in packs (history is tracked separately)")
            src = t.get("source")
            paper = isinstance(src, dict) and bool(src.get("doi"))
            if (t.get("group") or paper) and not (paper and src.get("journal") and t.get("group")):
                err("paper-based topics need 'group' and source.journal/doi (see sources/phd/GUIDE.md)")
            if paper and not (src.get("institution") and src.get("year")):
                err("paper source needs 'institution' (where the authors were) and 'year'")
            if src and not paper and not (isinstance(src, dict) and src.get("publisher") and src.get("quote")):
                err("web source needs 'publisher' and the supporting 'quote' (see sources/absurd/GUIDE.md)")
            for s_ in ([src] + list(src.get("also") or [])) if isinstance(src, dict) else []:
                if not (str(s_.get("url", "")).startswith("https://") and s_.get("archive")):
                    err("every source needs an https 'url' and an offline 'archive' copy")
                elif check_archive and not os.path.isfile(os.path.join(ARCHIVE, s_["archive"])):
                    err(f"offline copy missing: {ARCHIVE}/{s_['archive']}")
            if t.get("tags") is not None and not (isinstance(t["tags"], list) and all(isinstance(x, str) and x for x in t["tags"])):
                err("'tags' must be a list of strings")
            title, truth, lies = t.get("topic", ""), t.get("truth") or {}, t.get("lies") or []
            if not title or not t.get("category"):
                err("needs 'topic' (title) and 'category'")
            # Items may be one-sided (PhD pack: real truths and separately invented lies); paired ones get the pairing checks.
            if not (truth.get("text") or lies) or not all(l.get("text") for l in lies):
                err("needs truth.text and/or lies with text")
                continue
            if src and not truth.get("text"):
                err("a source/DOI belongs only on a truth")
            if title.lower() in titles:
                err(f"title '{title}' already used by {titles[title.lower()]}")
            titles[title.lower()] = where
            for s in ([truth["text"]] if truth.get("text") else []) + [l["text"] for l in lies]:
                if s in texts:
                    err(f"statement duplicated in {texts[s]}: {s[:50]}")
                texts[s] = where
            n = len(truth.get("facts", []))
            if truth.get("text") and not TRUTH_FACTS[0] <= n <= TRUTH_FACTS[1]:
                err(f"truth has {n} facts (want {TRUTH_FACTS[0]}-{TRUTH_FACTS[1]})")
            for i, l in enumerate(lies):
                jl = [f for f in l.get("facts", []) if f.startswith("Journals like ")]
                if papers and not truth.get("text") and len(jl) != 1:
                    err(f"lie {i} needs exactly one 'Journals like X and Y publish papers on ...' fact in a paper pack")
                n = len(l.get("facts", [])) - len(jl)  # the journals line doesn't count toward the fact budget
                if not LIE_FACTS[0] <= n <= LIE_FACTS[1]:
                    err(f"lie {i} has {n} facts (want {LIE_FACTS[0]}-{LIE_FACTS[1]})")
            for f in truth.get("facts", []) + [f for l in lies for f in l.get("facts", [])]:
                if len(words(f)) > (JOURNAL_FACT_WORDS if f.startswith("Journals like ") else MAX_FACT_WORDS):
                    err(f"fact over {MAX_FACT_WORDS} words: {f}")
                if f.lstrip().startswith(("•", "-", "*")):
                    err(f"fact has a bullet character (the UI adds it): {f}")
            if not (truth.get("text") and lies):
                continue
            tw = len(words(truth["text"]))
            title_stems = {stem(w) for w in words(title) if w not in STOP and len(w) > 2}
            truth_stems = {stem(w) for w in words(truth["text"])}
            for i, l in enumerate(lies):
                lw = len(words(l["text"]))
                if not 0.6 <= lw / max(tw, 1) <= 1.6:
                    warn(f"lie {i} is {lw} words vs truth {tw}")
                if bool(re.search(r"\d", truth["text"])) != bool(re.search(r"\d", l["text"])):
                    warn(f"a number/date appears on only one side (lie {i})")
                if bool(HEDGE.search(truth["text"])) != bool(HEDGE.search(l["text"])):
                    warn(f"hedging word ('legend', 'claimed'...) on only one side (lie {i})")
                lie_stems = {stem(w) for w in words(l["text"])}
                for s in title_stems:
                    if (s in truth_stems) != (s in lie_stems):
                        side = "truth" if s in truth_stems else f"lie {i}"
                        warn(f"title word '{s}..' appears only in the {side}: '{title}'")
    # A lie's background facts shouldn't name the subject of another topic's truth
    # (a liar would be holding a spoiler for someone else's statement).
    names = lambda s: set(re.findall(r"\b[A-Z][a-z]{3,}(?:\s[A-Z][a-z]+)+\b", s))
    truth_names = {}
    for path in paths:
        try:
            for t in json.load(open(path, encoding="utf-8")).get("topics", []):
                for n in names((t.get("truth") or {}).get("text", "")):
                    truth_names.setdefault(n, t.get("id"))
        except (OSError, ValueError):
            pass
    for path in paths:
        try:
            pack = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for t in pack.get("topics", []):
            for l in t.get("lies") or []:
                for f in l.get("facts", []):
                    for n in names(f):
                        if truth_names.get(n) not in (None, t.get("id")):
                            warnings.append(f"{pack.get('id')}:{t.get('id')}: lie fact names '{n}', the subject of {truth_names[n]}'s truth")
    return errors, warnings


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        # No paths given (e.g. `python -m scripts.lint_packs` in CI): lint the repo's own packs.
        import glob
        packs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "packs")
        args = sorted(p for p in glob.glob(os.path.join(packs_dir, "*.json")) if not os.path.basename(p).startswith("_"))
        if not args:
            sys.exit(__doc__)
    errors, warnings = lint(args, "--check-archive" in sys.argv)
    if "--quiet" not in sys.argv:
        for w in warnings:
            print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors else 0)

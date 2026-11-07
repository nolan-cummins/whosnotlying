# PhD Mode: Simple — writing guide and how the pack was made

`packs/phd-mode-simple.json` is a rewrite of `packs/phd-mode.json`: the same papers, the same topic ids,
the same tags, categories and sources, with every statement and fact rewritten to the rules below.
It declares `"derived_from": "phd-mode"`, so a finding heard in either pack is blocked in both, and
the linter lets the two packs share titles (never statements).

## Why

Game night, November 2026 (five players, PhD Mode): the statements were too long and too specific,
with just as wordy bullet points; non-native speakers struggled with the technical terms and the pile
of numbers; the bullets often summarised the paper's discussion instead of backing the claim; lies
carried numbers in the statement (95% of PhD Mode lies vs 63% of truths) and some of those numbers
were absurd to anyone in the field; and the "Journals like X and Y publish papers on …" bullet read as
a bluffing tip that gave liars away, because truths show their journal, year and link after questioning.

## Rules

**Statement** (truth and lie alike)
- The main conclusion in ONE plain sentence, at most 28 words, that someone could repeat after hearing
  it once. Everyday words; no acronyms, gene / protein / compound / material names or jargon.
- At most ONE number, and only when the number is the point. Lies usually carry none: the liar makes
  the figures up when asked, which is the fun. Nothing an expert would find absurd.
- Causation only where the paper claims it; otherwise "were more likely to", "went with".

**Facts**
- Truths: 3-5 bullets of at most 14 words, each a finding or a concrete fact of the study: the sample,
  the time span, how the key thing was measured or defined, the striking secondary result, what the
  effect depended on. The numbers live here. Never an argument ("some argue"), never discussion-section
  hedging, no institution or author names, no DOI.
- Lies: 2-4 bullets of true general background on the real concepts the statement uses; never a fact
  that supports the invented part.

**Lies also carry `venues`**: 2-3 real journals that publish this kind of work, shown on the phone apart
from the facts under "Journals that publish this kind of work", with a reminder that every truth comes
with a journal, a year and a link. The old journals bullet is gone.

**Summary** (never shown; embedded for expertise matching): 80-150 words of the paper's key findings.

Example, from the review at the table (`t07-26`):
- PhD Mode: "Comparing 39,000 ancient homes at 770 sites over 10,000 years, archaeologists found
  fortified settlements, a sign of war, usually had bigger wealth gaps, but not where government was
  more collective."
- Simple: "Archaeologists found that ancient settlements built with fortifications for war usually had
  bigger gaps between large and small homes, a sign of wealth inequality." Facts: "Compared about
  39,000 homes at 770 settlements worldwide" · "Homes span the last 10,000 years" · "Wealth gap
  measured by house-size differences within each settlement" · "Where governance was more collective,
  war did not widen the gap".

## Pipeline (`sources/phd/simple/`)

Everything runs from the game repo root with `python3 -I sources/phd/simple/pipeline.py <cmd>`.

1. **fetch**: for each DOI in PhD Mode, OpenAlex (title, abstract, open-access PDF links), then
   Europe PMC full text (JATS XML, references and metadata stripped, sections in reading order), then
   the OA PDF through `pdftotext`, else the abstract alone. Texts are capped at 6,500 words and stored
   under `sources/raw/openalex/texts/simple/` (git-ignored); `texts-index.json` records, per DOI,
   whether the writer had the full text or only the abstract.
2. **batches**: truths grouped by paper, four papers per batch; lies thirty per batch. Each batch file
   carries the rules (`prompts/writer_truth.md`, `prompts/writer_lie.md`), the paper text and the PhD
   Mode items.
3. **Writer** (a Claude Opus subagent per batch, run from Claude Code): for every truth it first lists
   the paper's key findings, then writes the statement, the facts and the summary; for every lie the
   simplified statement, background facts and venues. Output: `<batch>.out.json`.
4. **Checker** (a second Opus subagent with a fresh context, `prompts/checker_*.md`): it sees only the
   paper text and the proposed item, never the writer's reasoning. For truths it gives a verdict per
   claim (statement and every fact: supported / unsupported / contradicted, with the quote that backs
   it), checks the rules, and for abstract-only papers states whether every claim is literally in the
   abstract. For lies it checks the rules, absurd numbers, facts that help the lie and the risk that
   the invention is accidentally true. Output: `<batch>.check.json`.
5. **validate**: deterministic checks (lengths, number count, fact counts, venues, statement changed,
   no journals line) merged with the checker's verdict. An item is accepted only when the lint is clean
   and the checker passed it; **an abstract-only truth is accepted only when the checker confirmed every
   claim is in the abstract**. Everything else goes to `review.jsonl` for a human; every verdict goes to
   `checks.jsonl` (the audit trail that is committed).
6. **build**: accepted items become `packs/phd-mode-simple.json`; then `npm run lint:packs`.

Items that fail get one more writer pass with the checker's notes; items that fail again stay out of the
pack until a person settles them.

## Feedback log
- **Pilot (10 items: 7 truths incl. `t07-26`, 3 lies incl. `l20-02`)**: awaiting review.

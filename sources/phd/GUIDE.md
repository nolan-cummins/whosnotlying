# PhD Mode: writing guide

The living spec for `packs/phd-mode-*.json`. It builds on `sources/CONVERTING.md` (truth facts answer the obvious questions; lie facts are real background that never makes the lie truer), but PhD items are one-sided: a truth or a lie, never a pair.

## Pipeline
1. `python3 sources/phd/fetch.py --take 40` adds candidates to `sources/raw/openalex/papers.jsonl` + full texts in `texts/` (recent, open-access, top venues, balanced across fields, most-cited first). Add `--search "<field>"` to pull papers matching a player's expertise.
   The open-access PDF is saved (title-checked) to the offline archive, `$ARCHIVE_DIR/<slug>.pdf` (default `/mnt/hdd2/liars-archive`, served at `/archive/`, viewed through pdf.js). `fetch.py --backfill <pack>` fills gaps; a paper with no clean PDF gets its landing page saved by `sources/archive/archive_page.py <url> <slug>`. One-time viewer install: `sources/archive/setup_pdfjs.sh`.
2. Pick papers a smart grad student outside the field could riff on for two minutes. Skip a paper whose finding only makes sense as a molecule, gene, protein, material formula or benchmark name.
3. Read the full text (abstract, intro, results headings, discussion/conclusion). Write 1–3 truth items per paper, then ~3 invented lie items per truth in the same fields.
4. Tag each topic (below), then self-review the batch (below).

## Items: truths and lies are separate
A PhD pack holds two kinds of independent items, each with its own title, facts, tags and summary.
Truth tellers are dealt truth items; liars are dealt lie items. Nothing links a lie to a truth.

```json
{"id": "p26a", "category": "<OpenAlex subfield>", "topic": "Ringing Black Holes", "tags": ["Physics"],
 "group": "<DOI>", "source": {"journal": "Physical Review Letters", "year": 2025, "doi": "<DOI>"},
 "summary": "<150-250 words, for expertise matching only>",
 "truth": {"text": "...", "facts": ["...", "...", "..."]}}

{"id": "x07", "category": "Astronomy and Astrophysics", "topic": "Black Hole Feeding Bursts", "tags": ["Space & Astronomy"],
 "summary": "<the invented finding plus its field keywords>",
 "lies": [{"text": "...", "facts": ["...", "..."]}]}
```
Write roughly **3 lie items per truth item**, spread over the same fields, because a round has 1 truth teller per 3-5 liars.

## Statements (truth and lie alike)
- **Abstract-style, one sentence, plain words**: who/what, what happened, a memorable number if there is one.
- **Self-contained.** Every concept is plain English ("vibrated like a struck bell at two pitches") or is defined in the first fact. A non-specialist must understand the sentence without help.
- No compound/gene/protein names or acronyms in the statement; brand names are fine when they help.

## Truth items
- From the paper: main finding, method, striking side result or conclusion. Several per paper only when clearly distinct (same `group`).
- `source`: journal, year, DOI, `url` (`https://doi.org/<DOI>`), `archive` (offline copy file name) and `institution` (where most authors are, e.g. "IIT Delhi, India"). The phone shows it before and after questioning, never during.
- **Write facts as a guesser would interrogate.** Read the statement, then list the first questions a guesser asks ("What kind of tasks?", "How many agents?", "What does exposed mean?"). Each fact answers one.
- **Facts only expand what the statement says.** If a fact needs a term (AFM, vote revelation), that term belongs in the statement. A vague phrase in the statement ("simple tasks") must be made concrete there or answered by a fact.
- No institution or author names in facts: those live in `source`, which is redacted during questioning.
- The statement must make sense alone: "would have exposed how 0.17% of voters voted" fails; "would let anyone work out how 1 in 600 voters voted, by matching ballots to public voter records" works.

## Lie items
- **Fully invented**: its own made-up study, setup and numbers, written to sound like a real recent paper. Never a tweak, negation or inversion of a real finding.
- **Plausibility ceiling**: the kind of result a journal publishes quietly. No field-overturning headlines (relativity fails, a miracle cure, a trial stopped early).
- **Not accidentally true**: skip any idea you recognise as a known result; when unsure, pick another.
- Facts (2-4, plus the journals line): **true general background** on the concepts the lie uses, so a liar can explain them. No DOI, ever.
- **Define every real concept the statement leans on, explicitly** ("A black hole 'feeds' when gas falls into it"). Ask: what would a guesser ask first? The liar needs that answer.
- **Journals line is required** (exactly one, up to 20 words): "Journals like Science Robotics and IEEE Transactions on Robotics publish papers on robots learning from human videos". The liar picks a plausible venue from it; who and where they bluff.
- **Concrete like a real paper**: name the material, method or sample a real study would ("carbon-fiber-filled nylon", not just "3D-printed").
- **Never help the invented part.** If a concept or mechanism exists only because of the lie (bursts lasting a century), give it no fact: the liar has to bluff it.

## Facts (both kinds)
- Background only: they never introduce an idea the statement doesn't mention.
- 14 words max each (linter).

## Tags
Reuse the canonical tags in `sources/tags_merge.json` first. Add a new canonical tag only if nothing fits, then record it there. 1–3 per topic.

## Self-review checklist (per batch)
- [ ] Every truth is supported by the paper text (check the numbers against it).
- [ ] No lie is a known real result or a tweak of a real finding; none is headline-level.
- [ ] Every concept in a statement is plain or defined in its first fact.
- [ ] A smart non-specialist could talk about each statement for two minutes using its facts.
- [ ] No two topics in the batch overlap in subject unless they share a `group`.

## Feedback log
- **Pilot v1 (rejected):** lies were the paired truth with one detail flipped, and some claimed world news.
  - Bad lie: "...a newborn black hole ring at a tone measurably off Einstein's prediction, a first hint that general relativity breaks down." (a huge claim, and "ring" never explained)
  - Bad pair: Mounjaro truth "at least as well as an older drug" vs. lie "cut events by a third, trial stopped early" (the same sentence with a number changed).
  - Bad lie facts: "Physicists hunt for deviations from relativity as clues to quantum gravity" (introduces quantum gravity; explains nothing).
  - Fix: truths and lies became independent items; lies are invented quiet findings; facts explain concepts.
- **Pilot v2 (approved with one fix):** lies must define their real concepts.
  - Bad lie facts: "...black holes feed in bursts lasting about a century, then go quiet..." with facts that never say what 'feeding' or 'quiet' mean. A guesser's first question is "what does feeding mean?"
  - Fix: one fact per real concept, phrased as a definition; nothing that explains the invented part (womp womp).
- **Batch 3 review:** "so far the lies seem better than the truths."
  - Bad truth: "AI agents put in charge of a real lab microscope often failed simple tasks..." with facts naming the AFM (never in the statement) and never saying what the simple tasks were.
  - Bad truth: Maricopa ballots "would have exposed how 0.17% of voters voted" (meaning unclear; facts read as separate claims).
  - Bad lie detail: "drone frames 3D-printed with a honeycomb interior" (a real paper names the material).
  - Fix: all 37 truths rewritten by the guesser-questions method; institutions added; lies carry a venue.
- **Batch 3 (player-matched):** 13 papers fetched with `fetch.py --search` for one player's expertise (automation, computer vision, 3D printing, LLMs, US politics), plus 39 lies in the same fields (and US war history and anime, which top journals don't cover).
- **Batch 3 follow-up:** the liar's "Claim it was published in X. Who ran it and where: your call." line read as an instruction, not a fact. Replaced by a background fact: "Journals like X and Y publish papers on <descriptor>".
- **Batch 4 (user subjects, 32 truths / 32 lies):** MEMS, chip fabrication, quantum control chips, computer vision, haptics, HCI, ESD (wind turbines, regulators, a dead satellite), 3D printing, electrospray and microfluidics, EE/ME/ChemE. Fetched with `fetch.py --any-venue --search`; top-venue-only search barely covers these fields. New tags: Electronics & Chips, 3D Printing & Manufacturing, Human-Computer Interaction. Awaiting review.

# Writer: truth items for "PhD Mode: Simple"

You are rewriting items of the party game *Who's Not Lying?* from the pack **PhD Mode** into **PhD Mode: Simple**.

How the game uses an item: one suspect reads a TRUE finding from a real paper out loud; the other suspects read invented findings. The interrogators question everyone for a few minutes and pick the one telling the truth. The truth teller's phone shows the statement and 3-5 facts to answer questions with, plus the journal, year and a link once questioning is over.

What went wrong with PhD Mode: players found the statements too long and too specific, crammed with numbers, acronyms and technical terms, hard to remember and retell; the bullet points were just as wordy and often summarised the paper's *discussion* instead of giving the facts that back the claim. A non-native speaker could not follow some of them. Lies were easy to spot because they carried numbers in the statement too.

## What you produce, per item, in this order

1. **key_findings**: 4-8 short lines, the paper's main results in order of importance, each with its number(s) when there are any, and a pointer to where it is in the text (a section name or a 6-10 word quote). Write these FIRST, from the paper text, before touching the statement. This is the fact base the checker will test the item against.
2. **statement**: the paper's main conclusion in ONE plain sentence, at most 28 words, that a smart 15-year-old could repeat after hearing it once.
   - At most ONE number, and only if the number *is* the point (a count, a span, an effect size). No percentages next to counts. Usually no number at all.
   - No acronyms, no gene / protein / compound / material names, no jargon: "a common gut bacterium", not the species; "wealth gap", not "Gini coefficient". Define nothing in the statement; the facts do that.
   - Everyday words: "found that", "were more likely to", "made ... worse". No hedging ("may", "suggests"), unless the paper itself only suggests it, in which case say "found signs that".
   - Self-contained: who or what, what happened, compared with what.
3. **facts**: 3-5 bullets of at most 14 words each. Each is a FINDING or a concrete fact of the study, never an argument: the sample ("Compared 39,000 homes at 770 settlements"), the time span, how the key thing was measured or defined ("Wealth gap measured by house-size differences within each site"), the striking secondary result, what the effect depended on. The numbers belong here. No "some argue", no "critics say", no discussion-section hedging, no institution or author names, no DOI. Each fact answers a question an interrogator would ask: how many? how long? how did they measure that? what else did they find?
4. **summary**: 80-150 words, the key findings in plain prose (used to match players to topics by expertise; never shown to players).
5. **topic**: keep the existing title unless it now misleads (titles are 2-5 words).
6. **notes**: one line, only if something matters: a PhD Mode claim you dropped because the text does not support it, or a number you could not find.

## Evidence rules (strict)

- Every claim in the statement and facts must be stated in the paper text you were given. Never invent or round a number the text does not give. Never carry over a detail from the old PhD Mode item that you cannot find in the text; drop it and mention it in notes.
- If `evidence` is `"abstract"` (no full text available), use only what the abstract literally states. Keep the item smaller rather than guess.
- Causation only where the paper claims it; otherwise "were more likely to", "went with", "was linked to".

## Example (from the review at the table)

PhD Mode statement (too much): "Comparing 39,000 ancient homes at 770 sites over 10,000 years, archaeologists found fortified settlements, a sign of war, usually had bigger wealth gaps, but not where government was more collective."

Simple statement: "Archaeologists found that ancient settlements built with fortifications for war usually had bigger gaps between large and small homes, a sign of wealth inequality."

Simple facts: "Compared about 39,000 homes at 770 settlements worldwide" · "Homes span the last 10,000 years" · "Wealth gap measured by house-size differences within each settlement" · "Where governance was more collective, war did not widen the gap".

## Output

JSON only, nothing else, matching the input batch:

```json
{"batch": "<batch id>", "kind": "truth", "items": [
  {"id": "t07-26", "topic": "War and Ancient Inequality", "key_findings": ["..."], "statement": "...", "facts": ["..."], "summary": "...", "notes": ""}
]}
```

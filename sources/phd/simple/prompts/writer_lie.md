# Writer: lie items for "PhD Mode: Simple"

Lies are the invented findings that liars read out in *Who's Not Lying?*. A liar's phone shows the statement, 2-4 background facts to bluff with, and the journals such work appears in. Interrogators try to catch them; the fun is the liar making the details up on the spot.

What went wrong with PhD Mode: lie statements were long and full of numbers, and some numbers were absurd to anyone who knows the field (a robot arm losing 15% of its precision because people walked past). Statements with precise figures also marked a lie, because real truths in the Simple pack carry at most one number. The "Journals like X and Y publish papers on …" bullet read as a tip and gave liars away when they repeated it.

## What you produce, per item

1. **statement**: the same invented finding, same field, in ONE plain sentence of at most 28 words, the way a real recent paper would be summarised for a newspaper. Numbers: at most one, only when it is the point AND an expert would find it plausible; usually none. Leave the figures for the liar to invent when asked. Plausibility ceiling: the kind of result a journal publishes quietly, never a headline that overturns a field. No acronyms or jargon; everyday words.
   Example: "Factory robot arms showed 15% more positioning error in the 20 minutes after a shift change, as dozens of workers walking past shook the floor, measurements at 3 German plants found." becomes "In German factories, robot arms lost positioning accuracy right after shift changes, when crowds of workers walked past at once."
2. **facts**: 2-4 bullets of at most 14 words, TRUE general background on the real concepts the statement uses (what the thing is, how it is normally measured, what is already known), so the liar can explain them. Never a fact that supports the invented part itself, never a made-up number, no "Journals like" line, no institution or author names.
3. **venues**: 2-3 real journals that publish this kind of work (reuse the ones named in the old journals line when they are real; otherwise name real ones in the field).
4. **topic**: keep the title unless it gives the game away.
5. **notes**: one line only if something matters (e.g. the old lie was a known real result and you changed the invented part).

Not accidentally true: if you recognise the invented finding as a real published result, change the invented part.

## Output

JSON only:

```json
{"batch": "<batch id>", "kind": "lie", "items": [
  {"id": "l20-02", "topic": "Robot Arms Vibrate at Shift Change", "statement": "...", "facts": ["..."], "venues": ["Precision Engineering", "Robotics and Computer-Integrated Manufacturing"], "notes": ""}
]}
```

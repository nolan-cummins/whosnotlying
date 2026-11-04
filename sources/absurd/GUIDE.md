# Absurd pack: writing guide

The living spec for `packs/absurd-*.json`. Truths are real facts so absurd that nobody can dismiss a statement just for being ridiculous; lies are invented in the same style. Like the PhD pack, items are one-sided: a truth or a lie, never a pair. The general rules in `sources/phd/GUIDE.md` (self-contained statements, background-only facts, 14-word facts) apply here too.

## Truths: obscure first, then research, archive, write
0. **Obscure, or don't bother.** Players must not have heard it. Gate every candidate with `python3 scripts/fame.py "<Wikipedia article title>"`: over ~1,000 views/month (2025) is too well known, and no article at all is best. Also reject anything you'd expect in a "50 weird facts" listicle, an Ig Nobel that made headlines, or a story Perplexity returns from ten outlets. Ids cut for fame live in `scripts/famous.txt` (abuild skips them).
   Where obscure finds come from (not the first page of a web search): low-view Wikipedia articles (`Wikipedia:Unusual articles` filtered by fame.py), historical newspapers (Chronicling America, Trove, British Newspaper Archive snippets), court rulings and Hansard, patent records, museum collection records and local-history society pages, regional news, recent papers in odd niches.
1. **Find it.** Perplexity search (`mcp__Perplexity__perplexity_search`) for the claim and its best source: a museum, government or university page, a reputable outlet (BBC, Smithsonian, Britannica), or the original paper. Wikipedia is fine as a lead, never as the only source.
2. **Check it.** Read what the source actually says. Drop anything a reputable source calls a myth or unverified, or word it the way the source does ("is reported to have", "said to"). A second independent source goes in `source.also` when the first is thin or the claim is surprising.
3. **Archive it.** `python3 sources/archive/archive_page.py <url> absurd-<id>` saves the offline copy to `$ARCHIVE_DIR` (default `/mnt/hdd2/liars-archive`, served at `/archive/`). PDFs are saved as PDFs and shown through pdf.js.
4. **Quote it.** `source.quote` holds the sentence from the archived copy that supports the statement (the linter requires it). Every number in the statement and facts must appear in a source.

```json
{"id": "a05", "category": "Military History", "topic": "The Pig War", "tags": ["Military History", "Animals"],
 "source": {"publisher": "U.S. National Park Service", "year": 2024, "url": "https://...", "archive": "absurd-a05.html",
            "quote": "...the only casualty was a pig.", "also": [{"publisher": "...", "url": "...", "archive": "..."}]},
 "summary": "<plain description + keywords, for expertise matching>",
 "truth": {"text": "...", "facts": ["...", "...", "..."]}}
```

## Lies
- **Invented and equally absurd**: same flavours as the truths (odd laws, animal stunts, bizarre history, strange experiments). A guesser must not be able to spot the lie by its weirdness alone.
- **Not accidentally true.** Absurd reality is huge: search before using an idea (cheese cannonballs, a man who mailed himself to Australia, Queen Victoria's rat-catcher all turned out real). If it exists, it becomes a truth instead.
- **Concrete**: a place, a year, a number, a named animal.
- Facts (2-4): true background the liar can use ("The World Snail Racing Championships are held in Congham, Norfolk"); nothing that supports the invented part. No journals line (that's for paper packs).

## Feedback log
- **Pilot (25 truths / 25 lies):** awaiting review.
- **2026-11-01, user:** some truths were already familiar. Fame check: 61 of 64 truths had articles at 2,000-120,000 views/month (Emu War, Dyatlov Pass, Hachiko...). Cut them all; added rule 0 and fame.py.
- **Lies collide with reality often** (~40% of first drafts were real): search every lie idea before writing it.
- **Check the archived text before quoting**: about a third of guessed URLs archive a 404 or bot-check page without failing.

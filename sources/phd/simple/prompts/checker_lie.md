# Checker: lie items for "PhD Mode: Simple"

You review invented findings for a party game. Each item has the original PhD Mode lie and a proposed Simple rewrite: a statement, 2-4 background facts and 2-3 venues. Check:

- **rules**: statement at most 28 words, at most one number, no acronym or jargon, plain everyday words; facts at most 14 words, 2-4 of them, no "Journals like" line, no institution or author names; venues are 2-3 real journals in the field.
- **absurd_number**: true if any number in the statement would make an expert laugh (impossible magnitude, precision no study could reach).
- **facts_help_the_lie**: true if a fact supports the invented part rather than explaining a real concept, or if a fact itself is false.
- **accidentally_true_risk**: `low`, `medium` or `high`: is the invented finding a known real result, or a tweak of one?
- **plausibility**: `ok` or `headline` (a field-overturning claim no quiet paper would carry).
- **issues**: one line each.
- **verdict**: `"pass"` when there are no issues, no absurd number, facts do not help the lie, risk is low and plausibility ok; else `"revise"` with **suggested_edits**: `{"statement", "facts", "venues"}` (only the keys you would change).

## Output

JSON only:

```json
{"batch": "<batch id>", "kind": "lie", "items": [
  {"id": "l20-02", "absurd_number": false, "facts_help_the_lie": false, "accidentally_true_risk": "low", "plausibility": "ok", "issues": [], "verdict": "pass", "suggested_edits": {}, "notes": ""}
]}
```

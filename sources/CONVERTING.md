# Converting trivia sources into topic packs

`sources/raw/` holds downloaded trivia in any format (CSV, JSON, TXT, PDF, OpenTDB dumps, scraped lists). Put each download in its own subfolder, named `raw/<source-name>/`, and add a one-line `SOURCE.txt` with the URL and its license.

The output is a pack JSON in `packs/`. The game auto-loads any `*.json` dropped there, with no restart needed, and the Admin Console lists it under **Topic Packs**.

Whoever converts a source, whether a person or an LLM, follows the steps below exactly.

## How the game uses a topic

Every suspect gets one topic. The **title** shows publicly, on phones and on the TV. One suspect reads the topic's **truth**. Everyone else reads one of their own topic's **lies**. The guessers then interrogate everyone.

So:
- **The title must fit the truth and the lie equally.** If the title only makes sense for one statement, the guessers can tell which is real without asking anything.
- **The truth's facts must answer the questions people will actually ask:** who, what is X, why, how, and what happened next.
- **The lie's facts are real background** that lets a liar talk about the topic convincingly. They never make the lie more true.

## Pack format (v2)

```json
{
  "id": "my-pack-1",
  "name": "My Pack 1",
  "version": 2,
  "topics": [
    {
      "id": "top_1",
      "category": "Religious History",
      "topic": "Papal Trials",
      "truth": {
        "text": "In 897 AD, Pope Stephen VI had the rotting corpse of his predecessor exhumed, dressed in papal robes, and placed on trial.",
        "facts": [
          "The dead pope, Formosus, had crowned Arnulf, enemy of Stephen's Spoleto backers",
          "Stephen's faction wanted Formosus's acts and ordinations voided",
          "A deacon stood beside the corpse to answer for it",
          "Found guilty; his blessing fingers were cut off, body thrown in the Tiber",
          "Public outrage got Stephen jailed and strangled months later"
        ]
      },
      "lies": [
        {
          "text": "In 1345, the King of Bohemia appointed his favorite wolfhound an honorary member of the royal council.",
          "facts": [
            "Wolfhounds are giant hunting dogs, prized by medieval nobles",
            "A royal council advised the king on law, war and taxes",
            "Bohemia was a kingdom in today's Czech Republic, ruled from Prague",
            "King John of Bohemia ruled 1310 to 1346"
          ]
        }
      ]
    }
  ]
}
```

- `id` (pack) is lowercase with dashes. Keep it stable, because history records use it.
- `topics[].id` is `top_<n>`. Never reuse an id or renumber. Rewording, fact edits and new lies keep the id. A changed *truth* claim gets a new id, so old play history doesn't wrongly block it.
- There is no `used` field. Play history lives in `data/history.json`, keyed by `pack:topic:t` or `pack:topic:f<N>`.
- Facts are plain strings. The UI adds the bullet characters.
- `lies` may hold several lies. The game picks one at random.

## Procedure

### 1. Extract candidates
Read the raw file and pull out candidate facts. A short script into a scratch CSV is fine. Keep a candidate only if all of these hold:
- **Surprising.** Most people would guess it's false.
- **Verifiable.** It's on Wikipedia or a reputable source. Check every number and date.
- **Not common knowledge.** No "the Great Wall is visible from space" style myths, and no famous trivia everyone has heard.
- **Tellable as a story.** It has an actor, an action and an outcome. Bare Q&A trivia ("What is the capital of Peru?") fails this test, so reject it or reframe it into an event.

### 2. Write the truth (`truth.text`)
- One sentence, 15–35 words.
- Concrete: a date, place, number or name.
- No hedging ("reportedly", "some say") and no exclamation marks. If one side has to hedge ("legend says…"), the other side must too, or the hedge itself gives the answer away.
- **Names:** leave people unnamed ("a jockey", "an American farmer") unless they're famous or the name matters to the story (Nicolas Cage, Alexander Fleming, Wojtek the bear). Put the name in a fact bullet instead ("The jockey was Frank Hayes"). Lies follow the same rule, so a named truth next to an unnamed lie doesn't stand out.

### 3. Write the truth facts (`truth.facts`, 3–5 bullets)
Before writing, list the 5 questions a skeptical guesser would ask, for example: *Why did they do it? Who was it? What is a ___? How did it work? What happened afterwards?* Each bullet answers one of them.
- 14 words or fewer each.
- No restating the statement, and no trivia without context. "Three blessing fingers were cut off" is bad. "Found guilty; his blessing fingers were cut off" is good: the context makes it part of the story.
- At least one bullet gives the **reason or motive**, and one gives the **outcome**.
- Define any unusual term in the statement (wolfhound, TP-82, synod).

### 4. Write the lie (`lies[].text`)
- **The same subject as the truth**, or at least the same subject as the title. If the title is "Ashes in Space", the lie is also about ashes in space.
- Within ±40% of the truth's word count.
- The same "texture": if the truth has a date, place and number, so does the lie.
- Plausible but false. Check that it isn't accidentally true, and that it doesn't contradict a fact everyone knows.
- No telltale absurdity, no jokes, and no impossible scale.

### 5. Write the lie facts (`lies[].facts`, 2–4 bullets)
Real, checkable background that grounds the lie: what the nouns are, where the place is, what the institution did, and who ruled when.
- They **must not** invent new claims or confirm the lie itself. "The wolfhound attended meetings for years" is wrong. "Royal councils advised on law, war and taxes" is right.
- 14 words or fewer each.

### 6. Write the title (`topic`)
- 2–4 words, neutral, e.g. "Papal Trials", "Military Animals", "Odd Royal Appointments".
- **It must fit both statements.** Test: cover the statements and ask whether the title alone leans toward either one. Every specific word in the title (a country, an object, a place) must apply to both the truth and the lie.
- It must be unique across all packs (the linter checks this).
- `category` is a broader shelf ("Space Oddities", "Strange Laws"). Several topics can share one.

### 7. Lint
```sh
python3 scripts/lint_packs.py packs/my-pack-1.json
```
- **ERROR** lines must be fixed. They cover the schema, duplicate ids, titles or statements, fact counts and lengths, and leftover `used` flags.
- **WARN** lines are heuristics for your review:
  - a title word appearing on only one side
  - a length mismatch
  - a number on one side only.

  Fix each one, or confirm it's a false positive. For example, "Swiss Laws" with a lie set in Geneva is fine.

### 8. Spot-check and ship
- Read 10 random topics aloud as if you were playing. Can you tell the truth from the lie using only the title? Can you answer "why?" from the truth facts?
- Copy the file into `packs/`. It's live immediately. On the Docker deploy, the packs dir is `/app/data/packs` in the `deployment_game_data` volume, and the image seeds it from the repo's `packs/` on start.

## Prompt template (for an LLM doing the conversion)

> You are converting trivia into topics for a party game where one player tells a true statement and others tell lies on related topics. Follow `sources/CONVERTING.md` steps 2–6 exactly. Input: a batch of verified facts. Output: a JSON array of v2 topic objects (`id`, `category`, `topic`, `truth{text,facts}`, `lies[{text,facts}]`). Every title word must apply to both the truth and the lie. Truth facts answer why / who / what-is / what-happened-next. Lie facts are real background only. Do not add `used` fields.

Then lint the result and fix it.

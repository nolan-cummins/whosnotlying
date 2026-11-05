# Contributing

## Bugs and ideas

Open an issue with what you did, what you expected and what happened. For rules questions, say which stage the game was in and how many players there were.

## Question packs

New packs are welcome. Follow the schema in the README, keep statements to one or two sentences, give the truth at least three facts, and run the linter before opening a pull request:

```bash
npm run lint:packs
```

Only use sources you may redistribute, and credit them in the topic's `source` field. Packs that quote copyrighted text at length will not be merged.

## Code

```bash
npm install
npm test
```

Keep the game free of dependencies beyond the one in `package.json` (the QR encoder) and of build steps: it is meant to run from a laptop with `npm start`, and Node 22 runs the TypeScript as is (so only erasable syntax: no enums, no parameter properties). Add a test for any rule change; `tests/rotation.test.ts` guards fairness and `tests/server.test.ts` guards what each page is allowed to see.

## Pull requests

One change per pull request, with the tests green. Describe the player-visible effect in the description.

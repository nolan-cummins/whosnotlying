# Contributing

## Bugs and ideas

Open an issue with what you did, what you expected and what happened. For rules questions, say which stage the game was in and how many players there were.

## Question packs

New packs are welcome. Follow the schema in the README, keep statements to one or two sentences, give the truth at least three facts, and run the linter before opening a pull request:

```bash
python3 -m scripts.lint_packs
```

Only use sources you may redistribute, and credit them in the topic's `source` field. Packs that quote copyrighted text at length will not be merged.

## Code

```bash
pip install -r requirements.txt
python3 -m pytest -q
```

Keep the game dependency-free beyond `requirements.txt`: it is meant to run from a laptop with `python3 -m src.main`. Add a test for any rule change; `tests/test_rotation.py` guards fairness and `tests/test_server.py` guards what each page is allowed to see.

## Pull requests

One change per pull request, with the tests green. Describe the player-visible effect in the description.

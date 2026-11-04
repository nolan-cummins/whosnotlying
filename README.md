# Who's Not Lying?

A party game of one truth and many bluffs, played on phones with a TV as the table.

Everyone but the interrogator is a suspect. Each suspect's phone shows a topic and a statement about it. One statement is true, and that suspect gets a dossier of real facts to back it up. The rest are convincing lies. The interrogator questions everyone, then accuses. Points for catching the truth teller, points for being accused whatever you held.

This repository is the self-hosted game: a single Python process with no database and no build step, packaged for Docker. It runs on a laptop for a living room, or on any small server. A hosted version with lobbies and accounts lives at [whosnotlying.com](https://whosnotlying.com). The game was previously named *One of These People Is Not Lying*; the code and the pages still say so in places.

## Quick start

With Docker:

```bash
git clone https://github.com/nolan-cummins/whosnotlying.git
cd whosnotlying
cp .env.example .env        # set ADMIN_PASS, and PUBLIC_URL if players are not on your network
docker compose up -d
```

Open `http://localhost:5050/qr` on the TV and scan the code with a phone. Host controls are at `/control`, the full console at `/admin`.

Without Docker (Python 3.11 or newer):

```bash
pip install -r requirements.txt
python3 -m src.main            # opens the host controller and the QR screen in your browser
```

`python3 -m src.main --no-browser` runs headless; `python3 deployment/web_server.py` is the same server with the production defaults (binds `0.0.0.0`, honours `$PORT` and `$PUBLIC_URL`).

## The pages

| Path | Who opens it | What it shows |
|---|---|---|
| `/join` | every player, on a phone | name entry, then the secret role card, statements, facts, voting and standings |
| `/qr` | the TV before the game | a big join QR code and link; standings at the end of a round |
| `/display` | the TV during the game | the case files, the accusation and the reveal |
| `/control` | the host, spoiler-free | advance the stages, deal roles, start a new round, end the game |
| `/admin` | the host, full dossier | everything above plus every role, statement and fact, score adjustments, settings, history, reviews and logs (login with `ADMIN_USER` / `ADMIN_PASS`) |
| `/health` | monitoring | `200 OK` |

The stages are Lobby, Setup, Questioning, Accusation and Reveal. There are no timers: the interrogator decides when enough has been said.

## Configuration

Everything is an environment variable (set in `.env` for Docker).

| Variable | Default | Meaning |
|---|---|---|
| `ADMIN_USER`, `ADMIN_PASS` | `admin`, `notthepassword` | host console login; change the password |
| `PUBLIC_URL` | the machine's LAN address | base URL written into the QR code, e.g. `https://game.example.com` behind a reverse proxy |
| `PORT`, `HOST` | `5050`, `0.0.0.0` | where to listen |
| `DATA_DIR` | `./data` (`/app/data` in Docker) | standings, history, accounts |
| `PACKS_DIR` | `./packs` (`/app/data/packs` in Docker) | the question packs in use |
| `OLLAMA_URL` | empty (off) | an [Ollama](https://ollama.com) server for topic matching by expertise and résumé parsing |
| `EMBED_MODEL`, `RESUME_MODEL` | `qwen3-embedding:0.6b`, `qwen3-vl:4b` | the Ollama models for those two features |
| `ARCHIVE_DIR` | `/app/archive` | optional folder of offline source documents served read-only at `/archive/` |

Persistence: the Docker volume `game_data` holds the data directory. Upgrading the image keeps it; packs you edited in the volume are not overwritten (the image only seeds packs that are newer than yours).

Behind a reverse proxy (Caddy, nginx, a Cloudflare Tunnel), forward to port 5050 and set `PUBLIC_URL` to the public address so the QR code points the right way. The server speaks plain HTTP; terminate TLS at the proxy.

## Settings a host can change

In `/admin`: which packs are on, how many interrogators and truth tellers a round has (one of each by default; the rest are liars), fair rotation of roles, whether liars also get background facts to bluff with, whether facts are hidden during questioning, topic matching (off, by the tags players pick, or by the expertise they describe), skipping topics already heard in this game or by a saved account, and the idle timeout that ends an abandoned game.

## Question packs

Packs are JSON files in `packs/`. Each holds topics with a truth, one or more lies, and facts behind each:

```json
{
  "id": "my-pack", "name": "My pack", "version": 2,
  "topics": [
    {
      "id": "t1", "category": "Food", "topic": "Why bread rises", "tags": ["Cooking", "Chemistry"],
      "truth": { "text": "Yeast turns sugars into carbon dioxide, which the gluten traps.", "facts": ["...", "..."] },
      "lies": [{ "text": "Bread rises because flour expands when it absorbs water.", "facts": ["..."] }]
    }
  ]
}
```

Drop a file into the packs directory and the game picks it up on the next request; no restart. Packs can be one-sided (only truths, or only lies). `python3 -m scripts.lint_packs` checks every pack for duplicates, near-duplicate statements and leaks between truths and lies. The three shipped packs are general trivia, an absurd pack, and *PhD Mode*, built from open-access research papers with the citation revealed after the verdict; `sources/CONVERTING.md` explains how the raw sources were turned into packs.

## Optional: topic matching and résumé upload

With an Ollama server reachable at `OLLAMA_URL`, the host can switch topic matching to "expertise": each player's free-text description is embedded and topics are dealt with a bias toward what they know, never locked to it. Players can also upload a PDF résumé, which a local vision model turns into a draft profile. Nothing leaves your network and the PDF is not kept. Without Ollama both features are off and topics are dealt at random; matching by tags still works.

## Development

```bash
pip install -r requirements.txt
python3 -m pytest -q          # 109 tests: rules, fair rotation, packs, matching, server, accounts
python3 -m scripts.lint_packs
```

The rules live in `src/game.py`, packs in `src/packs.py`, the HTTP server and pages in `src/server.py` and `src/templates.py`. There is no front-end build: the pages are plain HTML and JavaScript, polled once a second.

## Contributing

Bug reports and new packs are the most useful contributions. See `CONTRIBUTING.md`.

## Licence

MIT. Question sources are credited inside the packs.

#!/bin/bash
# lint scratch pack built from given files
cd /tmp/claude-1000/-home-nolan-src-liars/2b5b37ba-e844-4d6a-9bb6-127597b1f151/scratchpad/mass; rm -f test.json; python3 build2.py test.json "$@" && cd ~/src/liars/src && python3 scripts/lint_packs.py /tmp/claude-1000/-home-nolan-src-liars/2b5b37ba-e844-4d6a-9bb6-127597b1f151/scratchpad/mass/test.json --check-archive 2>&1 | grep -v "^OK" | tail -12

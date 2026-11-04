#!/bin/bash
# rebuild the single PhD Mode pack from every item file listed in packs.tsv, lint, copy item sources into the repo
cd /tmp/claude-1000/-home-nolan-src-liars/2b5b37ba-e844-4d6a-9bb6-127597b1f151/scratchpad/mass
R=/home/nolan/src/liars/src
mkdir -p $R/sources/phd/items
args=""
while IFS=$'\t' read -r pack files; do
  for f in $files; do args="$args $f.txt"; cp $f.txt $R/sources/phd/items/; done
done < packs.tsv
rm -f $R/packs/phd-mode*.json
cp $R/sources/phd/base.json $R/packs/phd-mode.json  # the hand-built checkpoint batch; build2 appends the rest
python3 build2.py $R/packs/phd-mode.json $args
cd $R && python3 scripts/lint_packs.py packs/*.json --check-archive 2>&1 | tail -4

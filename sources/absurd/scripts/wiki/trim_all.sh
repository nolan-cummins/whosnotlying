#!/bin/bash
# Trim every downloaded dump part into /mnt/hdd2/wikipedia/parts/pNN/{corpus,meta}.jsonl, 6 at a time (bz2 decode is
# single-threaded, ~2 min per part). Skips parts already trimmed; safe to rerun while downloads are still going.
#   bash trim_all.sh [DUMPS] [OUT]
D=${1:-/mnt/hdd2/wikipedia/dumps}; O=${2:-/mnt/hdd2/wikipedia/parts}; H=$(dirname "$(readlink -f "$0")")
mkdir -p "$O"
ls "$D"/enwiki_content-*.json "$D"/enwiki_content-*.json.bz2 2>/dev/null | while read -r f; do
  n=$(basename "$f" | grep -o -- '-[0-9]*\.json' | tr -dc 0-9); n=$((10#$n))
  [ -s "$O/p$n/meta.jsonl" ] || echo "$f $O/p$n"
done | xargs -P 6 -L 1 sh -c 'python3 -I "'"$H"'/trim.py" "$0" "$1" && echo "trimmed $1"'

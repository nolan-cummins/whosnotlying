#!/bin/bash
cd /home/nolan/src/liars/src
while IFS=$'\t' read -r kind n q; do
  echo "=== $q"
  if [ "$kind" = any ]; then extra="--any-venue --min-cites 5"; else extra=""; fi
  timeout 1800 python3 sources/phd/fetch.py --months 24 --pool 120 --take "$n" --search "$q" $extra 2>&1 | grep -v "^\s*$" | tail -n 30
done < "$1"
echo ALLDONE

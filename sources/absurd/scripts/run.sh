#!/bin/sh
# archive each "name<TAB>url" line of $1; prints name, saved file (or FAILED), url
cd /home/nolan/src/liars/src
while IFS="	" read -r name url; do
  [ -z "$name" ] && continue
  out=$(timeout 150 python3 sources/archive/archive_page.py "$url" "$name" 2>/dev/null)
  echo "$name	${out:-FAILED}	$url"
done < "$1"

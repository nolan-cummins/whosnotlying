#!/bin/sh
# Install the pdf.js viewer into the offline-source archive (served at /archive/_pdfjs/), so PDFs open in any
# browser, including Android Chrome, which otherwise just downloads them. Legacy build = older phones too.
set -e
ARCHIVE=${ARCHIVE_DIR:-/mnt/hdd2/liars-archive}
VER=${PDFJS_VERSION:-6.4.299}
tmp=$(mktemp -d)
curl -sSL -o "$tmp/pdfjs.zip" "https://github.com/mozilla/pdf.js/releases/download/v$VER/pdfjs-$VER-legacy-dist.zip"
rm -rf "$ARCHIVE/_pdfjs" && mkdir -p "$ARCHIVE/_pdfjs"
(cd "$ARCHIVE/_pdfjs" && python3 -m zipfile -e "$tmp/pdfjs.zip" . && rm -f web/compressed.tracemonkey-pldi-09.pdf)
rm -rf "$tmp"
echo "pdf.js $VER -> $ARCHIVE/_pdfjs ($(du -sh "$ARCHIVE/_pdfjs" | cut -f1))"

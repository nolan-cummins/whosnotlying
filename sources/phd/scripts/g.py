"""Sentences matching a regex in a paper's text: python3 g.py IDX REGEX [max]"""
import re, sys
from meta import papers, RAW
r = papers[int(sys.argv[1])]; t = re.sub(r"\s+", " ", open(f"{RAW}/texts/{r['slug']}.txt").read())
n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
for s in re.split(r"(?<=[.!?])\s+", t):
    if re.search(sys.argv[2], s, re.I) and len(s) < 600:
        print("-", s); n -= 1
        if n <= 0: break

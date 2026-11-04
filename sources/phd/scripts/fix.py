"""Replace exact strings in a file: python3 fix.py FILE  (pairs on stdin: old\\tnew per line)"""
import sys
p = sys.argv[1]; s = open(p).read()
for line in sys.stdin:
    if "\t" not in line: continue
    a, b = line.rstrip("\n").split("\t")
    assert a and a in s, a; s = s.replace(a, b)
open(p, "w").write(s)

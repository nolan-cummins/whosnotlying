"""Print reading notes for papers: python3 ext.py IDX... (abstract, institutions, conclusion excerpt)."""
import re, sys
from meta import papers, src, RAW
for a in sys.argv[1:]:
    i = int(a); r = papers[i]; s = src(i)
    t = re.sub(r"\s+", " ", open(f"{RAW}/texts/{r['slug']}.txt").read())
    m = [x.start() for x in re.finditer(r"\b(Conclusions?|CONCLUSIONS?|Discussion|DISCUSSION)\b", t)]
    cut = m[-1] if m and m[-1] > len(t) * 0.4 else int(len(t) * 0.75)
    print(f"##### {i} [{s['journal']} {s['year']}] {r['title']}\nINST: {'; '.join(s['institution_candidates'])} ({s['country']}) ARCH: {bool(s['archive'])}\n"
          f"ABS: {r['abstract'][:1500]}\nCONCL: {t[cut:cut + int(__import__("os").environ.get("CONCL", "0"))]}\n")

"""Drop blocks by title: python3 drop.py FILE 'Title' ..."""
import re, sys
fn = sys.argv[1]; bad = set(sys.argv[2:])
blks = re.split(r"\n\s*\n", open(fn).read().strip())
keep = [b for b in blks if b.split("|")[1].strip() not in bad]
open(fn, "w").write("\n\n".join(keep) + "\n"); print(len(blks), "->", len(keep))

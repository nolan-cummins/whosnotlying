"""Plain text of an archived copy: atext.py NAME [regex ...] -> length, or matching snippets."""
import html, os, re, subprocess, sys
A = "/mnt/hdd2/liars-archive"
def text(name):
    for ext in (".html", ".pdf"):
        p = f"{A}/{name}{ext}"
        if os.path.exists(p):
            if ext == ".pdf":
                return " ".join(subprocess.run(["pdftotext", "-q", p, "-"], capture_output=True, text=True).stdout.split())
            s = open(p, encoding="utf-8", errors="replace").read()
            s = re.sub(r"(?is)<(style|script|svg)[^>]*>.*?</\1>", " ", s)
            s = re.sub(r"(?s)<[^>]+>", " ", s)
            s = re.sub(r"data:[^\s\"')]+", "", s)
            return " ".join(html.unescape(s).split())
    return ""
if __name__ == "__main__":
    t = text(sys.argv[1])
    if len(sys.argv) == 2:
        print(sys.argv[1], len(t))
    for pat in sys.argv[2:]:
        b = t.find("Open the original"); b = b + 20 if 0 < b < 3000 else 0  # skip the archive banner
        for m in [m for m in re.finditer(pat, t, re.I) if m.start() > b][:2]:
            print(f"[{pat}] …{t[max(b, m.start() - 130):m.end() + 130]}…")

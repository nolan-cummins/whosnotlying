"""
Save an offline copy of a source page into the archive (served at /archive/<name>), viewable in any browser.

    python3 sources/archive/archive_page.py URL NAME        # -> $ARCHIVE_DIR/NAME.html (or NAME.pdf)

Web pages become one self-contained .html: stylesheets and images inlined as data URIs, scripts stripped,
links made absolute, and a banner naming the original URL and date. A URL that serves a PDF is saved as NAME.pdf.
A page over 15 MB once inlined is printed to NAME.pdf instead (shown through pdf.js, like any PDF).
Uses a real headless Chromium (Playwright), so pages that need JavaScript or bot checks usually work.
Prints the saved file name; exits 1 on failure.
"""
import base64
import datetime as dt
import os
import re
import sys
import urllib.parse

from playwright.sync_api import sync_playwright

ARCHIVE = os.environ.get("ARCHIVE_DIR", "/mnt/hdd2/liars-archive")
MAX_HTML = 15 * 1024 * 1024
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")

# Runs in the page: drop scripts and handlers, absolutize links, report what to inline.
PREP = """() => {
  document.querySelectorAll('script, noscript, iframe, object, embed, link[rel=preload], link[rel=modulepreload]').forEach(e => e.remove());
  // cookie banners, paywall nags and other overlays: fixed elements go, sticky ones stay in the flow
  // (inside body only: some sites put "cookie"/"consent" classes on <html> or <body> itself)
  document.querySelectorAll(['[id*=cookie i]', '[class*=cookie i]', '[id*=consent i]', '[class*=consent i]', '[id^=onetrust]',
    '[class*=modal i][role=dialog]'].map(x => 'body ' + x).join(', ')).forEach(e => e.remove());
  document.querySelectorAll('body *').forEach(e => { const pos = getComputedStyle(e).position; if (pos === 'fixed') e.remove(); else if (pos === 'sticky') e.style.position = 'static'; });
  for (const el of [document.documentElement, document.body]) if (el && el.style) el.style.overflow = 'auto';
  document.querySelectorAll('*').forEach(e => [...e.attributes].forEach(a => { if (/^on/i.test(a.name)) e.removeAttribute(a.name); }));
  document.querySelectorAll('a[href]').forEach(a => { a.setAttribute('href', a.href); a.setAttribute('target', '_blank'); });
  const imgs = [...document.querySelectorAll('img')].map((im, i) => { im.dataset.arc = i; im.loading = 'eager'; return im.currentSrc || im.src; });
  const css = [...document.querySelectorAll('link[rel~=stylesheet]')].map((l, i) => { l.dataset.arc = i; return l.href; });
  return {imgs, css};
}"""


def data_uri(body: bytes, ctype: str) -> str:
    return f"data:{ctype.split(';')[0] or 'application/octet-stream'};base64,{base64.b64encode(body).decode()}"


def main(url: str, name: str) -> str:
    os.makedirs(ARCHIVE, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent=UA, viewport={"width": 1200, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        fetch = lambda u: ctx.request.get(u, timeout=30000, headers={"Referer": url})
        try:
            r = fetch(url)
        except Exception:  # some sites refuse a bare request but serve a real browser fine
            r = None
        if r and r.ok and "pdf" in (r.headers.get("content-type") or "") and r.body().startswith(b"%PDF"):
            out = name + ".pdf"
            open(os.path.join(ARCHIVE, out), "wb").write(r.body())
            b.close()
            return out
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        page.wait_for_selector("body", timeout=20000)
        page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 800) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } window.scrollTo(0, 0); }")
        page.wait_for_timeout(1500)
        title = page.title()
        found = page.evaluate(PREP)
        imgs, css = {}, {}
        for i, u in enumerate(found["imgs"]):
            if u and not u.startswith("data:"):
                try:
                    r = fetch(u)
                    if r.ok:
                        imgs[str(i)] = data_uri(r.body(), r.headers.get("content-type", "image/png"))
                except Exception:
                    pass
        for i, u in enumerate(found["css"]):
            try:
                r = fetch(u)
                if r.ok:  # relative url(...) inside the CSS must point at the original site
                    css[str(i)] = re.sub(r"url\((['\"]?)(?!data:|https?:|//)([^'\")]+)\1\)",
                                         lambda m: f"url({m.group(1)}{urllib.parse.urljoin(u, m.group(2))}{m.group(1)})", r.text())
            except Exception:
                pass
        banner = (f"Offline copy saved {dt.date.today().isoformat()} from {url}. Images and styles are embedded; "
                  "interactive parts of the original are removed.")
        page.evaluate("""([imgs, css, banner, url]) => {
          document.querySelectorAll('img[data-arc]').forEach(im => { const d = imgs[im.dataset.arc]; if (d) { im.src = d; im.removeAttribute('srcset'); } im.removeAttribute('data-arc'); });
          document.querySelectorAll('source[srcset]').forEach(s => s.remove());
          document.querySelectorAll('link[data-arc]').forEach(l => { const t = css[l.dataset.arc]; if (t != null) { const s = document.createElement('style'); s.textContent = t; l.replaceWith(s); } });
          const bar = document.createElement('div');
          bar.setAttribute('style', 'all:initial;display:block;position:relative;z-index:2147483647;background:#ffe9a8;color:#222;font:14px/1.4 system-ui,sans-serif;padding:8px 12px;border-bottom:1px solid #c9a63c');
          bar.textContent = banner + ' ';
          const a = document.createElement('a'); a.href = url; a.textContent = 'Open the original'; a.target = '_blank'; a.setAttribute('style', 'color:#0645ad');
          bar.appendChild(a);
          document.body.prepend(bar);
          if (!document.querySelector('meta[name=viewport]')) { const m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width, initial-scale=1'; document.head.appendChild(m); }
        }""", [imgs, css, banner, url])
        html = "<!DOCTYPE html>\n" + page.content()
        if len(html.encode()) <= MAX_HTML:
            out = name + ".html"
            open(os.path.join(ARCHIVE, out), "w", encoding="utf-8").write(html)
        else:
            out = name + ".pdf"
            page.pdf(path=os.path.join(ARCHIVE, out), print_background=True)
        b.close()
        print(f"{out}  ({title[:70]})", file=sys.stderr)
        return out


if __name__ == "__main__":
    if len(sys.argv) != 3 or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", sys.argv[2]):
        sys.exit(__doc__)
    try:
        print(main(sys.argv[1], sys.argv[2]))
    except Exception as e:
        print(f"failed: {e}", file=sys.stderr)
        sys.exit(1)

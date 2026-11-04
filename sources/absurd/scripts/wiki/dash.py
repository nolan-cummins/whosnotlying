"""
LAN dashboard for the Wikipedia pipeline: renders every STATUS_DIR/*.json written by progress.Job.
Page at http://<host>:8097/, data at /jobs.json.

    setsid nohup python3 -I dash.py >/dev/null 2>&1 &
"""
import glob
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATUS_DIR = os.environ.get("STATUS_DIR", "/mnt/hdd2/wikipedia/status")
PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Wikipedia pipeline</title>
<style>
:root{color-scheme:dark;--bg:#111418;--card:#1a1f26;--line:#2a313b;--fg:#e6e9ee;--dim:#8b95a3;--ok:#4cc38a;--run:#4a90e2;--bad:#e5655b;--wait:#e5b454}
body{margin:0;font:15px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:900px;margin:0 auto;padding:20px 16px 40px}h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--dim);font-size:13px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.head{display:flex;justify-content:space-between;gap:10px;align-items:baseline}.t{font-weight:600}
.chip{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid currentColor}
.running{color:var(--run)}.done{color:var(--ok)}.failed{color:var(--bad)}.waiting{color:var(--wait)}
.bar{height:10px;background:var(--line);border-radius:6px;overflow:hidden;margin:10px 0 4px}
.bar>div{height:100%;background:var(--run)}.done .bar>div,.card.done .bar>div{background:var(--ok)}
.meta{color:var(--dim);font-size:13px}.note{color:var(--dim);font-size:13px;margin-top:4px}
table{border-collapse:collapse;margin-top:8px;font-size:14px}td{padding:2px 14px 2px 0}td:first-child{color:var(--dim)}
.charts{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px}.ch{flex:1 1 260px}.ch .lbl{font-size:12px;color:var(--dim)}
svg{width:100%;height:110px;background:#151a20;border-radius:6px}
pre{margin:8px 0 0;font-size:12px;color:var(--dim);white-space:pre-wrap;max-height:160px;overflow:auto}
details summary{cursor:pointer;color:var(--dim);font-size:13px;margin-top:6px}
</style><main><h1>Wikipedia pipeline</h1><div class="sub" id="sub">loading…</div><div id="jobs"></div></main>
<script>
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=x=>typeof x==='number'?(Math.abs(x)>=1000?Math.round(x).toLocaleString():(+x.toFixed(4)).toString()):esc(x);
const dur=s=>s<90?Math.round(s)+' s':s<5400?Math.round(s/60)+' min':(s/3600).toFixed(1)+' h';
function chart(name,pts){
  if(!pts.length)return'';const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),W=300,H=100,P=6;
  const X=x=>P+(W-2*P)*(x1>x0?(x-x0)/(x1-x0):.5),Y=y=>H-P-(H-2*P)*(y1>y0?(y-y0)/(y1-y0):.5);
  const d=pts.map((p,i)=>(i?'L':'M')+X(p[0]).toFixed(1)+' '+Y(p[1]).toFixed(1)).join(' ');
  return `<div class="ch"><div class="lbl">${esc(name)} — last ${fmt(ys[ys.length-1])} (min ${fmt(y0)}, max ${fmt(y1)})</div>
  <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path d="${d}" fill="none" stroke="#4a90e2" stroke-width="2" vector-effect="non-scaling-stroke"/></svg></div>`}
function card(j,now){
  const el=now-j.started,frac=j.total?Math.min(1,j.done/j.total):null,rate=j.done/Math.max(1,(j.state==='running'?now:j.updated)-j.started);
  let meta=`${fmt(j.done)}${j.total?' / '+fmt(j.total):''} ${esc(j.unit)}`;
  if(j.state==='running'){meta+=` · ${rate>=1?rate.toFixed(1)+'/s':(rate*60).toFixed(1)+'/min'} · running ${dur(el)}`;
    if(frac&&rate>0)meta+=` · ETA ${dur((j.total-j.done)/rate)}`;
    if(now-j.updated>120)meta+=` · <span class="failed">no update for ${dur(now-j.updated)}</span>`}
  else meta+=` · took ${dur(j.updated-j.started)} · ${new Date(j.updated*1000).toLocaleString()}`;
  const m=Object.entries(j.metrics);
  return `<div class="card ${j.state}"><div class="head"><span class="t">${esc(j.title)}</span><span class="chip ${j.state}">${j.state}</span></div>
  ${j.note?`<div class="note">${esc(j.note)}</div>`:''}
  ${frac!==null?`<div class="bar"><div style="width:${(100*frac).toFixed(1)}%"></div></div>`:''}<div class="meta">${meta}${frac!==null?` · ${(100*frac).toFixed(1)}%`:''}</div>
  ${m.length?`<table>${m.map(([k,v])=>`<tr><td>${esc(k)}</td><td>${fmt(v)}</td></tr>`).join('')}</table>`:''}
  <div class="charts">${Object.entries(j.series).map(([k,v])=>chart(k,v)).join('')}</div>
  ${j.log.length?(j.state==='running'?`<pre>${j.log.map(esc).join('\n')}</pre>`:`<details><summary>log</summary><pre>${j.log.map(esc).join('\n')}</pre></details>`):''}</div>`}
async function tick(){try{const d=await(await fetch('jobs.json',{cache:'no-store'})).json(),now=d.now;
  const order={running:0,waiting:1,failed:2,done:3};d.jobs.sort((a,b)=>order[a.state]-order[b.state]||b.updated-a.updated);
  document.getElementById('sub').textContent=`${d.jobs.filter(j=>j.state==='running').length} running · updated ${new Date(now*1000).toLocaleTimeString()} · refreshes every 3 s`;
  document.getElementById('jobs').innerHTML=d.jobs.map(j=>card(j,now)).join('')}
  catch(e){document.getElementById('sub').textContent='dashboard unreachable: '+e}}
tick();setInterval(tick,3000);
</script>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/jobs.json"):
            import time
            jobs = []
            for p in glob.glob(os.path.join(STATUS_DIR, "*.json")):
                try:
                    jobs.append(json.load(open(p)))
                except (OSError, ValueError):
                    pass  # mid-write or malformed; skip this round
            body, ctype = json.dumps({"now": time.time(), "jobs": jobs}).encode(), "application/json"
        else:
            body, ctype = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    os.makedirs(STATUS_DIR, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8097))), H).serve_forever()

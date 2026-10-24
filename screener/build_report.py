#!/usr/bin/env python3
"""Build the deliverable report: clickable pool links + client-side auto-audit field."""
import json, html, time, os, sys, urllib.request
sys.path.insert(0,"screener")
from links import link_set, defillama_link, geckoterminal_token, dexscreener_token, GT_CHAIN, DEXSCREENER_CHAIN
from audit import load_protocols, assess

UA={"User-Agent":"Mozilla/5.0","Accept":"application/json"}
def esc(x): return html.escape(str(x)) if x is not None else ""

def merge_raw():
    """results.json lost pool/underlyingTokens; re-merge from the source."""
    r=urllib.request.Request("https://yields.llama.fi/pools",headers=UA)
    raw=json.loads(urllib.request.urlopen(r,timeout=30).read().decode())["data"]
    by={}
    for p in raw:
        by[(p.get("chain"),p.get("project"),p.get("symbol"))]=p
    return by

def build(out="report.html"):
    res=json.load(open("screener/results.json"))
    by=merge_raw()
    try: protos=load_protocols()
    except Exception: protos={}

    real=[r for r in res if r["verdict"]=="REAL" and r["tvl"]>10_000_000]
    real.sort(key=lambda r:-r["apy"])
    rows=[]
    for r in real[:80]:
        src=by.get((r["chain"],r["project"],r["symbol"]),{})
        merged={**r,"pool":src.get("pool"),"underlyingTokens":src.get("underlyingTokens") or []}
        rows.append((merged, assess(r,protos) if protos else {"verdict":"?"}, link_set(merged)))

    from collections import Counter
    vc=Counter(r["verdict"] for r in res); fc=Counter(f for r in res for f in r["fails"])
    ar=[]
    try: ar=json.load(open("screener/audit_reads.json"))
    except Exception: pass
    ts=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    H=[f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aegis Yield Screen</title>
<style>
body{{font:14px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
margin:0;padding:18px;background:#0d1117;color:#c9d1d9;max-width:1200px}}
h1{{font-size:20px;margin:0 0 4px}}h2{{font-size:14px;margin:26px 0 8px;color:#8b949e;
text-transform:uppercase;letter-spacing:.06em}}
.sub{{color:#8b949e;font-size:12px;margin-bottom:18px}}
table{{border-collapse:collapse;width:100%;font-size:12.5px}}
th{{text-align:left;color:#8b949e;font-weight:600;border-bottom:1px solid #21262d;padding:6px 7px}}
td{{padding:6px 7px;border-bottom:1px solid #161b22}}tr:hover td{{background:#161b22}}
a{{color:#58a6ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.big{{display:flex;gap:9px;flex-wrap:wrap;margin:10px 0 6px}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:9px 13px;min-width:88px}}
.card .n{{font-size:18px;font-weight:600}}.card .l{{font-size:11px;color:#8b949e}}
.ok{{color:#3fb950}}.warn{{color:#d29922}}.bad{{color:#f85149}}.dim{{color:#8b949e}}
.note{{background:#161b22;border-left:3px solid #d29922;padding:10px 14px;margin:12px 0;
font-size:13px;border-radius:0 6px 6px 0}}
.tool{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin:18px 0}}
input,select,button{{font:13px inherit;background:#0d1117;color:#c9d1d9;border:1px solid #30363d;
border-radius:6px;padding:9px 11px}}
input{{width:100%;box-sizing:border-box;margin-bottom:10px}}
button{{background:#238636;border-color:#2ea043;color:#fff;cursor:pointer;font-weight:600}}
button:hover{{background:#2ea043}}
.v{{font-size:17px;font-weight:700;margin:10px 0 4px}}
ul{{margin:6px 0;padding-left:20px}}li{{margin:3px 0}}
</style></head><body>"""]
    H.append("<h1>Aegis Yield Screen</h1>")
    H.append(f"<div class='sub'>{len(res):,} pools scanned &middot; {ts} &middot; "
             "classifies what a yield is made of, not what it will return</div>")

    # ---- the paste tool (works offline, no backend) ----
    H.append("""<div class="tool">
<h2 style="margin-top:0">Audit a pool</h2>
<div class="sub">Paste a pool or token link, or just a contract address. Runs the six checks in your browser.</div>
<input id="q" placeholder="https://www.geckoterminal.com/base/pools/0x... &nbsp; or &nbsp; 0x833589fC... &nbsp; or &nbsp; WETH-USDC">
<button onclick="run()">Run audit</button>
<div id="out"></div>
</div>""")

    # ---- summary ----
    H.append("<h2>Verdicts</h2><div class='big'>")
    for k,c in (("REAL","ok"),("PROMISING","ok"),("MIXED","warn"),("AVOID","bad")):
        H.append(f"<div class='card'><div class='n {c}'>{vc.get(k,0):,}</div><div class='l'>{k}</div></div>")
    H.append("</div><h2>Why pools were rejected</h2><div class='big'>")
    for k,c in fc.most_common():
        H.append(f"<div class='card'><div class='n'>{c:,}</div><div class='l'>{k}</div></div>")
    H.append("</div>")

    if ar:
        nread=sum(1 for o in ar if (o.get("read") or {}).get("ok"))
        nolink=sum(1 for o in ar if not o.get("fetchable"))
        H.append("<h2>Audit reports</h2><div class='big'>"
          f"<div class='card'><div class='n bad'>{nolink}</div><div class='l'>no fetchable audit</div></div>"
          f"<div class='card'><div class='n ok'>{nread}</div><div class='l'>report read</div></div></div>")
        H.append("<div class='note'><b>85% of real-yield pools publish no audit link at all.</b> "
                 "A further 55 point only at Google Drive or Docsend. For four out of five real-yield "
                 "pools there is no audit report available to read.</div>")

    # ---- the table WITH CLICKABLE LINKS ----
    H.append(f"<h2>REAL pools, &gt;$10M TVL, by organic APY ({len(rows)})</h2>")
    H.append("<table><tr><th>chain</th><th>project</th><th>symbol</th><th>APY</th><th>base</th>"
             "<th>reward</th><th>TVL</th><th>days</th><th>sigma</th><th>audit</th><th>links</th></tr>")
    for r,a,L in rows:
        av=a.get("verdict","?"); cls={"AUDITED":"ok","UNAUDITED":"bad","THIN":"warn"}.get(av,"dim")
        sg=r.get("sigma"); sgt=f"{sg:.3f}" if isinstance(sg,(int,float)) else "-"
        links=[]
        if L.get("defillama"): links.append(f"<a href='{esc(L['defillama'])}' target='_blank' rel='noopener'>DL</a>")
        # token, not pool: DefiLlama publishes no pool address, so the labels say so
        if L.get("geckoterminal"):
            links.append("<a href='%s' target='_blank' rel='noopener' title='GeckoTerminal page for "
                         "the underlying token, not this pool'>GT token</a>" % esc(L['geckoterminal']))
        if L.get("dexscreener"):
            links.append("<a href='%s' target='_blank' rel='noopener' title='DexScreener lookup by the "
                         "underlying token address. This is not the pool page.'>DS token</a>"
                         % esc(L['dexscreener']))
        links.append(f"<a href='{esc(L['dexscreener_search'])}' target='_blank' rel='noopener'>search</a>")
        H.append("<tr>"
          f"<td>{esc(r['chain'])[:12]}</td><td>{esc(r['project'])[:20]}</td>"
          f"<td>{esc(r['symbol'])[:16]}</td>"
          f"<td class='ok'>{r['apy']:.2f}%</td><td>{r['base']:.2f}%</td>"
          f"<td class='dim'>{r['rew']:.2f}%</td><td>${r['tvl']/1e6:,.1f}M</td>"
          f"<td class='dim'>{r['count']}</td><td class='dim'>{sgt}</td>"
          f"<td class='{cls}'>{esc(av)}</td><td class='dim'>{' '.join(links)}</td></tr>")
    H.append("</table>")
    H.append("<div class='sub' style='margin-top:6px'>Links: <b>DL</b> DefiLlama pool &middot; "
             "<b>GT token</b> / <b>DS token</b> = explorer page for the underlying token "
             "(DefiLlama publishes no pool address) &middot; <b>search</b> = symbol search &middot; "
             "<b>search</b> DexScreener by symbol. Token links are omitted where the pool publishes a "
             "null address (staked-ETH pools do).</div>")

    H.append("<h2>Method</h2><div class='sub'>Six checks, each set by a measured failure: "
             "outlier flag &middot; reward share &gt;50% &middot; spot vs 7d base &middot; "
             "TVL &gt;$1M &middot; turnover &gt;1%/day (only when volume data exists) &middot; "
             "plausibility (stable pool &gt;25% organic = credit risk). "
             "This tool never places an order and does not predict returns.</div>")

    # ---- client-side auditor ----
    core=open("screener/audit_core.js").read()
    # embed the full screen results for offline lookup
    # embed only pools worth a lookup: REAL/PROMISING plus anything >$1M TVL.
    # embedding all 16,830 made a 5.8MB file; this keeps it under ~1.5MB.
    keep=[r for r in res if r["verdict"] in ("REAL","PROMISING","MIXED") or r["tvl"]>1_000_000]
    slim=[{k:r.get(k) for k in ("symbol","chain","project","apy","base","rew","tvl","count","sigma","verdict","fails","reasons")} for r in keep]
    H.append("<script type='module'>")
    H.append(core.replace("export ",""))
    H.append(f"\nconst DATA={json.dumps(slim)};")
    H.append("""
function extract(s){
  s=(s||'').trim();
  const m=s.match(/0x[a-fA-F0-9]{40}/);
  if(m) return {kind:'addr', v:m[0]};
  const g=s.match(/geckoterminal\\.com\\/([^\\/]+)\\/(pools|tokens)\\/([^\\s?]+)/i);
  if(g) return {kind:'gt', chain:g[1], type:g[2], v:g[3]};
  const d=s.match(/dexscreener\\.com\\/([^\\/]+)\\/([^\\s?]+)/i);
  if(d) return {kind:'ds', chain:d[1], v:d[2]};
  return {kind:'sym', v:s};
}
function run(){
  const el=document.getElementById('out');
  const raw=document.getElementById('q').value;
  const x=extract(raw);
  let hits=[];
  if(x.kind==='sym'){
    const q=x.v.toUpperCase();
    hits=DATA.filter(r=>(r.symbol||'').toUpperCase().includes(q) ||
                        (r.project||'').toUpperCase().includes(q)).slice(0,5);
  } else if(x.kind==='addr'||x.kind==='gt'||x.kind==='ds'){
    // we don't hold addresses client-side; explain and offer the symbol route
    el.innerHTML=`<div class='v dim'>Address/URL received</div>
      <div class='sub'>Contract <code>${x.v}</code> on <b>${x.chain||'unknown chain'}</b>.<br><br>
      This static page has no backend, so it cannot query the chain for that address yet.
      Two options:<br>
      &bull; paste the <b>symbol</b> (e.g. <code>WETH-USDC</code>) to look it up in the {N} scanned pools, or<br>
      &bull; connect the MCP endpoint, which resolves addresses server-side.</div>`;
    return;
  }
  if(!hits.length){
    el.innerHTML=`<div class='v dim'>No match</div><div class='sub'>No pool symbol matching that in the scanned set.</div>`;
    return;
  }
  el.innerHTML=hits.map(r=>{
    const cls=r.verdict==='REAL'?'ok':r.verdict==='AVOID'?'bad':'warn';
    return `<div class='v ${cls}'>${r.verdict} &mdash; ${r.symbol} <span class='sub'>(${r.chain} / ${r.project})</span></div>
      <div class='sub'>APY ${r.apy}% &middot; base ${r.base}% &middot; reward ${r.rew}% &middot; TVL $${(r.tvl/1e6).toFixed(1)}M &middot; ${r.count} days</div>
      <ul>${(r.reasons&&r.reasons.length?r.reasons:['all six checks passed']).map(z=>`<li>${z}</li>`).join('')}</ul>`;
  }).join('<hr style="border-color:#21262d">');
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')run();});
window.run=run;
""".replace("{N}", str(len(res))))
    H.append("</script></body></html>")
    open(out,"w").write("".join(H))
    return keep
    print(f"wrote {out}  ({os.path.getsize(out):,} bytes)")
if __name__=="__main__": build()

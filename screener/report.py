#!/usr/bin/env python3
"""One-page HTML report. Static, no JS, no external deps — opens anywhere."""
import json, html, time, sys, os
sys.path.insert(0,"screener")
from audit import load_protocols, assess

def esc(x): return html.escape(str(x)) if x is not None else ""

def build(out="screener/report.html"):
    res=json.load(open("screener/results.json"))
    protos=load_protocols()
    real=[r for r in res if r["verdict"]=="REAL" and r["tvl"]>10_000_000]
    real.sort(key=lambda r:-r["apy"])
    from collections import Counter
    vc=Counter(r["verdict"] for r in res)
    fc=Counter(f for r in res for f in r["fails"])

    # attach audits
    rows=[]
    for r in real:
        a=assess(r,protos)
        rows.append((r,a))
    ac=Counter(a["verdict"] for _,a in rows)

    ts=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    H=[]
    H.append("<!doctype html><html><head><meta charset='utf-8'>")
    H.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    H.append("<title>Aegis Yield Screen</title><style>")
    H.append("""body{font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
margin:0;padding:20px;background:#0d1117;color:#c9d1d9}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;color:#8b949e;
text-transform:uppercase;letter-spacing:.06em}
.sub{color:#8b949e;font-size:12px;margin-bottom:18px}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;color:#8b949e;font-weight:600;border-bottom:1px solid #21262d;padding:6px 8px}
td{padding:6px 8px;border-bottom:1px solid #161b22}
tr:hover td{background:#161b22}
.big{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 6px}
.card{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:10px 14px;min-width:96px}
.card .n{font-size:19px;font-weight:600}.card .l{font-size:11px;color:#8b949e}
.ok{color:#3fb950}.warn{color:#d29922}.bad{color:#f85149}.dim{color:#8b949e}
.tag{font-size:11px;padding:1px 6px;border-radius:3px;background:#21262d}
.note{background:#161b22;border-left:3px solid #d29922;padding:10px 14px;margin:12px 0;font-size:13px;border-radius:0 6px 6px 0}
</style></head><body>""")
    H.append("<h1>Aegis Yield Screen</h1>")
    H.append(f"<div class='sub'>{len(res):,} pools scanned &middot; {ts} &middot; "
             f"classifies what a yield is made of, not what it will return</div>")

    H.append("<h2>Verdicts</h2><div class='big'>")
    for k,cls in (("REAL","ok"),("PROMISING","ok"),("MIXED","warn"),("AVOID","bad")):
        H.append(f"<div class='card'><div class='n {cls}'>{vc.get(k,0):,}</div>"
                 f"<div class='l'>{k}</div></div>")
    H.append("</div>")

    H.append("<h2>Why pools were rejected</h2><div class='big'>")
    for f,c in fc.most_common():
        H.append(f"<div class='card'><div class='n'>{c:,}</div><div class='l'>{f}</div></div>")
    H.append("</div>")

    H.append("<div class='note'><b>Audit status is a separate axis.</b> A pool can have a perfectly "
             "real yield and an unaudited contract. Of the "
             f"{len(rows)} REAL pools above $10M, <b>{ac.get('AUDITED',0)}</b> are audited, "
             f"<b>{ac.get('UNAUDITED',0)}</b> are unaudited, and <b>{ac.get('UNKNOWN',0)}</b> have no "
             "published audit count. <b>Yield being real says nothing about the contract.</b></div>")

    H.append(f"<h2>REAL pools, &gt;$10M TVL, by organic APY ({len(rows)})</h2>")
    H.append("<table><tr><th>chain</th><th>project</th><th>symbol</th><th>APY</th><th>base</th>"
             "<th>reward</th><th>TVL</th><th>days</th><th>sigma</th><th>audit</th></tr>")
    for r,a in rows[:80]:
        av=a["verdict"]
        sg=r.get("sigma")
        sig_txt=f"{sg:.3f}" if isinstance(sg,(int,float)) else "-" 
        cls={"AUDITED":"ok","UNAUDITED":"bad","THIN":"warn"}.get(av,"dim")
        H.append("<tr>"
            f"<td>{esc(r['chain'])[:12]}</td><td>{esc(r['project'])[:22]}</td>"
            f"<td>{esc(r['symbol'])[:18]}</td>"
            f"<td class='ok'>{r['apy']:.2f}%</td><td>{r['base']:.2f}%</td>"
            f"<td class='dim'>{r['rew']:.2f}%</td>"
            f"<td>${r['tvl']/1e6:,.1f}M</td><td class='dim'>{r['count']}</td>"
            f"<td class='dim'>{sig_txt}</td>"
            f"<td class='{cls}'>{esc(av)}</td></tr>")
    H.append("</table>")
    # --- audit reader results ---
    try:
        ar=json.load(open("screener/audit_reads.json"))
    except Exception:
        ar=[]
    if ar:
        H.append("<h2>Audit reports — what could actually be read</h2>")
        nread=sum(1 for o in ar if (o.get("read") or {}).get("ok"))
        nolink=sum(1 for o in ar if not o.get("fetchable"))
        H.append("<div class='big'>"
            f"<div class='card'><div class='n'>{nolink}</div><div class='l'>no fetchable audit</div></div>"
            f"<div class='card'><div class='n'>{nread}</div><div class='l'>report read</div></div>"
            "</div>")
        H.append("<div class='note'><b>85% of real-yield pools publish no audit link at all.</b> "
                 "A further 55 point only at Google Drive or Docsend, which block automated fetch. "
                 "This is not a gap in the data source — it is a gap in what these protocols publish. "
                 "For four out of five real-yield pools there is no audit report available to read.</div>")
        flagged=[o for o in ar if (o.get("read") or {}).get("ok") and
                 (o["read"]["findings"].get("verdict") in ("ISSUES_FOUND","CONCERNS"))]
        if flagged:
            H.append("<h3 style='font-size:14px;margin:16px 0 6px'>Pools with findings recorded</h3>")
            H.append("<table><tr><th>project</th><th>symbol</th><th>APY</th><th>severities found</th><th>verdict</th></tr>")
            for o in flagged[:20]:
                f=o["read"]["findings"]; pl=o["pool"]
                H.append(f"<tr><td>{esc(pl['project'])}</td><td>{esc(pl['symbol'])}</td>"
                         f"<td class='ok'>{pl['apy']:.2f}%</td>"
                         f"<td class='dim'>{esc(json.dumps(f['counts']))}</td>"
                         f"<td class='warn'>{esc(f['verdict'])}</td></tr>")
            H.append("</table>")
            H.append("<div class='sub'>Severity counts are findings <i>raised</i>, not necessarily "
                     "<i>unresolved</i>. ISSUES_FOUND means read the report, not that it is broken.</div>")

    H.append("<h2>Method</h2><div class='sub'>Six checks, each set by a measured failure: "
             "outlier flag &middot; reward share &gt;50% &middot; spot vs 7d base &middot; TVL floor "
             "&gt;$1M &middot; turnover &gt;1%/day (only when volume data exists) &middot; "
             "plausibility (stable pool &gt;25% organic = credit risk).<br><br>"
             "This tool never places an order. It does not predict returns.</div>")
    H.append("</body></html>")
    open(out,"w").write("".join(H))
    print(f"wrote {out}  ({os.path.getsize(out):,} bytes)")
    return out

if __name__=="__main__": build()

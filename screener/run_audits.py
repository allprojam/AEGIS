#!/usr/bin/env python3
"""Run the audit reader across all REAL pools and cache results."""
import json, sys, time
sys.path.insert(0,"screener")
from audit import load_protocols, assess
from auditread import read_protocol, FETCHABLE

res=json.load(open("screener/results.json"))
protos=load_protocols()
real=[r for r in res if r["verdict"]=="REAL" and r["tvl"]>10_000_000]
real.sort(key=lambda r:-r["tvl"])
print(f"REAL pools >$10M: {len(real)}", flush=True)

# map pool -> registry entry with audit links
raw=json.loads(__import__("urllib.request",fromlist=["x"]).urlopen(
    __import__("urllib.request",fromlist=["x"]).Request("https://api.llama.fi/protocols",
    headers={"User-Agent":"Mozilla/5.0"}),timeout=30).read().decode())
by_name={(p.get("name") or "").lower():p for p in raw}

out=[]; done=0; fetched=0
for r in real:
    key=(r.get("project") or "").lower()
    p=by_name.get(key)
    if not p:
        for k,v in by_name.items():
            if k and (key.startswith(k) or k.startswith(key)) and len(k)>3:
                p=v; break
    links=(p or {}).get("audit_links") or []
    fetchable=[l for l in links if any(f in l for f in FETCHABLE)]
    rec=dict(pool=r, audit_links=links, fetchable=fetchable)
    if fetchable:
        a=read_protocol((p or {}).get("name") or r.get("project"), fetchable, max_links=1)
        rec["read"]=a
        if a.get("ok"): fetched+=1
    out.append(rec); done+=1
    if done%25==0: print(f"  {done}/{len(real)}  fetched {fetched}", flush=True)
    time.sleep(0.3)

json.dump(out, open("screener/audit_reads.json","w"))
print(f"\nDONE: {len(out)} pools, {fetched} with a report actually read", flush=True)
from collections import Counter
c=Counter((o.get("read") or {}).get("findings",{}).get("verdict") if o.get("read",{}).get("ok") else "NO_REPORT" for o in out)
for k,v in c.most_common(): print(f"  {str(k):<16} {v:>5}")

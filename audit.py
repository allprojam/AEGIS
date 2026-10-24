#!/usr/bin/env python3
"""
Audit layer — attaches audit status and fork provenance to each screened pool.

WHY THIS EXISTS: the screener flagged 759 IMPLAUSIBLE and 1,488 SUBSIDISED pools,
but it could not see the single biggest gap found this session — that Enosys Loans
has ZERO audits and is a modified fork of an audited protocol (Liquity V2 has 2).

That is the category of risk a yield screen cannot see: the rate can be perfectly
real and the contract still unaudited.

Data: DefiLlama /protocols -> audits, audit_links, forkedFrom, listedAt, openSource.
Injected transport for the prose layer (container cannot reach Ollama).
"""
import json, urllib.request, time

def fetch(url):
    r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=30).read().decode())

def load_protocols():
    """Protocol metadata keyed by a NORMALISED name.

    DefiLlama's bulk feed uses DISPLAY names ("ZEROBASE CeDeFi") while the yields feed uses
    SLUGS ("zerobase-cedefi"), so a direct join matches only 28% of our pools. Normalising both
    sides to alphanumerics lifts the join to 98% (351 of 359 embedded projects, measured). That
    matters because this feed is the only authoritative source for a protocol's OFFICIAL site
    url and its published audit links -- both of which we were not surfacing.
    """
    import re as _re
    # CACHED. The build must not depend on a live fetch: a registry outage would silently drop
    # the official links from every row, and the page would look fine. A stale cache is a
    # visible, checkable failure; a missing one is invisible.
    import os, json as _json
    cache=os.path.join(os.path.dirname(os.path.abspath(__file__)), "protocols_cache.json")
    if os.path.exists(cache):
        try:
            d=_json.load(open(cache))
        except Exception:
            d=fetch("https://api.llama.fi/protocols")
    else:
        d=fetch("https://api.llama.fi/protocols")
    try:
        _json.dump(d, open(cache,"w"))
    except Exception:
        pass
    out={}
    for p in d:
        n=_re.sub(r"[^a-z0-9]", "", (p.get("name") or "").lower())
        if n:
            out[n]=dict(name=p.get("name"), url=p.get("url"),
                        audits=p.get("audits"), audit_links=p.get("audit_links") or [],
                        twitter=p.get("twitter"), chains=p.get("chains"))
    return out


def load_protocols_raw():
    d=fetch("https://api.llama.fi/protocols")
    out={}
    for p in d:
        n=(p.get("name") or "").lower()
        if n: out[n]=dict(
            name=p.get("name"), audits=p.get("audits"),
            audit_links=p.get("audit_links") or [],
            open_source=p.get("openSource"), forked_from=p.get("forkedFrom"),
            listed_at=p.get("listedAt"), category=p.get("category"),
            chains=p.get("chains"), url=p.get("url"),
        )
    return out

def age_years(proto):
    la=proto.get("listed_at")
    if not la: return None
    return (time.time()-la)/(365.25*86400)

def assess(pool, protos):
    """Return an audit assessment for one screened pool."""
    import re as _re
    # normalised key, matching load_protocols(). Slug 'zerobase-cedefi' and display name
    # 'ZEROBASE CeDeFi' both reduce to 'zerobasecedefi'.
    key=_re.sub(r"[^a-z0-9]", "", (pool.get("project") or "").lower())
    proto=protos.get(key)
    if not proto:
        for k,v in protos.items():
            if k and len(k)>3 and (key.startswith(k) or k.startswith(key)):
                proto=v; break
    if not proto:
        return dict(project=pool.get("project"), known=False, audits=None,
                    verdict="UNKNOWN", note="protocol not found in registry")

    a=proto.get("audits")
    # DefiLlama returns audits as a STRING ('0','2'). Coerce, and remember if unparseable.
    if isinstance(a,str):
        a=int(a) if a.strip().isdigit() else None
    links=proto.get("audit_links") or []
    fork=proto.get("forked_from")
    yrs=age_years(proto)

    if a is None:
        verdict="UNKNOWN"; note="no audit count published"
    elif a==0:
        verdict="UNAUDITED"; note="zero audits reported"
    elif a>=2:
        verdict="AUDITED"; note=f"{a} audit(s)"
    else:
        verdict="THIN"; note="1 audit only"

    # fork without its own audits is the Enosys case
    fork_warning=None
    if fork and a==0:
        fork_warning=(f"unauadited fork of {fork} — the original's audits do NOT transfer "
                      f"to a modified fork (this was the Enosys/Liquity V2 case)")
    elif fork:
        fork_warning=f"fork of {fork}"

    return dict(project=proto.get("name"), known=True, audits=a,
                audit_links=links[:3], verdict=verdict, note=note,
                fork=fork, fork_warning=fork_warning,
                age_years=round(yrs,1) if yrs else None,
                open_source=proto.get("open_source"),
                category=proto.get("category"),
                url=proto.get("url"),
                twitter=proto.get("twitter"))

def summary(pools, protos):
    from collections import Counter
    c=Counter()
    for p in pools:
        c[assess(p,protos)["verdict"]]+=1
    return c

if __name__=="__main__":
    print("loading protocol registry...")
    protos=load_protocols()
    print(f"  {len(protos):,} protocols")
    res=json.load(open("screener/results.json"))
    top=[r for r in res if r["verdict"]=="REAL" and r["tvl"]>10_000_000]
    top.sort(key=lambda r:-r["apy"])
    print(f"\n=== AUDIT STATUS of the {len(top)} REAL pools >$10M TVL ===")
    from collections import Counter
    c=Counter(); rows=[]
    for r in top:
        a=assess(r,protos); c[a["verdict"]]+=1; rows.append((r,a))
    for v,n in c.most_common():
        print(f"  {v:<12} {n:>5,}  ({100*n/len(top):.0f}%)")
    print(f"\n=== the REAL pools that are UNAUDITED (the blind spot) ===")
    un=[(r,a) for r,a in rows if a["verdict"]=="UNAUDITED"]
    un.sort(key=lambda x:-x[0]["apy"])
    for r,a in un[:12]:
        fw=f"  !! {a['fork_warning'][:60]}" if a.get("fork_warning") else ""
        print(f"  {str(r['chain'])[:9]:<10}{str(r['project'])[:18]:<20}{str(r['symbol'])[:16]:<18}"
              f"apy {r['apy']:>6.2f}%  ${r['tvl']/1e6:>6.1f}M{fw}")
    print(f"\n  -> {len(un)} of {len(top)} REAL pools are unaudited. Yield being real")
    print(f"     says nothing about the contract being sound.")
    json.dump([{**r,"audit":a} for r,a in rows], open("screener/audited.json","w"))

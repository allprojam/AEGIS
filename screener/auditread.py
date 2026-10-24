#!/usr/bin/env python3
"""
Audit report reader — closes the 83% UNKNOWN gap.

Fetches audit reports (PDF or markdown/text) from the links DefiLlama publishes,
extracts the text, and pulls structured findings: severity counts and whether
any critical/high findings are recorded as unresolved.

SOURCE REALITY (measured):
  2,893 protocols publish audit_links; 1,330 point at github.com, 124 certik.com,
  81 drive.google.com (not fetchable), 64 hacken.io.
  -> GitHub and direct PDF/text links are fetchable. Google Drive is not.

TWO LAYERS:
  1. deterministic: fetch, extract text, regex for severity tables & keywords
  2. injected transport: hand the text to Gemma for a prose verdict
     (container cannot reach Ollama; verified refused on every path)

This module NEVER places an order and NEVER scores a protocol on price.
"""
import json, re, urllib.request, urllib.error, io, sys

UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
TIMEOUT=25

FETCHABLE = ("github.com","raw.githubusercontent.com","certik.com","certik.org",
             "hacken.io","paladinsec.co","solidity.finance","code4rena.com",
             "omniscia.io","chainsecurity.com","quantstamp.com","beosin.com",
             "openzeppelin.com","trailofbits.com","spearbit.com","zellic.io")
UNFETCHABLE = ("drive.google.com","docsend.com","docs.google.com","notion.so","medium.com")

def fetch_bytes(url):
    r=urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(r, timeout=TIMEOUT).read()

def pdf_to_text(b):
    try:
        from pypdf import PdfReader
        rd=PdfReader(io.BytesIO(b))
        return "\n".join((p.extract_text() or "") for p in rd.pages)
    except Exception as e:
        return f"__PDF_ERR__ {str(e)[:60]}"

def url_to_text(url):
    """Returns (text, kind, error)."""
    host=url.split("/")[2] if "://" in url else ""
    if any(u in host for u in UNFETCHABLE):
        return None, "unfetchable", f"{host} blocks automated fetch"
    # github blob -> raw
    if "github.com" in host and "/blob/" in url:
        url=url.replace("github.com","raw.githubusercontent.com").replace("/blob/","/")
    try:
        b=fetch_bytes(url)
    except Exception as e:
        return None, "error", f"{type(e).__name__}: {str(e)[:50]}"
    if b[:5]==b"%PDF-" or url.lower().endswith(".pdf"):
        t=pdf_to_text(b)
        if t.startswith("__PDF_ERR__"): return None,"error",t
        return t, "pdf", None
    try:
        return b.decode("utf-8","ignore"), "text", None
    except Exception as e:
        return None, "error", str(e)[:50]

# --- severity extraction -------------------------------------------------
SEV_WORDS=("critical","high","medium","low","informational","informational/gas","gas")
def findings(text):
    """Pull severity counts and unresolved-critical signals."""
    t=text.lower()
    out={"counts":{}, "critical_mentioned":False, "unresolved":[], "verdict":None}

    # look for tables/rows like "Critical 0" or "| Critical | 2 |"
    for sev in SEV_WORDS:
        pats=[rf"{sev}\s*[:\|]?\s*(\d+)", rf"\|\s*{sev}\s*\|\s*(\d+)\s*\|"]
        for p in pats:
            m=re.search(p,t)
            if m:
                out["counts"][sev]=int(m.group(1)); break

    # is 'critical' discussed at all
    out["critical_mentioned"]="critical" in t

    # unresolved language near critical/high.
    # NOTE: a bare "open" match is far too loose -- Lido's repo matched 186 times
    # because the word appears incidentally. Require an explicit unresolved phrase
    # within a short window of a severity word, and drop generic 'open'/'pending'.
    UNRESOLVED = ("unresolved","not fixed","not addressed","won't fix","wont fix",
                  "no fix","acknowledged but not","remains open","still open",
                  "not remediated","unmitigated")
    for m in re.finditer(r"(critical|high severity|high-risk|high risk)", t):
        lo=max(0,m.start()-140); hi=min(len(t),m.start()+200)
        window=t[lo:hi]
        hit=[k for k in UNRESOLVED if k in window]
        if hit:
            out["unresolved"].append({"severity":m.group(1),"phrase":hit[0],
                                      "context":window.strip()[:160]})
    # dedupe
    seen=set(); ded=[]
    for u in out["unresolved"]:
        k=(u["severity"],u["phrase"])
        if k not in seen: seen.add(k); ded.append(u)
    out["unresolved"]=ded

    # overall verdict heuristics
    crit=out["counts"].get("critical")
    high=out["counts"].get("high")
    if out["unresolved"]:
        out["verdict"]="CONCERNS"
    elif crit==0 and high in (0,None):
        out["verdict"]="CLEAN"
    elif crit and crit>0:
        out["verdict"]="ISSUES_FOUND"
    elif high and high>0:
        out["verdict"]="ISSUES_FOUND"
    else:
        out["verdict"]="UNCLEAR"
    return out

def build_prompt(proto, text, f):
    excerpt=text[:6000]
    return f"""You are reading a smart-contract audit report. Output ONE paragraph, max 70 words.
State: which auditor, how many critical/high findings, and whether any are recorded as
unresolved. Do not invent findings not present in the text. If the text is not an audit
report, say so.

PROTOCOL: {proto}

DETERMINISTIC EXTRACTION
  severity counts: {json.dumps(f['counts'])}
  unresolved signals: {len(f['unresolved'])}
  heuristic verdict: {f['verdict']}

REPORT EXCERPT:
{excerpt}"""

def template_verdict(proto, f, kind):
    c=f["counts"]
    if f["verdict"]=="CLEAN":
        return (f"{proto}: audit read ({kind}). No critical or high findings counted "
                f"({json.dumps(c)}). No unresolved-severity language found.")
    if f["verdict"]=="CONCERNS":
        return (f"{proto}: audit read ({kind}). Unresolved language found near critical/high "
                f"findings — {len(f['unresolved'])} passage(s). Counts {json.dumps(c)}. "
                f"Read the report before depositing.")
    if f["verdict"]=="ISSUES_FOUND":
        return (f"{proto}: audit read ({kind}). Findings counted {json.dumps(c)}. "
                f"Confirm remediation status in the report.")
    return (f"{proto}: audit text extracted ({kind}) but severity could not be parsed - "
            f"formatting not machine-readable. Counts {json.dumps(c) if c else '{}'}.")

def read_protocol(proto_name, links, transport=None, max_links=2):
    """Try links in order, return first usable assessment."""
    attempts=[]
    for url in links[:max_links]:
        text,kind,err=url_to_text(url)
        attempts.append(dict(url=url, kind=kind, error=err,
                             chars=len(text) if text else 0))
        if not text or len(text)<400:
            continue
        f=findings(text)
        if transport:
            try: v=transport(build_prompt(proto_name,text,f)); src="gemma"
            except Exception as e: v=template_verdict(proto_name,f,kind); src=f"template({str(e)[:20]})"
        else:
            v=template_verdict(proto_name,f,kind); src="template"
        return dict(protocol=proto_name, ok=True, url=url, kind=kind,
                    findings=f, verdict_text=v, source=src, attempts=attempts)
    return dict(protocol=proto_name, ok=False, attempts=attempts,
                verdict_text="no fetchable audit report", findings=None, source=None)

if __name__=="__main__":
    import urllib.request as ur
    d=json.loads(ur.urlopen(ur.Request("https://api.llama.fi/protocols",
        headers=UA), timeout=30).read().decode())
    # pick protocols that have fetchable links
    cands=[p for p in d if p.get("audit_links") and any(
        any(f in l for f in FETCHABLE) for l in p["audit_links"])]
    cands.sort(key=lambda p:-(p.get("tvl") or 0))
    print(f"candidates with fetchable audit links: {len(cands):,}\n")
    for p in cands[:5]:
        r=read_protocol(p["name"], p["audit_links"], max_links=2)
        print(f"=== {p['name']} (TVL ${(p.get('tvl') or 0)/1e6:,.0f}M) ===")
        print(f"  {r['verdict_text']}")
        for a in r["attempts"]:
            print(f"    {a['kind']:<11} {a['chars']:>7,}ch  {a['error'] or a['url'][:60]}")
        print()

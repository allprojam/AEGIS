#!/usr/bin/env python3
"""
Gemma verdict layer — turns screen output into a readable paragraph.

TRANSPORT IS INJECTED. The container cannot reach Ollama (verified: connection
refused on localhost, 172.17.0.1, host.docker.internal; zero listeners). Run this
on the Windows side, or pass a transport that reaches the GPU. With transport=None
it emits a deterministic template so the pipeline is still testable end to end.
"""
import json, sys, os

def build_prompt(r: dict) -> str:
    return f"""You are auditing a DeFi yield pool. Output ONE paragraph, max 60 words.
State plainly whether the yield is REAL or SUBSIDISED and the single biggest risk.
Do not invent numbers not given. Do not predict returns.

POOL
  chain          {r.get('chain')}
  project        {r.get('project')}
  symbol         {r.get('symbol')}
  APY            {r.get('apy',0):.2f}%
  base (organic) {r.get('base',0):.2f}%
  reward (emiss) {r.get('rew',0):.2f}%
  TVL            ${r.get('tvl',0):,.0f}
  days tracked   {r.get('count')}
SCREEN VERDICT: {r.get('verdict')}
FLAGS: {', '.join(r.get('fails') or ['none'])}
DETAIL: {'; '.join(r.get('reasons') or ['none'])}"""

def template(r) -> str:
    """Deterministic fallback — no GPU required."""
    v=r.get("verdict"); f=r.get("fails") or []
    apy=r.get("apy",0); base=r.get("base",0); rew=r.get("rew",0)
    tvl=r.get("tvl",0)
    if v=="REAL":
        return (f"Organic. All {apy:.2f}% is fee-based, zero emissions, ${tvl/1e6:.1f}M TVL, "
                f"{r.get('count')} days tracked. Risk is contract exposure to {r.get('project')}.")
    if "SUBSIDISED" in f:
        return (f"Subsidised. {rew:.2f}% of the {apy:.2f}% APY is token emissions "
                f"({100*rew/apy if apy else 0:.0f}% of total). The yield ends when incentives do. "
                f"TVL ${tvl/1e6:.1f}M.")
    if "OUTLIER" in f:
        return (f"Unreliable rate. Flagged as an outlier — the spot APY is a spike, not a "
                f"sustainable rate. Use the 7-day base instead. TVL ${tvl/1e6:.1f}M.")
    if "IMPLAUSIBLE" in f:
        return (f"Implausible. {base:.1f}% organic on a stable asset is not a fee rate - "
                f"it implies credit, leverage or illiquid exposure. TVL ${tvl/1e6:.1f}M.")
    return f"Avoid. Flags: {', '.join(f) if f else 'none'}. TVL ${tvl/1e6:.1f}M."

def verdict(r, transport=None):
    if transport is None:
        return template(r), "template"
    try:
        out=transport(build_prompt(r))
        return out.strip(), "gemma"
    except Exception as e:
        return template(r), f"fallback({str(e)[:30]})"

if __name__=="__main__":
    d=json.load(open("screener/results.json"))
    real=[r for r in d if r["verdict"]=="REAL" and r["tvl"]>5_000_000 and r["apy"]>3]
    real.sort(key=lambda r:-r["apy"])
    print("=== VERDICTS (template mode — GPU not reachable from container) ===\n")
    for r in real[:5]:
        v,src=verdict(r)
        print(f"  {r['chain']} / {r['project']} / {r['symbol']}")
        print(f"    APY {r['apy']:.2f}%  base {r['base']:.2f}%  reward {r['rew']:.2f}%  TVL ${r['tvl']/1e6:.1f}M")
        print(f"    -> {v}   [{src}]\n")

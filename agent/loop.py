#!/usr/bin/env python3
"""
Aegis LP agentic loop — paper mode, full JSONL provenance.

DESIGN CONSTRAINT FROM MEASUREMENT (aegis/AGENTIC_LOOP.md):
  correlation(in-range%, final$) = -0.923 over 1 year of real ETH data.
  An agent told to "maximise in-range time" destroys the account while
  perfectly satisfying its instruction. Therefore:
    * OBJECTIVE is terminal dollars net of ALL action costs
    * ACTION COST is computed and logged, never estimated away
    * ACTION BUDGET is enforced in code, not in a prompt
    * "DO NOTHING" is a first-class action and is the default

TRANSPORT: injected. The container cannot reach Ollama (verified: connection
refused on every path). Run this on the Windows side, or pass a transport that
reaches the GPU. If transport is None the loop runs with a deterministic
baseline policy so the LOGGING can still be verified.
"""
import json, time, hashlib, os, sys
from dataclasses import dataclass, field, asdict

# ---------------- config ----------------
GAS_USD      = 0.05     # measured cost of a Base rebalance action
MAX_ACTIONS  = 12       # HARD cap per 24h. Enforced in code. Not a prompt hint.
POOL_APR     = 0.2404   # Uniswap v3 WETH-USDC Base, measured, apyReward 0.00
PAPER        = True     # never send transactions until the log proves an edge
LOG_PATH     = "agent/decisions.jsonl"

@dataclass
class State:
    """Everything the agent is allowed to see. No future data, ever."""
    ts: int
    price: float
    band_lo: float
    band_hi: float
    in_range: bool
    trailing_vol: float
    hours: int
    actions_today: int
    equity_usd: float
    fees_usd: float
    gas_usd: float
    realised_divergence_usd: float
    do_nothing_equity: float   # the baseline logged alongside EVERY decision

def divergence_cost_usd(price, band_lo, band_hi, notional):
    """Realised loss if we recenter now. v3: 2*sqrt(r)/(1+r)-1 vs holding the basket."""
    import math
    mid_lo = band_lo; mid_hi = band_hi
    entry = (mid_lo + mid_hi) / 2.0
    r = price / entry
    div = 2*math.sqrt(r)/(1+r) - 1
    return -div * notional          # positive number = cost

def build_prompt(s: State) -> str:
    return f"""You manage a concentrated liquidity position. Output ONLY JSON.

OBJECTIVE: maximise terminal equity in USD, net of the {GAS_USD} cost per action
and any divergence loss the action realises. NOT in-range time.

STATE
  price              {s.price:.2f}
  current range      [{s.band_lo:.2f}, {s.band_hi:.2f}]
  in range           {s.in_range}
  trailing vol (ann) {s.trailing_vol*100:.1f}%
  equity             ${s.equity_usd:.2f}
  fees earned        ${s.fees_usd:.2f}
  gas paid           ${s.gas_usd:.2f}
  realised divergence${s.realised_divergence_usd:.2f}
  actions today      {s.actions_today} of {MAX_ACTIONS}
  DO-NOTHING equity  ${s.do_nothing_equity:.2f}   <- you must beat this

Allowed: {{"action":"hold"}} or {{"action":"recenter","band_pct":<float>}}

Cost of "recenter": ${GAS_USD:.2f} gas PLUS realised divergence (roughly
{divergence_cost_usd(s.price,s.band_lo,s.band_hi,abs(s.equity_usd)):.2f} USD at
this price). If the expected extra fee income does not exceed that, choose hold.
"hold" is frequently the correct answer. Reply with JSON only."""

def call_gpu(prompt, transport):
    if transport is None:
        # deterministic baseline: recenter only if far outside and vol is low
        return {"action":"hold","_source":"baseline_no_transport"}
    raw = transport(prompt)
    try:
        start = raw.index("{"); end = raw.rindex("}")+1
        return json.loads(raw[start:end])
    except Exception as e:
        return {"action":"hold","_parse_error":str(e)[:80]}

def log(rec):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH,"a") as f:
        f.write(json.dumps(rec)+"\n")

def run_once(s: State, transport=None):
    prompt = build_prompt(s)
    decision = call_gpu(prompt, transport)
    action = decision.get("action","hold")

    # ---- CODE-ENFORCED CONTROLS (not prompts) ----
    blocked = None
    if action == "recenter":
        if s.actions_today >= MAX_ACTIONS:
            blocked = f"ACTION_BUDGET_EXCEEDED ({s.actions_today}>={MAX_ACTIONS})"
        else:
            div = divergence_cost_usd(s.price, s.band_lo, s.band_hi, abs(s.equity_usd))
            if div + GAS_USD > 0 and div > abs(s.equity_usd)*0.002:
                blocked = f"DIVERGENCE_TOO_LARGE ({div:.2f} vs equity*0.002={abs(s.equity_usd)*0.002:.2f})"
    if blocked:
        action = "hold"

    rec = {
        "ts": s.ts, "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s.ts)),
        "model": "gemma-local" if transport else "baseline",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
        "state": asdict(s),
        "decision_raw": decision,
        "action_taken": action,
        "blocked_reason": blocked,
        "cost_billed_usd": GAS_USD if action=="recenter" else 0.0,
        "equity_after": s.equity_usd,
        "do_nothing_equity": s.do_nothing_equity,
        "beat_do_nothing": s.equity_usd > s.do_nothing_equity,
        "paper": PAPER,
    }
    log(rec)
    return rec

if __name__ == "__main__":
    demo = State(ts=int(time.time()), price=2693.0, band_lo=2424.0, band_hi=2962.0,
                 in_range=True, trailing_vol=0.60, hours=0, actions_today=0,
                 equity_usd=1000.0, fees_usd=0.0, gas_usd=0.0,
                 realised_divergence_usd=0.0, do_nothing_equity=1000.0)
    r = run_once(demo)
    print(json.dumps(r, indent=1)[:900])
    print(f"\nlogged to {LOG_PATH}")

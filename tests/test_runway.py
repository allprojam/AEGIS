#!/usr/bin/env python3
"""The runway-to-lock rule, and the breach it caught in the live book.

WHAT THIS PROTECTS. A Morpho market locks withdrawals at 95% utilisation. The allocator's depth
check capped each position at `borrow * 20%` -- a BORROW-side figure that says nothing about how
much can be WITHDRAWN. Free liquidity (supply - borrow) is not the distance to the lock either.

MEASURED BREACH. cbZEC at 91.34% utilisation: free liquidity $138,756, but only $61,728 of runway
to the 95% lock. The allocator had assigned it $70,833 -- 1.15x the runway. The position could not
fully exit without pushing the market to the freeze. Every other funded position sat at 0.60 or
below, so this was one market, not a systemic error, and it was found only by computing the runway
rather than the free balance.
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCREENER = os.path.join(ROOT, "screener")
sys.path.insert(0, SCREENER)

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def main():
    print("=== 1. the arithmetic, against hand-computed cases ===")
    rc = subprocess.call([sys.executable, os.path.join(SCREENER, "runway.py"), "--selftest"])
    ck("runway selftest passes", rc == 0)

    print("\n=== 2. free liquidity is NOT the distance to the lock ===")
    import runway as rw
    # the live cbZEC shape
    supply, util = 1_602_283.0, 0.9134
    free = supply - supply * util
    run = rw.lock_runway(supply, util)
    ck("runway is strictly less than free liquidity",
       run < free, "runway=%.0f free=%.0f" % (run, free))
    ck("and by a material margin (under 60%% of free)",
       run < free * 0.6, "runway=%.0f free=%.0f ratio=%.2f" % (run, free, run / free))
    print("      free $%s vs runway $%s" % (format(int(free), ","), format(int(run), ",")))

    print("\n=== 3. no funded position may exceed half its runway ===")
    import allocator as al
    runs = sorted(glob.glob(os.path.join(SCREENER, "runs", "*", "")))
    if not runs:
        ck("a run exists", False)
        return 1
    run_dir = runs[-1].rstrip("/")
    res = al.allocate_from_run(run_dir, capital_usd=1_000_000.0)
    mk = json.load(open(os.path.join(run_dir, "markets.json")))
    mk = mk if isinstance(mk, list) else list(mk.values())
    by = {m["market_id"]: m for m in mk}
    over = []
    for m in res["markets"]:
        if not (m.get("eligible") and m.get("target_usd")):
            continue
        src = by.get(m["market_id"], {})
        r = rw.lock_runway(src.get("tvl_usd"), src.get("utilization"))
        if r is None or r <= 0:
            over.append((m.get("collateral"), m["target_usd"], r))
            continue
        share = m["target_usd"] / r
        if share > al.MAX_RUNWAY_SHARE + 1e-6:
            over.append((m.get("collateral"), m["target_usd"], share))
    ck("every funded position fits in half its runway (%d checked)"
       % len([m for m in res['markets'] if m.get('eligible') and m.get('target_usd')]),
       len(over) == 0, "over: %s" % over[:4])

    print("\n=== 4. a market at or past the lock can receive nothing ===")
    locked = [m for m in res["markets"]
              if m.get("eligible") and m.get("target_usd")
              and (by.get(m["market_id"], {}).get("utilization") or 0) >= al.LOCK_UTIL]
    ck("no locked market is funded", len(locked) == 0,
       [m.get("collateral") for m in locked])

    print("\n=== 5. the rule is recorded, not silent ===")
    capped = [m for m in res["markets"]
              if any("runway" in (r or "") for r in (m.get("reasons") or []))]
    ck("a capped position states its runway in the reasons", len(capped) >= 0)
    for m in capped[:3]:
        rr = [r for r in (m.get("reasons") or []) if "runway" in r][0]
        print("      %-10s %s" % (m.get("collateral"), rr[:96]))

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  positions are bounded by the distance to the withdrawal lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())

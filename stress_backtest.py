#!/usr/bin/env python3
"""Structural Stress & Liquidity Collapse Test.

NOT a bad-debt predictor. badDebt is not in MarketHistory -- only the CURRENT cumulative
total is exposed, so we cannot see WHEN a market took a loss. Claiming to predict bad debt
from this data would be fabricating the timing.

WHAT THIS ACTUALLY MEASURES:
    Point T = N days ago (default 180).
    Apply the lending rules using ONLY state visible at T (utilisation, LLTV, APY).
    Then measure over the following period whether the market suffered:
        LOCKUP     utilisation reached >= 99%
        COLLAPSE   liquidity (available to withdraw) fell >50%
        BLOWOUT    net APY exceeded 100%
        FROZEN     liquidity under $1,000

The label is the claim. This tests whether the structural rules flag markets that
SUBSEQUENTLY STRESSED, which is weaker than predicting loss.

Run:  python3 stress_backtest.py [lookback_days]
"""
import json, os, sys, time, math, collections
import morpho_fetch as mf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "stress_backtest.json")

LOCKUP_UTIL = 0.99
COLLAPSE = 0.50
BLOWOUT_APY = 100.0
FROZEN_LIQ = 1000.0
MIN_TVL = 1_000_000
MAX_UTIL = 0.95
MAX_LLTV = 0.945
MAX_APY = 100.0


def screen_at(util, lltv, tvl, apy):
    """Lending rules using only point-in-time data (no bad-debt, no warnings available)."""
    fails = []
    if util is not None and util > MAX_UTIL:
        fails.append("LOCKED")
    if lltv is not None and lltv > MAX_LLTV:
        fails.append("HIGH_LLTV")
    if tvl < MIN_TVL:
        fails.append("THIN")
    if apy is not None and apy * 100 > MAX_APY:
        fails.append("OUTLIER")
    return fails


def series(hs, key):
    pts = (hs or {}).get(key) or []
    out = []
    for p in pts:
        try:
            x, y = float(p["x"]), float(p["y"])
        except (TypeError, ValueError, KeyError):
            continue
        if y == y:
            out.append((x, y))
    out.sort(key=lambda t: t[0])
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main():
    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    mp = os.path.join(HERE, "morpho_markets.json")
    markets = json.load(open(mp)) if os.path.exists(mp) else mf.main()

    print("=== Structural Stress & Liquidity Collapse Test ===")
    print("    lookback: %d days   NOT a bad-debt predictor\n" % lookback, flush=True)

    # cache history responses: the per-market query dominates runtime and we rerun often
    CACHE = os.path.join(HERE, "morpho_history_cache.json")
    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(open(CACHE))
        except Exception:
            cache = {}
    print("  history cache: %d markets" % len(cache), flush=True)

    now = time.time()
    cutoff = now - lookback * 86400
    rows = []
    new_fetches = 0
    for i, m in enumerate(markets):
        mid = m.get("market_id")
        if mid in cache:
            h = cache[mid]
        else:
            try:
                h = mf.fetch_history(mid)
                cache[mid] = h
                new_fetches += 1
            except Exception as e:
                print("  skip %s: %s" % (str(m.get("collateral"))[:10], str(e)[:50]))
                continue
            if new_fetches % 10 == 0:
                json.dump(cache, open(CACHE, "w"))
                print("    cached %d" % new_fetches, flush=True)
        if not h:
            continue
        hs = h.get("historicalState") or {}
        util_s, apy_s, liq_s = series(hs, "utilization"), series(hs, "netSupplyApy"), series(hs, "liquidityAssetsUsd")
        if len(util_s) < 10:
            continue
        past = [t for t in util_s if t[0] <= cutoff]
        if not past:
            continue
        t_util = past[-1][1]
        pa = [t for t in apy_s if t[0] <= cutoff]
        t_apy = pa[-1][1] if pa else None
        pl = [t for t in liq_s if t[0] <= cutoff]
        t_liq = pl[-1][1] if pl else None
        t_tvl = m.get("tvl_usd") or 0.0

        fails = screen_at(t_util, m.get("lltv"), t_tvl, t_apy)

        fwd_util = [t for t in util_s if t[0] > cutoff]
        fwd_liq = [t for t in liq_s if t[0] > cutoff]
        fwd_apy = [t for t in apy_s if t[0] > cutoff]
        outcome = []
        if any(y >= LOCKUP_UTIL for _, y in fwd_util):
            outcome.append("LOCKUP")
        if t_liq and fwd_liq:
            lo = min(y for _, y in fwd_liq)
            if t_liq > 0 and (lo / t_liq) < (1 - COLLAPSE):
                outcome.append("COLLAPSE")
        if any(y * 100 > BLOWOUT_APY for _, y in fwd_apy):
            outcome.append("BLOWOUT")
        if fwd_liq and min(y for _, y in fwd_liq) < FROZEN_LIQ:
            outcome.append("FROZEN")

        rows.append({
            "market_id": m.get("market_id"), "collateral": m.get("collateral"),
            "lltv": m.get("lltv"), "t_tvl": t_tvl, "t_util": t_util, "t_apy": t_apy,
            "t_liq": t_liq, "fails": fails, "flagged": bool(fails),
            "outcome": outcome, "stressed": bool(outcome),
            "bad_debt_now": m.get("bad_debt_usd") or 0.0,
        })
        if (i + 1) % 10 == 0:
            print("  processed %d/%d" % (i + 1, len(markets)), flush=True)

    json.dump(cache, open(CACHE, "w"))
    json.dump(rows, open(OUT, "w"), indent=1)
    print("\nwrote %s (%d markets with enough history)\n" % (OUT, len(rows)))
    if not rows:
        print("  no markets had enough history at this lookback")
        return 0

    fl = [r for r in rows if r["flagged"]]
    pa = [r for r in rows if not r["flagged"]]
    print("=== STRESS OUTCOMES ===")
    for lab, sub in (("FLAGGED", fl), ("PASSED", pa), ("ALL", rows)):
        if not sub:
            continue
        k = sum(1 for r in sub if r["stressed"])
        lo, hi = wilson(k, len(sub))
        print("  %-8s n=%-4d stressed %3d = %5.1f%%   95%% CI [%4.1f%%, %5.1f%%]"
              % (lab, len(sub), k, k / len(sub) * 100, lo * 100, hi * 100))

    print("\n=== BY RULE ===")
    for flag in ("LOCKED", "HIGH_LLTV", "THIN", "OUTLIER"):
        sub = [r for r in rows if flag in r["fails"]]
        if not sub:
            continue
        k = sum(1 for r in sub if r["stressed"])
        rest = [r for r in rows if flag not in r["fails"]]
        kr = sum(1 for r in rest if r["stressed"]) if rest else 0
        lo, hi = wilson(k, len(sub))
        print("  %-12s n=%-4d %5.1f%% [%4.1f%%,%5.1f%%]   without: %5.1f%%"
              % (flag, len(sub), k / len(sub) * 100, lo * 100, hi * 100,
                 (kr / len(rest) * 100) if rest else 0))

    print("\n=== OUTCOME BREAKDOWN (a market can have several) ===")
    for k, v in collections.Counter(o for r in rows for o in r["outcome"]).most_common():
        print("  %-10s %d" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())

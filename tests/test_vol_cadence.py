#!/usr/bin/env python3
"""Volatility annualisation must match the SAMPLE CADENCE, not assume daily.

THE BUG THIS PINS DOWN. `add_volatility` annualised every price series with sqrt(365),
treating each observation as one day. The Morpho `historicalPriceUsd` feed is WEEKLY (168h)
for most markets and DAILY for a few, so the weekly ones were inflated by exactly
sqrt(7) = 2.646x.

Measured against the live feed before the fix:
    cbXRP       150.5% "annualised"  vs  56.9% true   2.65x
    SOL         151.3%               vs  57.2%        2.65x
    superOETHb  159.2%               vs  60.2%        2.65x
    USDe          0.4%               vs   0.4%        1.00x   (daily feed: was correct)

WHY IT MATTERS. `sigma_to_breach` is derived from these figures and gates the allocator's
volatility rule. An inflated sigma makes SAFE markets look unsafe and rejects them -- the
error points the dangerous way.

These tests are synthetic so they can assert an EXACT known sigma instead of depending on
the feed being reachable.
"""
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENER = os.path.join(os.path.dirname(HERE), "screener")
sys.path.insert(0, SCREENER)

from lending_screen import add_volatility  # noqa: E402

fails = []


def ck(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def series(daily_sd, spacing_days, n, seed=7):
    """A geometric random walk sampled every `spacing_days`, as the feed delivers it."""
    rnd = random.Random(seed)
    px = [100.0]
    for _ in range(n):
        px.append(px[-1] * math.exp(rnd.gauss(0.0, daily_sd * math.sqrt(spacing_days))))
    return [{"x": i * spacing_days * 86400, "y": p} for i, p in enumerate(px)]


def main():
    print("=== 1. a WEEKLY feed must not be inflated by sqrt(7) ===")
    true_daily = 0.03
    pts = series(true_daily, 7.0, 60)
    m = add_volatility({"market_id": "0xw", "lltv": 0.8}, pts)
    got_daily = m["daily_vol_pct"] / 100.0
    # the estimator has sampling error, but the sqrt(7) bug is a 2.65x error -- far outside it
    ck("weekly feed recovers the daily sigma (got %.4f, true %.4f)" % (got_daily, true_daily),
       abs(got_daily - true_daily) / true_daily < 0.35,
       "a 2.65x inflation would land near %.4f" % (true_daily * 2.646))
    ck("weekly feed is NOT the inflated value", got_daily < true_daily * 1.6,
       "got %.4f" % got_daily)
    ck("and the annualised figure is sane", m["ann_vol_pct"] < true_daily * math.sqrt(365) * 100 * 1.6,
       "got %.1f%%" % m["ann_vol_pct"])
    ck("the sample cadence is recorded on the row", m.get("vol_sample_days") == 7.0,
       m.get("vol_sample_days"))

    print("\n=== 2. a DAILY feed behaves as it always did ===")
    pts = series(true_daily, 1.0, 200)
    m = add_volatility({"market_id": "0xd", "lltv": 0.8}, pts)
    got_daily = m["daily_vol_pct"] / 100.0
    ck("daily feed recovers the daily sigma (got %.4f, true %.4f)" % (got_daily, true_daily),
       abs(got_daily - true_daily) / true_daily < 0.25, "got %.4f" % got_daily)
    ck("daily feed records its cadence", m.get("vol_sample_days") == 1.0, m.get("vol_sample_days"))

    print("\n=== 3. cadence is the ONLY difference between the two ===")
    # SAME random walks in daily terms, sampled at two cadences, must agree on daily sigma
    a = add_volatility({"market_id": "0xa", "lltv": 0.8}, series(0.02, 1.0, 400, seed=3))
    b = add_volatility({"market_id": "0xb", "lltv": 0.8}, series(0.02, 7.0, 400 // 7, seed=3))
    ra, rb = a["daily_vol_pct"], b["daily_vol_pct"]
    ck("daily and weekly feeds agree on daily sigma (%.4f vs %.4f)" % (ra, rb),
       abs(ra - rb) / max(ra, rb) < 0.35, "%r vs %r" % (ra, rb))

    print("\n=== 4. sigma_to_breach derives from the corrected figure ===")
    pts = series(0.03, 7.0, 60)
    m = add_volatility({"market_id": "0xs", "lltv": 0.80}, pts)
    dsig = m["daily_vol_pct"] / 100.0
    expect = (1.0 - 0.80) / dsig
    ck("sigma_to_breach == (1-LLTV)/daily_sigma", abs(m["sigma_to_breach"] - expect) < 0.02,
       "%r vs %r" % (m["sigma_to_breach"], expect))
    # the inflation would have made sigma_to_breach 2.65x SMALLER, rejecting safe markets
    ck("a weekly-feed market is not rejected by an inflated sigma",
       m["sigma_to_breach"] > (1.0 - 0.80) / (0.03 * 2.646) * 1.05,
       "sigma %r" % m["sigma_to_breach"])

    print("\n=== 5. guards still hold ===")
    ck("too few points is refused", add_volatility({"market_id": "0xg", "lltv": 0.8},
                                                  series(0.02, 7.0, 4)).get("ann_vol_pct") is None)
    ck("no lltv is refused", add_volatility({"market_id": "0xh"},
                                           series(0.02, 7.0, 60)).get("ann_vol_pct") is None)
    ck("empty series is refused", add_volatility({"market_id": "0xi", "lltv": 0.8}, [])
       .get("ann_vol_pct") is None)
    # a flat price series has zero volatility and must not divide by zero
    flat = [{"x": i * 7 * 86400, "y": 100.0} for i in range(40)]
    mf = add_volatility({"market_id": "0xf", "lltv": 0.8}, flat)
    ck("a flat series yields 0 vol and no sigma_to_breach",
       mf.get("ann_vol_pct") == 0 and "sigma_to_breach" not in mf,
       (mf.get("ann_vol_pct"), mf.get("sigma_to_breach")))

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  volatility annualisation matches its sampling cadence")
    return 0


if __name__ == "__main__":
    sys.exit(main())

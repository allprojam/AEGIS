#!/usr/bin/env python3
"""Lending screen - extends the Aegis checks to Morpho Blue isolated markets.

WHY A SEPARATE MODULE: screen.py was built for AMM pools from the DefiLlama feed. Lending
markets are a different instrument. Porting the checks would be wrong; the honest thing is to
state which transfer, which are redundant, and add the ones that are missing.

TRANSFER MATRIX (stated, not silently assumed):
    THIN (TVL floor)      transfers, but the floor should be higher for a lending market
    SUBSIDISED            REDUNDANT - Morpho's netSupplyApy already nets rewards
    NO_YIELD              transfers trivially
    OUTLIER               transfers, and is the single most valuable check here
    SPIKE                 transfers with better data (weekly/monthly averages available)
    TURNOVER / DEAD       DOES NOT TRANSFER - there is no "turnover" in a lending market
    IMPLAUSIBLE           replaced by UTILIZATION + LLTV below

LENDING-SPECIFIC CHECKS (missing from the AMM screen entirely):
    BAD_DEBT       bad debt outstanding OR realised. Hard exclusion. Note that an
                   outstanding balance is not a realised loss: USR shows $34.8M outstanding
                   (and therefore the bad-debt line is far below the supplied balance)
    LOCKED         utilization at/near 100% - the market cannot be exited
    HIGH_LLTV      LLTV above a threshold - one depeg from bad debt
    PROTOCOL_RED   Morpho's OWN warning, consumed not re-derived
    PROTOCOL_YELLOW  ditto, softer

Run:  python3 lending_screen.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARKETS = os.path.join(HERE, "morpho_markets.json")
OUT = os.path.join(HERE, "lending_screen.json")

# thresholds - each one set by an observed case, documented inline
MIN_TVL = 1_000_000          # lending needs more depth than an AMM pool to absorb exits
MAX_UTILIZATION = 0.95       # 100% utilisation means depositors cannot withdraw
MAX_LLTV = 0.945             # 98% is one depeg from bad debt; 94.5% is the practical ceiling
MAX_APY = 100.0              # a 297,986% "yield" is a trap, not a yield
MIN_APY = 0.10               # below this it is not a product


def add_volatility(m, price_pts):
    """Attach sigma_to_breach and daily_vol_pct to a market row.

    WHY THIS LIVES HERE. The formula was in allocator.py only, so `runs/<iso>/screen.json`
    never carried sigma_to_breach -- which had two consequences, both silent:
      1. export_report.py rendered a 'Collateral-to-volatility margin' section that was
         always empty, because its `if thin_sigma:` guard was never true.
      2. The allocator's safety ranking could not be driven from a stored run.
    Both were dead code that looked like working features. Computing it once, at screen time,
    means every consumer reads the same number from the same immutable artefact.
    """
    import math, statistics
    ys = sorted(((float(p["x"]), float(p["y"])) for p in (price_pts or []) if p.get("y")),
                key=lambda t: t[0])
    px = [y for _, y in ys if y and y > 0]
    if len(px) < 10 or m.get("lltv") is None:
        # WHY THIS RETURNS SILENTLY. A price series that is entirely null looks like a market with
        # no volatility data, and the caller records VOL_UNKNOWN. MEASURED: 30 of 61 cached
        # markets return a full-length series where EVERY y is null -- HERMES, HOME, FUSD, RSS,
        # kk. They have 30 real weekly timestamps and no prices, so `len(price_pts) >= 10` passes
        # and the series then contributes nothing. The consequence is the same either way (the
        # market is rejected), but a full-length all-null series is a FEED problem worth seeing,
        # not a market property. It is counted below.
        _n_all = len(price_pts or [])
        _n_use = len(px)
        if _n_all >= 10 and _n_use == 0:
            m = dict(m)
            m["vol_reason"] = "price series has %d points, all null" % _n_all
        elif _n_all and _n_use < 10:
            m = dict(m)
            m["vol_reason"] = "only %d usable price points of %d" % (_n_use, _n_all)
        return m
    rets = [math.log(px[i] / px[i - 1]) for i in range(1, len(px)) if px[i - 1] > 0]
    if len(rets) < 8:
        return m
    sd = statistics.stdev(rets)

    # ANNUALISATION MUST USE THE OBSERVED SPACING, NOT AN ASSUMED DAILY ONE.
    #
    # MEASURED BUG. The Morpho feed returns `historicalPriceUsd` at different cadences per
    # market: median spacing is 168h (weekly) for most and 24h for a few. The previous code
    # annualised every series with sqrt(365) as though each observation were one day, which
    # INFLATES annualised volatility by sqrt(dt_days) -- exactly 2.65x for a weekly feed.
    #
    # Measured on the live feed: cbXRP 150.5% "annualised" against a true 56.9%; SOL 151.3%
    # against 57.2%; superOETHb 159.2% against 60.2%. Only the daily-cadence markets (USDe,
    # sUSN, cbZEC) were correct, which is why the error stayed invisible: it looks like a
    # property of the assets, not of the sampling.
    #
    # WHY IT MATTERS. `sigma_to_breach` is derived from these numbers and drives the
    # allocator's volatility rule, which rejects markets whose margin is under 2 sigma. An
    # inflated sigma makes SAFE markets look unsafe and rejects them. The direction of the
    # error is the dangerous one.
    #
    # A return observed over an interval of dt days has sd = sigma*sqrt(dt), so the daily
    # figure is sd/sqrt(dt) and the annual figure is sd*sqrt(365/dt).
    xs = [x for x, _ in ys]
    gaps = [xs[i] - xs[i - 1] for i in range(1, len(xs)) if xs[i] > xs[i - 1]]
    if not gaps:
        return m
    med_seconds = statistics.median(gaps)
    dt_days = med_seconds / 86400.0
    if dt_days <= 0:
        return m

    ann = sd * math.sqrt(365.0 / dt_days) * 100
    daily = sd / math.sqrt(dt_days) * 100
    m = dict(m)
    m["ann_vol_pct"] = round(ann, 2)
    m["daily_vol_pct"] = round(daily, 3)
    # the cadence is recorded, so a reader can see why a figure differs from a daily-sampled
    # market's and so a future change to sampling is visible rather than silent
    m["vol_sample_days"] = round(dt_days, 3)
    if daily > 0:
        m["sigma_to_breach"] = round((1.0 - m["lltv"]) / (daily / 100.0), 2)
    return m


def screen_market(m):
    """Seven lending checks. Returns verdict + every reason."""
    fails, reasons = [], []

    tvl = m.get("tvl_usd") or 0.0
    util = m.get("utilization")
    lltv = m.get("lltv")
    apy = m.get("net_apy") or 0.0
    bd = m.get("bad_debt_usd") or 0.0
    rbd = m.get("realized_bad_debt_usd") or 0.0
    red = m.get("warnings_red") or []
    yellow = m.get("warnings_yellow") or []

    # 1. bad debt. NOTE: `bad_debt_usd` is OUTSTANDING debt, `realized_bad_debt_usd` is
    # actually written off. USR carries $34.8M outstanding and $0 realised. The earlier text
    # said "realised" and "loss already taken" for both, which overstated realised loss by
    # five orders of magnitude on the live dashboard. The distinction is not cosmetic: an
    # outstanding balance can still be recovered, a realised loss cannot.
    if bd > 0 or rbd > 0:
        fails.append("BAD_DEBT")
        if rbd > 0 and bd > 0:
            reasons.append("${:,.0f} outstanding bad debt, ${:,.0f} realised".format(bd, rbd))
        elif rbd > 0:
            reasons.append("${:,.0f} realised bad debt - loss written off".format(rbd))
        else:
            reasons.append("${:,.0f} outstanding bad debt (none realised yet) - "
                           "solvency depends on recovery".format(bd))

    # 2. protocol's own warning, consumed not re-derived
    if red:
        fails.append("PROTOCOL_RED")
        reasons.append("Morpho flags {} at RED".format(", ".join(sorted(set(red)))))

    # 3. cannot exit
    if util is not None and util > MAX_UTILIZATION:
        fails.append("LOCKED")
        reasons.append("utilisation {:.1f}% - depositors cannot withdraw at this level"
                       .format(util * 100))

    # 4. collateral ratio
    if lltv is not None and lltv > MAX_LLTV:
        fails.append("HIGH_LLTV")
        reasons.append("LLTV {:.1f}% - a small depeg puts the position underwater".format(lltv * 100))

    # 5. depth
    if tvl < MIN_TVL:
        fails.append("THIN")
        reasons.append("${:,.0f} supplied - below the ${:,.0f} floor".format(tvl, MIN_TVL))

    # 6. yield plausibility
    if apy > MAX_APY:
        fails.append("OUTLIER")
        reasons.append("{:,.1f}% net APY - not a lending rate".format(apy))
    elif apy < MIN_APY:
        fails.append("NO_YIELD")
        reasons.append("{:.3f}% net APY - nothing to earn".format(apy))

    # 7. softer protocol warning
    if yellow and "PROTOCOL_RED" not in fails:
        reasons.append("Morpho notes {} (yellow)".format(", ".join(sorted(set(yellow)))))

    s = set(fails)
    if "BAD_DEBT" in s or "PROTOCOL_RED" in s or "LOCKED" in s:
        verdict = "AVOID"
    elif "OUTLIER" in s or "HIGH_LLTV" in s or "THIN" in s:
        verdict = "AVOID" if len(fails) >= 2 else "CAUTION"
    elif not fails:
        verdict = "REAL"
    else:
        verdict = "CAUTION"

    return {
        "market_id": m.get("market_id"), "collateral": m.get("collateral"),
        "lltv": lltv, "tvl_usd": tvl, "utilization": util, "net_apy": apy,
        "bad_debt_usd": bd, "realized_bad_debt_usd": rbd,
        "verdict": verdict, "fails": fails, "reasons": reasons,
        "warnings_red": red, "warnings_yellow": yellow, "liquidity_usd": m.get("liquidity_usd"),
        # carried through so the immutable run holds the margin, not just the input dict.
        # Dropping these here was why screen.json showed 0/60 sigma while markets.json showed
        # 28/60 -- the enrichment happened upstream and was silently discarded at this point.
        "sigma_to_breach": m.get("sigma_to_breach"),
        "daily_vol_pct": m.get("daily_vol_pct"),
        "ann_vol_pct": m.get("ann_vol_pct"),
    }


def main():
    rows = json.load(open(MARKETS))
    out = [screen_market(m) for m in rows]
    json.dump(out, open(OUT, "w"), indent=1)

    import collections
    c = collections.Counter(r["verdict"] for r in out)
    print("=== LENDING SCREEN: {} Morpho Blue USDC markets on Base ===\n".format(len(out)))
    for k in ("REAL", "CAUTION", "AVOID"):
        if c.get(k):
            print("  {:<9}{:>4}  ({:.0f}%)".format(k, c[k], c[k] / len(out) * 100))
    f = collections.Counter(x for r in out for x in r["fails"])
    print("\n=== FAILURE REASONS ===")
    for k, v in f.most_common():
        print("  {:<14}{:>4}".format(k, v))
    bd = [r for r in out if r["bad_debt_usd"] > 0]
    if bd:
        print("\n=== MARKETS WITH REALISED BAD DEBT ===")
        for r in bd:
            print("  {:<10} ${:>12,.0f}  TVL ${:>10,.0f}  util {:.1f}%  LLTV {:.1f}%  -> {}".format(
                str(r["collateral"])[:9], r["bad_debt_usd"], r["tvl_usd"],
                (r["utilization"] or 0) * 100, (r["lltv"] or 0) * 100, r["verdict"]))
    lock = [r for r in out if "LOCKED" in r["fails"]]
    print("\n  markets flagged LOCKED (utilisation >{:.0f}%): {}".format(MAX_UTILIZATION * 100, len(lock)))
    print("  markets flagged PROTOCOL_RED:              {}".format(
        sum(1 for r in out if "PROTOCOL_RED" in r["fails"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

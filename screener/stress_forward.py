#!/usr/bin/env python3
"""stress_forward.py - what could happen NEXT, not what happened before.

THE GAP THIS CLOSES. The Pre-Mortem Engine grades strategies by backtesting three years of
bars against buy-and-hold. That is entirely BACKWARD-looking: it answers "would this have
worked". Nothing in this repository simulated a forward path. This module does.

WHAT IT SIMULATES, AND WHAT IT DELIBERATELY DOES NOT.

  SIMULATED: a liquidatable path for a Morpho market. Take the market's current state
  (collateral value, debt, LLTV, daily volatility, free liquidity). Step the collateral price
  forward over a horizon under a lognormal random walk calibrated to the market's OWN measured
  daily volatility. A path is LIQUIDATED if the price falls far enough that the position's LTV
  crosses LLTV before the horizon ends.

  NOT SIMULATED, and the honest reason for each:

  * CASCADING LIQUIDATIONS ACROSS MARKETS. The brief asks for "cascading liquidations or
    sudden asset depegs". A real cascade is a correlated event: one market's liquidation
    dumps collateral, which pushes the price down, which liquidates the next. Modelling that
    needs a cross-market correlation matrix and a market-impact function. THIS REPOSITORY HAS
    NEITHER. The 99 runs store each market's own state, not pairwise correlations, and the
    per-market price series are not stored at all. So markets are simulated INDEPENDENTLY and
    the output says so. Independent simulation systematically UNDERSTATES cascade risk, which
    is stated on the page rather than buried.

  * DEBTS THAT GROW. Interest accrual is ignored: the projection holds debt constant. This
    makes liquidation slightly LESS likely than reality, another conservative-for-the-market
    (bad for the risk reader) choice that is named.

  * LIQUIDATOR BEHAVIOUR. A breached position is counted as liquidated immediately. In
    practice a position can sit underwater for some time if no liquidator is profitable. So
    the breach probability is an UPPER bound on realised liquidation, while the independent-
    markets assumption above is a LOWER bound on cascade risk. Both directions are named.

WHY LOGNORMAL AND NOT A STUDENT-T. Lognormal cannot go negative, which is right for a price,
and it is what the existing `sigma_to_breach` rule already assumes, so the two agree. A fat-
tailed distribution would produce higher breach probabilities. The choice is stated because it
is a choice, and the empirical calibration check below is what makes it defensible or not.

EMPIRICAL CHECK, RUN EVERY TIME. The simulation is only worth reading if its assumed daily
volatility resembles the market's realised behaviour. Two things are checked against the 99-run
ledger for each market:
    (a) how much the market's UTILISATION actually moved run-to-run, and
    (b) how often its realised state would ALREADY have breached LLTV.
A market whose realised utilisation swings wildly is flagged `vol_trust=low` rather than
silently simulated with a single scalar.

Run:  python3 stress_forward.py                 writes stress_forward.json
      python3 stress_forward.py --selftest      hand-checked cases
      python3 stress_forward.py --paths 20000   more paths, tighter estimate
"""
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

HORIZONS = [1, 7, 30]          # days
DEFAULT_PATHS = 10000
SEED = 20261008                # fixed so a rerun reproduces the same numbers


def _norm_cdf(z):
    """Standard normal CDF via erfc -- no scipy dependency, which this project does not have."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def breach_prob_closed_form(margin, daily_vol, horizon_days):
    """Analytic probability the price breaches the liquidation margin within `horizon_days`.

    A lognormal price with daily vol s over h days has log-return sd = s*sqrt(h).
        price falls to exp(-sd*z) for z ~ N(0,1)
        breach when   1 - exp(-sd*z) >= margin
                  =>  exp(-sd*z)   <= 1 - margin
                  =>  z            >= -ln(1 - margin) / sd

    So the probability is  1 - Phi( -ln(1-margin) / (s*sqrt(h)) ).

    THE NUMERATOR IS -ln(1-margin), NOT margin. Those coincide only for small margins. An
    earlier version of this function used `margin` directly, which is a first-order
    approximation that overstates badly at large margins: at margin 0.50 with vol 0.25 over
    one day it returned 0.0228 against a 200,000-path simulation of 0.0030 -- a 7x error,
    and in the direction that makes a SAFE market look risky. The approximation was found by
    a discriminating test case; the three original cases all sat near zero where both forms
    agree, so they passed trivially and proved nothing.

    This is the terminal-value probability, NOT the first-passage probability. A path can
    breach and recover within the window, which terminal value misses. The Monte Carlo
    below uses the same terminal definition and therefore agrees with it by construction --
    which is a correctness check on the simulator, not independent evidence about markets.
    """
    if not daily_vol or daily_vol <= 0 or margin is None or margin <= 0:
        return None
    if horizon_days <= 0 or margin >= 1:
        return None
    sd = daily_vol * math.sqrt(horizon_days)
    return 1.0 - _norm_cdf(-math.log(1.0 - margin) / sd)


def simulate(margin, daily_vol, horizon_days, paths=DEFAULT_PATHS, rng=None):
    """Monte Carlo breach probability over independent lognormal price paths.

    Returns (probability, paths_used). Probability is None when the inputs cannot support a
    simulation -- e.g. a position already past its margin, which has probability 1 and should
    be reported as such rather than simulated.
    """
    if margin is None:
        return None, 0
    if margin <= 0:
        return 1.0, 0            # already breached; no simulation needed
    if not daily_vol or daily_vol <= 0 or horizon_days <= 0:
        return None, 0
    r = rng or random.Random(SEED)
    sd = daily_vol * math.sqrt(horizon_days)
    log_threshold = math.log(1.0 / (1.0 - margin)) if margin < 1 else float("inf")
    # margin is stored as a fraction of the collateral price that can be lost.
    thresh = margin                      # fall in terms of fraction of price
    hits = 0
    for _ in range(paths):
        # terminal log-return; we only need the endpoint for the terminal definition
        z = r.gauss(0.0, 1.0)
        fall_frac = 1.0 - math.exp(-sd * z)
        if fall_frac >= thresh:
            hits += 1
    return hits / float(paths), paths


def calibration(series, lltv):
    """How much can a single scalar volatility be trusted for this market?

    Reads the 99-run ledger for the market and reports:
      util_swing   the interquartile range of utilisation across runs
      already_breached  how many stored runs were ALREADY past LLTV
    A market whose utilisation never moves is one a scalar can describe; one that swings is
    flagged so a reader knows the simulation is smoothing over real variation.
    """
    utils = [r.get("utilization") for r in series if r.get("utilization") is not None]
    out = {"runs": len(series), "util_n": len(utils)}
    if len(utils) >= 4:
        q = sorted(utils)
        out["util_p25"] = q[len(q) // 4]
        out["util_p75"] = q[3 * len(q) // 4]
        out["util_swing"] = out["util_p75"] - out["util_p25"]
    else:
        out["util_swing"] = None
    # a market that has ALREADY breached is not a simulation question
    out["already_breached"] = sum(1 for r in series if r.get("verdict") == "AVOID")
    if out["util_swing"] is None:
        out["vol_trust"] = "unknown"
    elif out["util_swing"] < 0.02:
        out["vol_trust"] = "high"     # steady market, a scalar describes it
    elif out["util_swing"] < 0.10:
        out["vol_trust"] = "medium"
    else:
        out["vol_trust"] = "low"      # swings a lot; the scalar smooths over real variation
    return out


def project_market(market, series, horizons=HORIZONS, paths=DEFAULT_PATHS, rng=None,
                   price_pts=None):
    """Full forward projection for one Morpho market."""
    coll = market.get("collateral_usd")
    debt = market.get("borrow_usd")
    lltv = market.get("lltv")
    # USE THE CADENCE-CORRECTED SIGMA. The `daily_vol_pct` field stored in the run ledger was
    # annualised with sqrt(365) regardless of the feed's actual sampling, which inflates weekly
    # feeds by sqrt(7)=2.646x. `add_volatility` now corrects this given the raw price series; the
    # series is re-read here so the projection does not inherit the inflated figure. See
    # test_vol_cadence.py. Where the series is unavailable the stored value is used AND FLAGGED,
    # because an uncorrected weekly feed would overstate breach risk by roughly 2.6x.
    vol_pct = market.get("daily_vol_pct")
    vol_source = "stored (cadence uncorrected)"
    _pts = (price_pts or {}).get(market.get("market_id")) if price_pts else None
    if _pts:
        try:
            import lending_screen as _ls
            _fixed = _ls.add_volatility(market, _pts)
            if _fixed.get("daily_vol_pct"):
                vol_pct = _fixed["daily_vol_pct"]
                vol_source = "recomputed (cadence %.1fd)" % (_fixed.get("vol_sample_days") or 0)
        except Exception:
            pass

    out = {
        "market_id": market.get("market_id"),
        "collateral": market.get("collateral"),
        "loan": market.get("loan"),
        "lltv": lltv,
        "daily_vol_pct": vol_pct,
        "vol_source": vol_source,
        "collateral_usd": coll,
        "borrow_usd": debt,
        "liquidity_usd": market.get("liquidity_usd"),
        "horizons": {},
    }
    if not (coll and debt and lltv and vol_pct):
        out["reason"] = "insufficient state to simulate"
        return out

    ltv = debt / coll
    out["ltv"] = ltv
    # Margin = the fraction the collateral price may fall before LTV reaches LLTV.
    # LTV' = debt / (coll * (1-f)) must stay <= LLTV  =>  1-f >= LTV/LLTV  =>  f <= 1 - LTV/LLTV
    margin = 1.0 - (ltv / lltv) if lltv else None
    out["margin"] = margin

    cal = calibration(series or [], lltv)
    out["calibration"] = cal

    if margin is None:
        out["reason"] = "no LLTV"
        return out
    if margin <= 0:
        out["reason"] = "already past LLTV: liquidation is not a probability, it is a state"
        for h in horizons:
            out["horizons"][str(h)] = {"breach_prob": 1.0, "closed_form": 1.0}
        return out

    dsig = vol_pct / 100.0
    for h in horizons:
        p, n = simulate(margin, dsig, h, paths=paths, rng=rng)
        out["horizons"][str(h)] = {
            "breach_prob": p,
            "closed_form": breach_prob_closed_form(margin, dsig, h),
            "paths": n,
        }
    return out


def _load(p):
    with open(p) as fh:
        return json.load(fh)


def main():
    if "--selftest" in sys.argv:
        return selftest()

    paths = DEFAULT_PATHS
    if "--paths" in sys.argv:
        paths = int(sys.argv[sys.argv.index("--paths") + 1])

    runs_dir = os.path.join(HERE, "runs")
    if not os.path.isdir(runs_dir):
        print("no runs ledger; nothing to project", file=sys.stderr)
        return 1

    run_names = sorted(os.listdir(runs_dir))
    newest = os.path.join(runs_dir, run_names[-1])
    markets = _load(os.path.join(newest, "markets.json"))
    markets = markets if isinstance(markets, list) else list(markets.values())

    try:
        sys.path.insert(0, HERE)
        import run_history as rh
        series_for = lambda mid: rh.get_series(mid)
    except Exception:
        series_for = lambda mid: []

    # Load the raw price series if the cache exists, so volatility is recomputed at the correct
    # cadence rather than read from the possibly-inflated stored field.
    phist = {}
    _cache = os.path.join(HERE, "price_cache.json")
    if os.path.exists(_cache):
        try:
            with open(_cache) as fh:
                phist = json.load(fh)
        except Exception:
            phist = {}

    projections = []
    for mk in markets:
        try:
            ser = series_for(mk.get("market_id"))
        except Exception:
            ser = []
        projections.append(project_market(mk, ser, paths=paths, price_pts=phist))

    ok = [p for p in projections if p.get("ltv") is not None and p.get("margin", 0) > 0]
    already = [p for p in projections if p.get("margin") is not None and p.get("margin") <= 0]
    unsim = [p for p in projections if p.get("ltv") is None]

    # the interesting set: not already dead, but with a material 30-day breach chance
    risky = sorted([p for p in ok if p["horizons"]["30"]["breach_prob"] >= 0.05],
                   key=lambda p: -p["horizons"]["30"]["breach_prob"])

    low_trust = [p for p in ok if p["calibration"].get("vol_trust") == "low"]

    out = {
        "run": run_names[-1],
        "paths": paths,
        "seed": SEED,
        "horizons_days": HORIZONS,
        "independent_markets": True,
        "limitations": [
            "Markets are simulated INDEPENDENTLY: no cross-market correlation, so cascade risk "
            "is understated.",
            "Debt is held constant: interest accrual is ignored, so breach is slightly "
            "understated.",
            "A breach is counted as a liquidation: no liquidator-profitability delay, so "
            "realised liquidations are an upper bound.",
            "Terminal-value breach only: a path that breaches and recovers mid-window is not "
            "counted, so the probability understates first-passage risk.",
            "Lognormal returns, from the market's own scalar daily volatility.",
        ],
        "counts": {
            "markets": len(projections),
            "simulated": len(ok),
            "already_past_lltv": len(already),
            "insufficient_state": len(unsim),
            "risky_5pct_or_more_30d": len(risky),
            "low_vol_trust": len(low_trust),
        },
        "risky": risky[:20],
        "all": projections,
    }
    with open(os.path.join(HERE, "stress_forward.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    c = out["counts"]
    print("market run                   %s" % run_names[-1])
    print("markets                      %d" % c["markets"])
    print("  simulated                  %d" % c["simulated"])
    print("  already past LLTV          %d" % c["already_past_lltv"])
    print("  insufficient state         %d" % c["insufficient_state"])
    print("  >=5%% 30-day breach chance  %d" % c["risky_5pct_or_more_30d"])
    print("  low volatility trust       %d" % c["low_vol_trust"])
    print()
    for p in risky[:6]:
        h = p["horizons"]
        print("  %-9s LTV %.3f / LLTV %.2f  margin %.1f%%  1d %.3f  7d %.3f  30d %.3f  vol_trust=%s"
              % (p.get("collateral"), p["ltv"], p["lltv"], 100 * p["margin"],
                 h["1"]["breach_prob"], h["7"]["breach_prob"], h["30"]["breach_prob"],
                 p["calibration"].get("vol_trust")))
    return 0


def selftest():
    """Hand-checked cases. If these fail, the projected probabilities are wrong."""
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print("  %-58s %s" % (name, "PASS" if cond else "FAIL " + str(detail)))
        if not cond:
            ok = False

    # a position already past LLTV: probability is 1, not a simulation
    p, n = simulate(-0.05, 0.05, 30)
    check("negative margin reports certainty, not a simulation", p == 1.0 and n == 0, (p, n))

    # zero volatility means the price cannot move, so it cannot breach
    p, n = simulate(0.2, 0.0, 30)
    check("zero volatility cannot breach", p is None, p)

    # no margin -> nothing to say
    p, n = simulate(None, 0.05, 30)
    check("no margin yields None", p is None, p)

    # a huge margin with tiny vol over one day should be near zero
    p, _ = simulate(0.5, 0.001, 1, paths=2000)
    check("huge margin, tiny vol, 1 day -> ~0", p < 0.01, p)

    # a tiny margin with large vol should be large
    p, _ = simulate(0.01, 0.10, 30, paths=4000)
    check("tiny margin, large vol, 30 days -> large", p > 0.10, p)

    # monotonic in horizon: more time, more chance
    a, _ = simulate(0.10, 0.03, 1, paths=4000)
    b, _ = simulate(0.10, 0.03, 7, paths=4000)
    c, _ = simulate(0.10, 0.03, 30, paths=4000)
    check("breach prob rises with horizon", a < b < c, (a, b, c))

    # monotonic in volume: more vol, more chance
    lo, _ = simulate(0.10, 0.01, 30, paths=4000)
    hi, _ = simulate(0.10, 0.05, 30, paths=4000)
    check("breach prob rises with volatility", lo < hi, (lo, hi))

    # the simulator must agree with the closed form it shares a definition with.
    # this is a correctness check on the code, NOT independent evidence about markets.
    # CHOOSE CASES THAT DISCRIMINATE. Probabilities near zero agree trivially, so the three
    # cases that originally sat here proved nothing. These sit in the middle of the curve.
    for margin, vol, h in [(0.50, 0.25, 1), (0.50, 0.20, 1), (0.30, 0.15, 1),
                           (0.10, 0.03, 7), (0.05, 0.04, 30)]:
        sim, _ = simulate(margin, vol, h, paths=60000)
        cf = breach_prob_closed_form(margin, vol, h)
        check("MC agrees with closed form (m=%.2f v=%.2f h=%d)" % (margin, vol, h),
              abs(sim - cf) < 0.02, "mc=%.4f cf=%.4f" % (sim, cf))

    # calibration flags a swinging market as low trust
    swing = [{"utilization": 0.1}, {"utilization": 0.9}, {"utilization": 0.2},
             {"utilization": 0.8}, {"utilization": 0.5}]
    cal = calibration(swing, 0.8)
    check("a swinging market is low vol_trust", cal["vol_trust"] == "low", cal)
    steady = [{"utilization": 0.90} for _ in range(6)]
    cal2 = calibration(steady, 0.8)
    check("a steady market is high vol_trust", cal2["vol_trust"] == "high", cal2)

    # a market with no usable state says so rather than simulating
    proj = project_market({"market_id": "0x0"}, [])
    check("unusable market is refused, not guessed",
          proj.get("reason") == "insufficient state to simulate", proj.get("reason"))

    # margin maths: LTV 0.80 with LLTV 0.80 leaves no room
    proj = project_market({"market_id": "0x1", "collateral_usd": 100.0, "borrow_usd": 80.0,
                           "lltv": 0.80, "daily_vol_pct": 5.0}, [])
    check("LTV == LLTV means zero margin", abs(proj["margin"]) < 1e-12, proj.get("margin"))

    # ... and LTV 0.40 with LLTV 0.80 leaves exactly half
    proj = project_market({"market_id": "0x2", "collateral_usd": 100.0, "borrow_usd": 40.0,
                           "lltv": 0.80, "daily_vol_pct": 5.0}, [])
    check("LTV 0.40 / LLTV 0.80 gives margin 0.50", abs(proj["margin"] - 0.50) < 1e-12,
          proj.get("margin"))
    check("and a 1-day breach chance near zero for that headroom",
          proj["horizons"]["1"]["breach_prob"] < 1e-9, proj["horizons"]["1"])

    # reproducibility: same seed, same numbers
    r1 = project_market({"market_id": "0x3", "collateral_usd": 100.0, "borrow_usd": 70.0,
                         "lltv": 0.80, "daily_vol_pct": 6.0}, [],
                        paths=2000, rng=random.Random(SEED))
    r2 = project_market({"market_id": "0x3", "collateral_usd": 100.0, "borrow_usd": 70.0,
                         "lltv": 0.80, "daily_vol_pct": 6.0}, [],
                        paths=2000, rng=random.Random(SEED))
    check("same seed reproduces the same projection",
          r1["horizons"]["30"]["breach_prob"] == r2["horizons"]["30"]["breach_prob"])

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

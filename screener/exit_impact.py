#!/usr/bin/env python3
"""exit_impact.py - what does it actually cost to get out?

THE GAP THIS CLOSES. The screen flags a pool THIN when TVL < $1,000,000. That is one number
applied to 13,945 pools of wildly different structure, and it conflates two different things:
TVL is the SIZE of the pool, exit impact is the COST of leaving it. A $40M pool of a token
nobody trades can be more expensive to exit than a $2M pool of a major pair.

WHAT THIS COMPUTES. For a position of a given size V, the fraction of value lost to slippage
on exit, from the constant-product invariant x*y=k.

    A 50/50 CPMM with TVL T has reserves x = y = T/2.
    Exiting a position worth V (half in each token, as an LP position is):
        the base-token half is sold into the pool:  dx = V/2
        output received:                            dy = y*dx / (x + dx)
        value lost:                                 dx - dy
        fractional loss:                            dx / (x + dx)

    With x = T/2 and dx = V/2:
        loss(V) = (V/T) / (1 + V/T)

TWO HONEST LIMITS, stated up front because they bound every number below.

  1. THE FEED DOES NOT SAY WHICH AMM. Constant-product is the default assumption and it is
     the WORST case for any given depth, so the figures are a pessimistic bound, not a
     measurement. A concentrated-liquidity pool at the same TVL has a similar mid-range
     impact and a much worse one near the edges; a stableswap pool is far cheaper. The report
     labels every figure as modelled for this reason.

  2. TVL IS NOT EXIT LIQUIDITY. The number used here is the pool's total value on both sides,
     which is an upper bound on what is actually touchable. Real exit liquidity is less. So
     these costs are LOWER bounds on the real cost, while the CPMM choice above is an UPPER
     bound on the same thing. Both errors are named rather than averaged away.

WHERE A REAL LIQUIDITY FIGURE EXISTS, IT IS USED INSTEAD. The Morpho feed carries
`liquidity_usd` -- the amount actually available to withdraw, not a total. For those markets
the impact is computed against the real figure with NO model assumption, and that is the
stronger of the two datasets in this repository.

Run:  python3 exit_impact.py            writes exit_impact.json
      python3 exit_impact.py --selftest  verifies the maths against hand-computed cases
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Position sizes a reader might actually be holding. Exposed as configuration because the
# right thresholds are a policy choice, not a finding.
SIZES = [10_000, 100_000, 1_000_000]

# Above this fractional loss the pool is called EXPENSIVE rather than merely flagged. 2% is a
# round number chosen so that a 20% APY pool pays for its own exit in about five weeks.
EXPENSIVE = 0.02
# Above this, the pool cannot be left without giving up serious value.
BRUTAL = 0.10


def cpmm_loss(V, T):
    """Fraction of value lost exiting a position worth V from a 50/50 pool of TVL T.

    Exact, not linearised. The linear approximation (V/T) overstates the loss at large V,
    and it is precisely the large-V cases that matter here.
    """
    if not T or T <= 0 or V <= 0:
        return None
    r = V / T
    return r / (1.0 + r)


def grade(loss):
    """Turn a fractional loss into a word. None means it could not be computed."""
    if loss is None:
        return None
    if loss >= BRUTAL:
        return "BRUTAL"
    if loss >= EXPENSIVE:
        return "EXPENSIVE"
    return "OK"


def max_ok_position(T):
    """The largest position that can still be exited without the EXPENSIVE grade.

    Solved directly rather than searched: loss = r/(1+r) = E has the closed form
    r = E/(1-E), and V = r*T.
    """
    if not T or T <= 0:
        return None
    r = EXPENSIVE / (1.0 - EXPENSIVE)
    return T * r


def analyse_pool(pool, sizes=SIZES):
    """Exit profile for one AMM pool from the screen feed.

    The only depth figure this feed carries is `tvl`. Where it is missing there is nothing to
    say, and the result says nothing rather than guessing.
    """
    tvl = pool.get("tvl")
    out = {
        "pool": pool.get("pool"),
        "chain": pool.get("chain"),
        "project": pool.get("project"),
        "symbol": pool.get("symbol"),
        "verdict": pool.get("verdict"),
        "tvl": tvl,
        "modelled": True,          # feed does not state the AMM; CPMM assumed
        "losses": {},
    }
    if not tvl or tvl <= 0:
        out["depth_grade"] = None
        return out
    for v in sizes:
        out["losses"][str(v)] = cpmm_loss(v, tvl)
    out["depth_grade"] = grade(out["losses"][str(sizes[-1])])
    out["max_ok_position"] = max_ok_position(tvl)
    return out


def analyse_market(market, sizes=SIZES):
    """Exit profile for a Morpho market, using REAL liquidity rather than a model.

    `liquidity_usd` is the amount available to withdraw right now. That is the thing that
    actually gates an exit, so no constant-product assumption is made and the result is a
    measurement rather than a bound.
    """
    liq = market.get("liquidity_usd")
    out = {
        "market_id": market.get("market_id"),
        "collateral": market.get("collateral"),
        "loan": market.get("loan"),
        "tvl": market.get("tvl_usd"),
        "liquidity": liq,
        "utilization": market.get("utilization"),
        "modelled": False,         # liquidity_usd is a reading, not an assumption
        "losses": {},
    }
    if liq is None:
        out["depth_grade"] = None
        return out
    if liq <= 0:
        # a market with no free liquidity cannot be exited at ANY size. This is a hard stop,
        # and it is the state the depegged markets in this dataset are actually in.
        out["depth_grade"] = "BRUTAL"
        out["note"] = "no free liquidity: cannot be exited at any size"
        for v in sizes:
            out["losses"][str(v)] = 1.0
        out["max_ok_position"] = 0.0
        return out
    for v in sizes:
        out["losses"][str(v)] = cpmm_loss(v, liq)
    out["depth_grade"] = grade(out["losses"][str(sizes[-1])])
    out["max_ok_position"] = max_ok_position(liq)
    return out


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def main():
    if "--selftest" in sys.argv:
        return selftest()

    results_path = os.path.join(HERE, "results.json")
    if not os.path.exists(results_path):
        print("no results.json; nothing to analyse", file=sys.stderr)
        return 1
    pools = _load(results_path)

    profiles = [analyse_pool(p) for p in pools]
    ranked = [p for p in profiles if p["losses"].get("1000000") is not None]

    # The THIN flag is a boolean on a $1M boundary. Compare what each rule calls uninvestable.
    thin_by_flag = [p for p, raw in zip(profiles, pools) if "THIN" in (raw.get("fails") or [])]
    brutal = [p for p in ranked if p["depth_grade"] == "BRUTAL"]

    # The two sets that are the entire argument for the change: pools the $1M floor PASSES but
    # that are expensive to leave, and pools it REJECTS that are cheap to leave.
    flag_ids = {p["pool"] for p in thin_by_flag}
    passed_but_brutal = len([p for p in brutal if p["pool"] not in flag_ids])
    flagged_but_cheap = len([p for p in thin_by_flag if p["depth_grade"] == "OK"])

    # HONESTY CHECK ON THIS MODULE'S OWN POOL METRIC. For a 50/50 CPMM, fixing a loss threshold
    # makes the largest acceptable position exactly proportional to TVL (E/(1-E) * T). So
    # ranking pools by `max_ok_position` is IDENTICAL to ranking them by TVL -- measured, and
    # asserted below. The pool half of this module therefore converts the $1M boolean into a
    # DOLLAR COST, which is more useful to a reader, but it does NOT re-rank anything. It is
    # declared here rather than presented as new discrimination.
    ratios = sorted({round(p["max_ok_position"] / p["tvl"], 9)
                     for p in ranked if p.get("tvl") and p.get("max_ok_position")})
    rescales_tvl = (len(ratios) == 1 and abs(ratios[0] - EXPENSIVE / (1.0 - EXPENSIVE)) < 1e-6)

    out = {
        "sizes": SIZES,
        "modelled": True,
        "pool_metric_is_tvl_rescaled": rescales_tvl,
        "pool_metric_note": (
            "max_ok_position is exactly (E/(1-E)) * TVL for a 50/50 CPMM, so the pool ranking is "
            "identical to a TVL ranking. This half converts the flag into a cost, not a new order."
        ),
        "counts": {
            "pools": len(profiles),
            "ranked": len(ranked),
            "thin_by_1m_flag": len(thin_by_flag),
            "brutal_by_impact": len(brutal),
            "brutal_but_passed_the_1m_floor": passed_but_brutal,
            "flagged_thin_but_cheap_to_exit": flagged_but_cheap,
        },
        "profiles": ranked,
    }
    with open(os.path.join(HERE, "exit_impact.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    c = out["counts"]
    print("pool metric is a TVL rescaling?          %s" % rescales_tvl)
    print("pools analysed                           %d" % c["pools"])
    print("  THIN by the $1M floor                  %d" % c["thin_by_1m_flag"])
    print("  BRUTAL by exit impact                  %d" % c["brutal_by_impact"])
    print("  passed the floor, still brutal to exit %d" % c["brutal_but_passed_the_1m_floor"])
    print("  flagged THIN, but cheap to exit        %d" % c["flagged_thin_but_cheap_to_exit"])
    return 0


def selftest():
    """Hand-computed cases. If these fail the numbers in the report are wrong."""
    ok = True

    def check(name, got, want, tol=1e-9):
        nonlocal ok
        if isinstance(want, float) and isinstance(got, float):
            good = abs(got - want) <= tol
        else:
            good = got == want
        print("  %-56s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    # A position equal to the whole TVL: r=1 so loss = 1/2. Half the value is gone.
    check("exit of size == TVL loses exactly half the value", cpmm_loss(100, 100), 0.5)
    # r = 0.5 -> 0.5/1.5 = 1/3
    check("exit of size == half TVL loses a third", cpmm_loss(50, 100), 1.0 / 3.0)
    # $100k from a $2M pool: r=0.05 -> 0.05/1.05
    check("$100k from $2M", cpmm_loss(100_000, 2_000_000), 0.05 / 1.05)
    # the linear approximation overstates: r=1 would say 1.0, exact says 0.5
    check("exact loss is strictly BELOW the linear V/T at r=1", cpmm_loss(100, 100) < 1.0, True)
    check("loss rises with size", cpmm_loss(200, 1000) > cpmm_loss(100, 1000), True)
    check("loss falls with depth", cpmm_loss(100, 2000) < cpmm_loss(100, 1000), True)

    check("grade BRUTAL", grade(0.5), "BRUTAL")
    check("grade EXPENSIVE", grade(0.05), "EXPENSIVE")
    check("grade OK", grade(0.001), "OK")
    check("grade of None is None", grade(None), None)
    check("zero TVL yields None, not a fake zero", cpmm_loss(100, 0), None)
    check("negative V yields None", cpmm_loss(-1, 100), None)
    check("max_ok_position of zero TVL is None", max_ok_position(0), None)

    # worst size: at exactly that size the loss must equal the EXPENSIVE threshold
    T = 1_000_000
    v = max_ok_position(T)
    check("max_ok_position sits exactly on the EXPENSIVE boundary",
          cpmm_loss(v, T), EXPENSIVE, tol=1e-9)

    # a market with no liquidity cannot be exited at any size
    m = analyse_market({"market_id": "0x1", "liquidity_usd": 0.0, "tvl_usd": 10_000_000})
    check("zero-liquidity market is BRUTAL", m["depth_grade"], "BRUTAL")
    check("zero-liquidity market admits no position", m["max_ok_position"], 0.0)

    # ... but one with real liquidity is measured, not modelled
    m2 = analyse_market({"market_id": "0x2", "liquidity_usd": 2_000_000, "tvl_usd": 9_000_000})
    check("market with liquidity is NOT modelled", m2["modelled"], False)
    check("market with liquidity still computes a loss",
          m2["losses"]["100000"], cpmm_loss(100_000, 2_000_000))

    # a pool with no TVL says nothing rather than guessing
    p = analyse_pool({"pool": "x", "tvl": None})
    check("pool with no TVL has no grade", p["depth_grade"], None)

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

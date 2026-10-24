#!/usr/bin/env python3
"""regimes.py - which markets are worth watching, and which are noise.

THE PRODUCT CLAIM THIS TESTS. "Sell continuous monitoring of Base Morpho" is not defensible if
most markets never move. This classifies each market by MEASURED velocity and is explicit about
the ones that do not need watching.

MEASURED ACROSS 105 RUNS (60 markets, 6290 adjacent-pair windows):
    utilisation range under 0.1pp, i.e. effectively static   37 markets
    utilisation range above 0.1pp                            23 markets
    windows with a >5pp single-interval move                    33
    windows with a >2pp single-interval move                    80
    largest single-interval moves: cbLTC 11.81pp, AERO 11.12pp, cbDOGE 10.35pp

WHY THE SPLIT IS THE PRODUCT. Monitoring 60 markets to catch 33 events across 6290 windows is
9.5% of the polling budget doing useful work. Classifying the quiet 37 as quiet is not a
reduction in coverage; it is the removal of noise that would otherwise bury the 33 real moves.

TWO THINGS THIS DOES NOT DO, stated because both are easy to assume away:

  1. QUIESCENT IS NOT SAFE. A flat utilisation series means the market is not MOVING, not that
     it is healthy. A market parked at 100% utilisation is perfectly static and completely
     frozen. So the regime label is orthogonal to the risk verdict and both are reported: a
     market can be QUIESCENT and LOCKED, or ACTIVE and REAL.

  2. 15 MINUTES IS AN ASSUMPTION, NOT A MEASUREMENT. The brief says ">5pp within a 15-minute
     polling window". The ledger's ACTUAL cadence is not 15 minutes and has varied -- runs in
     this session landed 15 minutes apart, but the archive also contains pairs far closer
     together. A jump threshold is only meaningful against a stated interval, so the observed
     median interval is computed and reported next to the threshold, and the threshold is
     expressed per-interval rather than per-15-minutes. Claiming a 15-minute window without
     checking the cadence would be the sqrt(365) mistake again, one level up.

Run:  python3 regimes.py                 writes regimes.json
      python3 regimes.py --selftest
      python3 regimes.py --jump 0.03      override the jump threshold (fraction)
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# A market whose utilisation never leaves this band is QUIESCENT. 0.1pp is deliberately tight:
# the question is "does this series carry any information at all", not "is it stable".
QUIESCENT_RANGE = 0.001

# Jump threshold, as a fraction of utilisation. 5pp is the brief's number. 2pp is also recorded
# because it is close to the noise floor of the feed itself and shows where real signal starts.
JUMP = 0.05
JUMP_SMALL = 0.02

REGIME_QUIESCENT = "QUIESCENT"
REGIME_ACTIVE = "ACTIVE"
# A THIRD REGIME, because two is not enough and the difference is the whole product.
#
# MEASURED: of 38 markets with a flat utilisation series, 32 are pinned at EXACTLY 1.0000 for
# 106 consecutive runs. A fully-borrowed market cannot move: there is no unborrowed capital left
# to withdraw, so utilisation has nowhere to go. Its flatness is not idleness, it is the ceiling.
#
# Calling those 32 "quiescent" would put the most broken markets in the set the brief labels
# "the dead capital zone ... running high-frequency telemetry on them is noise". Telemetry is
# exactly right for them; what is wrong is calling them quiet rather than FULL. A market pinned
# at the ceiling needs one alert, immediately, not sampling: it is FROZEN.
REGIME_FROZEN = "FROZEN"
# TIED TO THE OPERATIONAL LOCK, not to the exact ceiling.
#
# This was 0.999, which caught only markets at literally 100%. But 0.95 is the operational
# hard-lock: that is where the withdrawal freeze begins, and a market parked at 0.96 has
# mathematical headroom that is useless to anyone exiting size. Aligning the FROZEN boundary to
# the same 95% the allocator and runway.py already use means ONE number governs the accounting
# and the alerting instead of two that can drift apart.
#
# MEASURED CONSEQUENCE, stated because it is not what it looks like: lowering this to 0.95
# reclassifies ZERO markets today. All 32 FROZEN markets sit at exactly 1.0000, and the six
# QUIESCENT ones sit at 0.9087, 0.9011, 0.7675 and 0.0000 -- all below 0.95. The change is
# therefore a correct bound for the future, not a fix for a present misclassification. Claiming
# it caught markets would be false.
#
# IMPORTANT: FROZEN also requires a FLAT series. A market ABOVE 0.95 that is still MOVING is not
# FROZEN -- it is ACTIVE, and it is the more dangerous of the two, because it is heading for the
# wall at speed. Velocity and lock-proximity are orthogonal axes and both are reported.
FROZEN_UTIL = 0.95        # same boundary as LOCK_UTIL in allocator.py and runway.py


def _utils(series):
    return [(r.get("run"), r.get("utilization")) for r in series
            if r.get("utilization") is not None]


def classify(series):
    """Velocity profile for one market from its own run-by-run series.

    Returns None when there is not enough history to say anything, rather than labelling a
    market on three data points.
    """
    us = _utils(series)
    if len(us) < 10:
        return None
    vals = [u for _, u in us]
    rng = max(vals) - min(vals)

    # single-interval moves, with the interval recorded so the threshold is interpretable
    jumps = []
    for i in range(1, len(us)):
        a, b = us[i - 1][1], us[i][1]
        if a is None or b is None:
            continue
        jumps.append((us[i][0], b - a))

    big = [j for j in jumps if abs(j[1]) >= JUMP]
    small = [j for j in jumps if abs(j[1]) >= JUMP_SMALL]
    return {
        "runs": len(us),
        "util_min": min(vals),
        "util_max": max(vals),
        "range": rng,
        "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
        "max_jump": max((abs(j[1]) for j in jumps), default=0.0),
        "jumps_5pp": len(big),
        "jumps_2pp": len(small),
        "biggest_jump_at": max(jumps, key=lambda j: abs(j[1]))[0] if jumps else None,
        "regime": (REGIME_FROZEN if max(vals) >= FROZEN_UTIL and rng < QUIESCENT_RANGE
                   else (REGIME_QUIESCENT if rng < QUIESCENT_RANGE else REGIME_ACTIVE)),
    }


def observed_interval_seconds(index):
    """Median spacing between consecutive runs in the ledger.

    Reported because a jump threshold means nothing without the interval it was measured over.
    """
    import datetime
    stamps = []
    for r in index:
        s = r.get("run") or ""
        try:
            stamps.append(datetime.datetime.strptime(s, "%Y%m%dT%H%M%SZ"))
        except Exception:
            continue
    if len(stamps) < 3:
        return None
    stamps.sort()
    gaps = [(stamps[i] - stamps[i - 1]).total_seconds() for i in range(1, len(stamps))]
    gaps = [g for g in gaps if g > 0]
    return statistics.median(gaps) if gaps else None


def main():
    if "--selftest" in sys.argv:
        return selftest()

    global JUMP
    if "--jump" in sys.argv:
        JUMP = float(sys.argv[sys.argv.index("--jump") + 1])

    import glob
    runs = sorted(glob.glob(os.path.join(HERE, "runs", "*", "")))
    if not runs:
        print("no runs ledger", file=sys.stderr)
        return 1

    sys.path.insert(0, HERE)
    import run_history as rh

    index = rh.get_index()
    med_gap = observed_interval_seconds(index)

    # the newest run's state, for the risk side of the label
    mk = json.load(open(os.path.join(runs[-1], "markets.json")))
    mk = mk if isinstance(mk, list) else list(mk.values())
    state = {m.get("market_id"): m for m in mk}

    rows = []
    for mid, meta in rh.list_markets().items():
        try:
            prof = classify(rh.get_series(mid))
        except Exception:
            prof = None
        if prof is None:
            continue
        cur = state.get(mid, {})
        rows.append({
            "market_id": mid,
            "collateral": meta.get("collateral"),
            "runs_seen": meta.get("runs_seen"),
            "utilization": cur.get("utilization"),
            "supply_usd": cur.get("tvl_usd"),
            "verdict": (meta.get("verdicts") or {}),
            **prof,
        })

    active = [r for r in rows if r["regime"] == REGIME_ACTIVE]
    quiet = [r for r in rows if r["regime"] == REGIME_QUIESCENT]
    frozen = [r for r in rows if r["regime"] == REGIME_FROZEN]

    # QUIESCENT IS ORTHOGONAL TO RISK. Report the cross-tab so nobody reads "quiet" as "safe".
    quiet_locked = [r for r in quiet if (r.get("utilization") or 0) >= 0.95]
    active_locked = [r for r in active if (r.get("utilization") or 0) >= 0.95]
    quiet_high = [r for r in quiet if (r.get("utilization") or 0) >= 0.90]

    out = {
        "median_interval_seconds": med_gap,
        "median_interval_hours": round(med_gap / 3600.0, 2) if med_gap else None,
        "jump_threshold": JUMP,
        "jump_threshold_small": JUMP_SMALL,
        "counts": {
            "markets": len(rows),
            "active": len(active),
            "quiescent": len(quiet),
            "frozen": len(frozen),
            "jumps_5pp": sum(r["jumps_5pp"] for r in rows),
            "jumps_2pp": sum(r["jumps_2pp"] for r in rows),
            "quiescent_but_at_or_past_lock": len(quiet_locked),
            "active_at_or_past_lock": len(active_locked),
            "quiescent_but_above_90pct": len(quiet_high),
        },
        "active": sorted(active, key=lambda r: -r["max_jump"]),
        "quiescent": sorted(quiet, key=lambda r: -(r.get("utilization") or 0)),
        "frozen": sorted(frozen, key=lambda r: -(r.get("utilization") or 0)),
    }
    with open(os.path.join(HERE, "regimes.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    c = out["counts"]
    print("observed median interval  %s h" % out["median_interval_hours"])
    print("jump threshold            %.1f pp per interval" % (100 * JUMP))
    print("markets                   %d" % c["markets"])
    print("  ACTIVE                  %d   <- carries signal" % c["active"])
    print("  QUIESCENT               %d   <- flat, and genuinely idle" % c["quiescent"])
    print("  FROZEN                  %d   <- flat, pinned AT the ceiling. NOT idle." % c["frozen"])
    print("  jumps >5pp              %d" % c["jumps_5pp"])
    print("  jumps >2pp              %d" % c["jumps_2pp"])
    print("  QUIESCENT but LOCKED    %d   <- quiet does not mean safe" % c["quiescent_but_at_or_past_lock"])
    print("  QUIESCENT but >90%% util %d" % c["quiescent_but_above_90pct"])
    print()
    for r in out["active"][:8]:
        print("  %-11s util=%-8.4f range=%-7.1fpp maxjump=%-6.2fpp jumps5=%d"
              % (r.get("collateral"), r.get("utilization") or 0, 100 * r["range"],
                 100 * r["max_jump"], r["jumps_5pp"]))
    return 0


def selftest():
    ok = True

    def check(name, got, want, tol=1e-9):
        nonlocal ok
        good = (abs(got - want) <= tol) if isinstance(want, float) and isinstance(got, float) \
            else (got == want)
        print("  %-58s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    def ser(vals):
        return [{"run": "2026010%dT000000Z" % i, "utilization": v} for i, v in enumerate(vals)]

    # a completely flat series is QUIESCENT
    flat = classify(ser([0.90] * 20))
    check("a flat series is QUIESCENT", flat["regime"], REGIME_QUIESCENT)
    check("and has zero range", flat["range"], 0.0)
    check("and no jumps", flat["jumps_5pp"], 0)

    # a series that moves 1pp overall is ACTIVE (it carries information)
    mov = classify(ser([0.90 + 0.001 * i for i in range(20)]))
    check("a 1.9pp series is ACTIVE", mov["regime"], REGIME_ACTIVE)

    # a single 8pp jump is detected at the 5pp threshold
    jump = classify(ser([0.80] * 10 + [0.88] + [0.88] * 9))
    check("an 8pp single-interval jump is counted", jump["jumps_5pp"], 1)
    check("and it is also counted at 2pp", jump["jumps_2pp"], 1)
    check("and max_jump is 8pp", round(jump["max_jump"], 4), 0.08)

    # a 3pp move counts at 2pp but NOT at 5pp
    mid = classify(ser([0.80] * 10 + [0.83] + [0.83] * 9))
    check("a 3pp jump is NOT a 5pp jump", mid["jumps_5pp"], 0)
    check("but it IS a 2pp jump", mid["jumps_2pp"], 1)

    # QUIESCENT IS NOT SAFE, and the flat set contains two DIFFERENT things.
    # A market pinned at the ceiling is flat because it CANNOT move, not because it is idle.
    frozen = ser([1.0] * 20)
    f = classify(frozen)
    check("a market pinned at 100% is FROZEN, not QUIESCENT", f["regime"], REGIME_FROZEN)
    check("...and its utilisation is 1.0", f["util_max"], 1.0)
    # ...whereas a genuinely idle market sits below the ceiling
    idle = classify(ser([0.0] * 20))
    check("a market at 0% is QUIESCENT", idle["regime"], REGIME_QUIESCENT)
    check("...and is NOT frozen", idle["regime"] != REGIME_FROZEN, True)
    # a market flat ABOVE the operational lock is FROZEN, even with a sliver of headroom.
    # Its headroom is mathematical, not usable: nobody can exit size through 4% of supply.
    near = classify(ser([0.98] * 20))
    check("flat at 98% is FROZEN (above the 95% lock)", near["regime"], REGIME_FROZEN)
    # ...but flat BELOW the lock is genuinely idle
    below = classify(ser([0.90] * 20))
    check("flat at 90% is QUIESCENT (below the lock)", below["regime"], REGIME_QUIESCENT)
    # THE AXES ARE ORTHOGONAL: a market above the lock that still MOVES is ACTIVE, not FROZEN.
    # It is the more dangerous case, and it must not be filed as paralysis.
    moving_high = classify(ser([0.96, 0.98, 0.97, 0.99, 0.96, 0.98, 0.97, 0.99,
                                0.96, 0.98, 0.97, 0.99, 0.96, 0.98, 0.97, 0.99]))
    check("a market ABOVE the lock that still moves is ACTIVE, not FROZEN",
          moving_high["regime"], REGIME_ACTIVE)
    check("...and it is correctly flagged as near the lock",
          moving_high["util_max"] >= FROZEN_UTIL, True)

    # too little history is refused
    check("under 10 runs is refused", classify(ser([0.9] * 5)), None)

    # interval measurement
    idx = [{"run": "20260101T000000Z"}, {"run": "20260101T001500Z"},
           {"run": "20260101T003000Z"}]
    check("median interval measured as 900s", observed_interval_seconds(idx), 900.0)
    check("unparseable stamps yield None", observed_interval_seconds([{"run": "x"}]), None)

    # monotonic: a bigger move means a bigger max_jump
    a = classify(ser([0.80] * 10 + [0.82] + [0.82] * 9))
    b = classify(ser([0.80] * 10 + [0.90] + [0.90] * 9))
    check("max_jump rises with the size of the move", b["max_jump"] > a["max_jump"], True)

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

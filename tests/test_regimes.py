#!/usr/bin/env python3
"""Regime segmentation: which markets carry signal, and which are merely stuck.

WHY THIS SUITE EXISTS. The brief divides the book into "23 active" and "37 flat, where telemetry
is noise". Verified: 23 markets do carry signal (cbLTC 11.81pp in one interval). But the flat
group is NOT one population.

MEASURED: of 38 flat markets, 32 are pinned at EXACTLY 1.0000 utilisation for 106 consecutive
runs. A fully-borrowed market cannot move because no unborrowed capital remains -- its flatness
is the CEILING, not idleness. Classifying those as "dead capital, do not watch" puts the most
broken markets in the set the product tells you to ignore. They are FROZEN, and they need one
alert now, not sampling.

The suite also pins the interval honesty: a ">5pp in 15 minutes" claim is meaningless unless the
ledger's actual cadence is measured, and it is 0.25h here, not 0.25h by assumption.
"""
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
    print("=== 1. the classifier's own cases ===")
    rc = subprocess.call([sys.executable, os.path.join(SCREENER, "regimes.py"), "--selftest"])
    ck("regimes selftest passes", rc == 0)

    print("\n=== 2. the three regimes are distinct populations ===")
    import regimes as rg
    p = os.path.join(SCREENER, "regimes.json")
    if not os.path.exists(p):
        ck("regimes.json exists", False)
        return 1
    d = json.load(open(p))
    c = d["counts"]
    ck("an ACTIVE population exists (%d)" % c["active"], c["active"] > 0)
    ck("a FROZEN population exists (%d)" % c["frozen"], c["frozen"] > 0,
       "if zero, the FROZEN distinction has been lost")
    ck("every market is classified exactly once",
       c["active"] + c["quiescent"] + c["frozen"] == c["markets"],
       "%d+%d+%d != %d" % (c["active"], c["quiescent"], c["frozen"], c["markets"]))

    print("\n=== 3. FROZEN means pinned at the ceiling, not idle ===")
    for r in d["frozen"][:5]:
        ck("  %-10s is at the ceiling (util %.4f)"
           % (r.get("collateral"), r.get("utilization") or 0),
           (r.get("utilization") or 0) >= rg.FROZEN_UTIL)
    # and the reverse: nothing QUIESCENT sits at the ceiling
    bad = [r for r in d["quiescent"] if (r.get("utilization") or 0) >= rg.FROZEN_UTIL]
    ck("no QUIESCENT market is at the ceiling", len(bad) == 0,
       [r.get("collateral") for r in bad][:5])

    print("\n=== 4. a frozen market is FLAT, which is why range alone is not enough ===")
    for r in d["frozen"][:5]:
        ck("  %-10s has a flat series (range %.4fpp)"
           % (r.get("collateral"), 100 * r["range"]),
           r["range"] < rg.QUIESCENT_RANGE)

    print("\n=== 5. the interval is MEASURED, not assumed ===")
    ck("a median interval is reported", d.get("median_interval_seconds") is not None)
    ck("and it is stated in hours for the threshold to mean something",
       d.get("median_interval_hours") is not None, d.get("median_interval_hours"))
    print("      measured median interval: %s h (the brief assumed 0.25h)"
          % d.get("median_interval_hours"))

    print("\n=== 6. the >5pp claim is real, and countable ===")
    ck("jumps above 5pp exist (%d)" % c["jumps_5pp"], c["jumps_5pp"] > 0,
       "a threshold nobody crosses is a threshold doing nothing")
    ck("and more are visible at 2pp (%d)" % c["jumps_2pp"],
       c["jumps_2pp"] > c["jumps_5pp"])
    biggest = d["active"][0] if d["active"] else None
    if biggest:
        ck("the largest mover exceeds 5pp (%s, %.2fpp)"
           % (biggest.get("collateral"), 100 * biggest["max_jump"]),
           biggest["max_jump"] > 0.05)

    print("\n=== 7. ACTIVE markets are not all at the ceiling ===")
    # an active market near the lock is the dangerous case the product exists for
    near = [r for r in d["active"] if (r.get("utilization") or 0) >= 0.88]
    ck("some ACTIVE markets sit above 88%% utilisation (%d)" % len(near), len(near) > 0,
       "that combination -- moving AND near the lock -- is the whole product case")

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  regimes are separated, and the frozen set is not mistaken for idle")
    return 0


if __name__ == "__main__":
    sys.exit(main())

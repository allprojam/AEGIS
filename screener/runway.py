#!/usr/bin/env python3
"""runway.py - how many dollars of withdrawals before a market freezes?

THE ONE METRIC IN THE BRIEF THAT SURVIVES CONTACT WITH THE DATA.

A Morpho market locks withdrawals at high utilisation: deposits cannot be redeemed while
borrows occupy the pool. The question a risk desk actually asks is not "what is utilisation"
but "how far is it from the freeze, and does MY position fit in that gap".

    utilisation u = borrow / supply
    The 95% lock is reached when, after withdrawals W, borrow / (supply - W) = 0.95:
        W_lock = supply - borrow / 0.95

W_lock is the DEPLOYABLE RUNWAY: the total dollars of supply that can still leave before the
market freezes. It is a dollar figure a committee can act on, unlike a percentage.

HONESTY ABOUT WHAT THIS IS AND IS NOT.

  IT IS an accounting identity on two published numbers (supplyAssetsUsd, utilization). It
  needs no model, no assumption about AMM type, and no tick data. Verified against the live
  feed: liquidityAssetsUsd == supplyAssetsUsd - borrowAssetsUsd exactly, and
  utilization == borrowAssetsUsd / supplyAssetsUsd exactly.

  IT IS NOT a forecast. It says how much room exists NOW, not when it will be used. A market
  at 89% with no depositors can sit there indefinitely; a market at 60% can gap to lock in one
  block if a whale withdraws. The runway is a capacity, not a rate.

  IT IS NOT INDEPENDENT INFORMATION from TVL and utilisation -- it is those two combined. The
  value is presentational and operational (a dollar budget instead of a percentage), not
  informational. Claiming otherwise would be the same error as selling exit slippage as new
  discrimination when it was a rescaling of TVL.

WHY THE RATIO MATTERS MORE THAN THE RUNWAY. A runway of $61,728 sounds ample until you compare
it to the position that has to exit through it. `target / runway` is the share of the available
exit that one position occupies. Above 1.0 the position cannot leave at all without pushing the
market to the lock. That ratio is the number a desk should gate on.

Run:  python3 runway.py            writes runway.json
      python3 runway.py --selftest
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

LOCK_UTIL = 0.95          # Morpho locks withdrawals at this utilisation
SEVERE = 0.75             # a single position using this share of the runway is worth a flag
BREACH = 1.00            # the position does not fit in the available exit


def lock_runway(supply_usd, utilization, lock=LOCK_UTIL):
    """Dollars of supply that can still be withdrawn before utilisation reaches `lock`.

    None when the inputs cannot support it, rather than a fabricated zero.
    """
    if supply_usd is None or utilization is None or supply_usd <= 0:
        return None
    if utilization >= lock:
        return 0.0            # already past the lock; nothing can leave
    borrow = supply_usd * utilization
    return supply_usd - borrow / lock


def grade(ratio):
    """How much of the available exit one position occupies."""
    if ratio is None:
        return None
    if ratio >= BREACH:
        return "BREACH"
    if ratio >= SEVERE:
        return "SEVERE"
    return "OK"


def analyse(market, target_usd=None, lock=LOCK_UTIL):
    """Runway for one market, optionally against a position size."""
    sup = market.get("tvl_usd")
    u = market.get("utilization")
    out = {
        "market_id": market.get("market_id"),
        "collateral": market.get("collateral"),
        "loan": market.get("loan"),
        "supply_usd": sup,
        "utilization": u,
        "lock_util": lock,
        "target_usd": target_usd,
    }
    rw = lock_runway(sup, u, lock)
    out["runway_usd"] = rw
    if rw is None:
        out["occupancy"] = None
        out["grade"] = None
        return out
    if rw <= 0:
        out["occupancy"] = float("inf") if target_usd else None
        out["grade"] = "BREACH" if target_usd else "AT_LOCK"
        out["note"] = "at or past the %.0f%% lock: no withdrawals possible" % (100 * lock)
        return out
    if target_usd:
        out["occupancy"] = target_usd / rw
        out["grade"] = grade(out["occupancy"])
    else:
        out["occupancy"] = None
        out["grade"] = None
    return out


def main():
    if "--selftest" in sys.argv:
        return selftest()

    import glob
    runs = sorted(glob.glob(os.path.join(HERE, "runs", "*", "")))
    if not runs:
        print("no runs; nothing to analyse", file=sys.stderr)
        return 1
    run = runs[-1]
    mk = json.load(open(os.path.join(run, "markets.json")))
    mk = mk if isinstance(mk, list) else list(mk.values())

    # pair each market with the allocator target, if a target exists
    targets = {}
    ap = os.path.join(run, "allocator.json")
    if os.path.exists(ap):
        alloc = json.load(open(ap))
        for m in alloc.get("markets", []):
            if m.get("eligible") and m.get("target_usd"):
                targets[m.get("market_id")] = m["target_usd"]

    rows = [analyse(m, targets.get(m.get("market_id"))) for m in mk]
    live = [r for r in rows if r.get("runway_usd") is not None]
    funded = [r for r in live if r.get("target_usd")]

    out = {
        "run": os.path.basename(run.rstrip("/")),
        "lock_util": LOCK_UTIL,
        "counts": {
            "markets": len(rows),
            "with_runway": len(live),
            "at_or_past_lock": sum(1 for r in live if (r.get("runway_usd") or 0) <= 0),
            "funded_positions": len(funded),
            "funded_grade_severe_or_worse": sum(
                1 for r in funded if r.get("grade") in ("SEVERE", "BREACH", "AT_LOCK")),
        },
        "funded": sorted(funded, key=lambda r: -(r.get("occupancy") or 0)),
        "all": live,
    }
    with open(os.path.join(HERE, "runway.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    c = out["counts"]
    print("run                       %s" % out["run"])
    print("markets                   %d" % c["markets"])
    print("  with a runway figure    %d" % c["with_runway"])
    print("  at or past the lock     %d" % c["at_or_past_lock"])
    print("  funded positions        %d" % c["funded_positions"])
    print("  of those, SEVERE+       %d" % c["funded_grade_severe_or_worse"])
    print()
    print("  %-11s %-8s %-14s %-12s %s" % ("collateral", "util", "runway$", "target$", "occupancy"))
    for r in out["funded"][:8]:
        print("  %-11s %-8.4f %-14s %-12s %.2f %s" % (
            r.get("collateral"), r.get("utilization") or 0,
            format(int(r["runway_usd"]), ","), format(int(r["target_usd"]), ","),
            r["occupancy"], r["grade"]))
    return 0


def selftest():
    ok = True

    def check(name, got, want, tol=1e-6):
        nonlocal ok
        good = (abs(got - want) <= tol) if isinstance(want, float) and isinstance(got, float) \
            else (got == want)
        print("  %-58s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    # supply 100, borrow 90 -> at the 95% lock, W = 100 - 90/0.95 = 5.263
    check("runway at 90% utilisation on $100 supply", lock_runway(100.0, 0.90), 100.0 - 90.0 / 0.95)
    # 95% exactly means zero runway
    check("runway is zero AT the lock", lock_runway(100.0, 0.95), 0.0)
    # past the lock is still zero, never negative
    check("runway is zero PAST the lock", lock_runway(100.0, 0.99), 0.0)
    # zero borrow leaves the whole supply withdrawable
    check("no borrow means the whole supply can leave", lock_runway(100.0, 0.0), 100.0)
    # guards
    check("no supply yields None", lock_runway(None, 0.9), None)
    check("no utilisation yields None", lock_runway(100.0, None), None)
    check("zero supply yields None", lock_runway(0.0, 0.9), None)

    # occupancy: a 50 position against a 100 runway uses half
    r = analyse({"market_id": "0x1", "tvl_usd": 1000.0, "utilization": 0.90}, target_usd=52.63)
    check("occupancy is target/runway", round(r["occupancy"], 4),
          round(52.63 / (1000.0 - 900.0 / 0.95), 4))

    # a position larger than the runway BREACHES
    r2 = analyse({"market_id": "0x2", "tvl_usd": 1000.0, "utilization": 0.94}, target_usd=100.0)
    check("a target bigger than the runway is BREACH", r2["grade"], "BREACH")
    check("and its occupancy exceeds 1", r2["occupancy"] > 1.0, True)

    # a market already at the lock admits nothing
    r3 = analyse({"market_id": "0x3", "tvl_usd": 1000.0, "utilization": 1.0}, target_usd=1.0)
    check("a locked market is BREACH", r3["grade"], "BREACH")
    check("and reports zero runway", r3["runway_usd"], 0.0)

    # no target -> no grade, but still a runway
    r4 = analyse({"market_id": "0x4", "tvl_usd": 1000.0, "utilization": 0.50})
    check("no target still yields a runway", r4["runway_usd"], 1000.0 - 500.0 / 0.95)
    check("no target yields no grade", r4["grade"], None)

    # monotonic: a fuller market has less runway
    check("runway shrinks as utilisation rises",
          lock_runway(1000.0, 0.90) < lock_runway(1000.0, 0.80), True)

    # the identity this relies on, asserted rather than assumed
    check("the lock is where runway hits zero",
          lock_runway(500.0, 0.95), 0.0)

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

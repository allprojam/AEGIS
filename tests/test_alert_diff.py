#!/usr/bin/env python3
"""Tests for alert_diff.py - the State Transition Log.

These construct their own run pairs, so they are deterministic and do not depend on what is
on disk.

The important cases are the negative ones: an absent field must produce UNCHECKED, not
"no changes". An absent input is not evidence of stability, and a monitor that silently
reports green when it cannot see is worse than no monitor.

Run:  python3 tests/test_alert_diff.py
"""
import importlib.util, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("alert_diff_under_test", os.path.join(ROOT, "alert_diff.py"))
A = importlib.util.module_from_spec(_spec)
cwd = os.getcwd()
try:
    os.chdir(ROOT)
    _spec.loader.exec_module(A)
finally:
    os.chdir(cwd)

FAILS = []


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def mkrun(screen, markets=None, block=100):
    mk = markets if markets is not None else []
    if not mk and screen:
        mk = [{"market_id": s["market_id"], "_prov": {"block_number": block}} for s in screen]
    return {"dir": "x", "screen": screen, "markets": mk, "meta": {}}


def row(mid, verdict="REAL", util=0.5, coll="X", fails=None):
    return {"market_id": mid, "verdict": verdict, "utilization": util,
            "collateral": coll, "fails": fails or [], "reasons": []}


def kinds(events):
    return [e["kind"] for e in events]


def main():
    print("=== 1. verdict downgrade is caught, upgrades are not reported as downgrades ===")
    ev, _ = A.diff_runs(mkrun([row("m1", "REAL")]), mkrun([row("m1", "AVOID")]))
    check("REAL -> AVOID fires", "VERDICT_DOWNGRADE" in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1", "CAUTION")]), mkrun([row("m1", "AVOID")]))
    check("CAUTION -> AVOID fires", "VERDICT_DOWNGRADE" in kinds(ev))
    ev, _ = A.diff_runs(mkrun([row("m1", "AVOID")]), mkrun([row("m1", "REAL")]))
    check("AVOID -> REAL does NOT fire a downgrade", "VERDICT_DOWNGRADE" not in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1", "REAL")]), mkrun([row("m1", "MIXED")]))
    check("REAL -> MIXED does NOT fire (not into AVOID)", "VERDICT_DOWNGRADE" not in kinds(ev))

    print("\n=== 2. utilisation crossing and jumps ===")
    ev, _ = A.diff_runs(mkrun([row("m1", util=0.88)]), mkrun([row("m1", util=0.92)]))
    check("88% -> 92% fires UTIL_CROSSED_90", "UTIL_CROSSED_90" in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1", util=0.95)]), mkrun([row("m1", util=0.99)]))
    check("already >90%, no re-cross", "UTIL_CROSSED_90" not in kinds(ev))
    ev, _ = A.diff_runs(mkrun([row("m1", util=0.50)]), mkrun([row("m1", util=0.75)]))
    check("50% -> 75% fires UTIL_JUMP", "UTIL_JUMP" in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1", util=0.50)]), mkrun([row("m1", util=0.55)]))
    check("50% -> 55% (5pts) does NOT fire", "UTIL_JUMP" not in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1", util=0.92)]), mkrun([row("m1", util=0.85)]))
    check("a FALL crossing 90% does not fire a cross", "UTIL_CROSSED_90" not in kinds(ev), str(kinds(ev)))

    print("\n=== 3. oracle flip, and the UNCHECKED path when the field is absent ===")
    p = mkrun([row("m1")], markets=[{"market_id": "m1", "oracle_type": "ChainlinkOracleV2"}])
    c = mkrun([row("m1")], markets=[{"market_id": "m1", "oracle_type": "Unknown"}])
    ev, un = A.diff_runs(p, c)
    check("verified -> Unknown fires ORACLE_FLIP", "ORACLE_FLIP" in kinds(ev), str(kinds(ev)))
    check("no UNCHECKED when the field is present", not un, str(un))

    p2 = mkrun([row("m1")], markets=[{"market_id": "m1"}])           # NO oracle_type
    ev2, un2 = A.diff_runs(p2, c)
    check("absent oracle_type -> UNCHECKED, not silence",
          any(u["check"] == "ORACLE_FLIP" for u in un2), str(un2))
    check("absent field does NOT fabricate an ORACLE_FLIP event",
          "ORACLE_FLIP" not in kinds(ev2), str(kinds(ev2)))

    print("\n=== 4. contaminated interval (no block_number) is flagged ===")
    p3 = mkrun([row("m1")], markets=[{"market_id": "m1"}], block=None)
    c3 = mkrun([row("m1")], markets=[{"market_id": "m1"}], block=999)
    ev3, _ = A.diff_runs(p3, c3)
    check("missing block_number -> INTERVAL_UNRELIABLE",
          "INTERVAL_UNRELIABLE" in kinds(ev3), str(kinds(ev3)))
    ev4, _ = A.diff_runs(mkrun([row("m1")], block=1), mkrun([row("m1")], block=2))
    check("both blocks present -> no false INTERVAL_UNRELIABLE",
          "INTERVAL_UNRELIABLE" not in kinds(ev4))

    print("\n=== 4b. parameter changes on an immutable market id ===")
    pm_ = [{"market_id": "m1", "lltv": 0.77, "oracle": "0xAAA", "collateral": "X"}]
    cm_ = [{"market_id": "m1", "lltv": 0.915, "oracle": "0xAAA", "collateral": "X"}]
    ev, _ = A.diff_runs(mkrun([row("m1")], markets=pm_), mkrun([row("m1")], markets=cm_))
    check("LLTV change fires LLTV_CHANGED", "LLTV_CHANGED" in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1")], markets=pm_), mkrun([row("m1")], markets=pm_))
    check("unchanged LLTV does NOT fire", "LLTV_CHANGED" not in kinds(ev))
    cm2_ = [{"market_id": "m1", "lltv": 0.77, "oracle": "0xBBB", "collateral": "X"}]
    ev, _ = A.diff_runs(mkrun([row("m1")], markets=pm_), mkrun([row("m1")], markets=cm2_))
    check("oracle ADDRESS change fires ORACLE_ADDRESS_CHANGED",
          "ORACLE_ADDRESS_CHANGED" in kinds(ev), str(kinds(ev)))

    print("\n=== 5. markets appearing and disappearing ===")
    ev, _ = A.diff_runs(mkrun([row("m1"), row("m2")]), mkrun([row("m1")]))
    check("a market vanishing fires MARKET_GONE", "MARKET_GONE" in kinds(ev), str(kinds(ev)))
    ev, _ = A.diff_runs(mkrun([row("m1")]), mkrun([row("m1"), row("m2")]))
    check("a market appearing fires MARKET_NEW", "MARKET_NEW" in kinds(ev))

    print("\n=== 6. identical runs produce ZERO events (no noise) ===")
    same = [row("m1", "REAL", 0.5), row("m2", "AVOID", 0.99)]
    ev, un = A.diff_runs(mkrun(same), mkrun(same))
    check("identical runs -> 0 events", len(ev) == 0, str(kinds(ev)))

    print("\n=== 7. missing utilization does not crash or misfire ===")
    a = {"market_id": "m1", "verdict": "REAL", "utilization": None, "collateral": "X", "fails": []}
    b = {"market_id": "m1", "verdict": "REAL", "utilization": 0.95, "collateral": "X", "fails": []}
    try:
        ev, _ = A.diff_runs(mkrun([a]), mkrun([b]))
        check("None utilisation handled without crashing", True)
        check("None -> 0.95 does NOT fire a cross (no baseline)",
              "UTIL_CROSSED_90" not in kinds(ev), str(kinds(ev)))
    except Exception as e:
        check("None utilisation handled without crashing", False, "%s: %s" % (type(e).__name__, e))

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all alert_diff assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

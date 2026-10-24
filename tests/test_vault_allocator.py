#!/usr/bin/env python3
"""Adversarial tests for allocator.py.

The brief asked only for "assert no capital is allocated to a flagged market". That is the
filter restated -- it passes as long as `if flagged: 0` survives in the code, which is not a
test of anything. These are the tests that can actually fail.

Every case constructs its own inputs, so the suite is deterministic and does not touch the
network.

Run:  python3 tests/test_vault_allocator.py
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("allocator_under_test", os.path.join(ROOT, "allocator.py"))
A = importlib.util.module_from_spec(_spec)
cwd = os.getcwd()
try:
    os.chdir(ROOT)
    _spec.loader.exec_module(A)
finally:
    os.chdir(cwd)

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def mk(mid, tvl, borrow, lltv, coll="X", verdict="REAL", fails=None):
    return {"market_id": mid, "tvl_usd": tvl, "borrow_usd": borrow, "lltv": lltv,
            "collateral": coll, "verdict": verdict, "fails": fails or []}


def calm(n=60, price=100.0, drift=0.0005):
    """A LOW-volatility series, not a FLAT one.

    An earlier version of this fixture returned a constant price. That has ZERO standard
    deviation, and the allocator correctly rejects zero volatility as UNMEASURABLE
    (VOL_UNKNOWN) rather than treating it as safe. The fixture was wrong; the rule was right.
    A real asset has some variance, so the fixture must too.
    """
    out, p = [], price
    for i in range(n):
        p *= (1.0 + drift * (1 if i % 3 else -0.8))
        out.append({"x": 1700000000 + i * 86400, "y": round(p, 6)})
    return out


def run(markets, screen, otypes, phist, cap=1_000_000.0):
    return A.allocate(markets, screen, otypes, phist, capital_usd=cap)


def main():
    print("=== 1. the basic invariant: flagged markets get nothing ===")
    m = [mk("0x1", 50e6, 10e6, 0.625), mk("0x2", 50e6, 10e6, 0.625)]
    s = [{"market_id": "0x1", "verdict": "REAL", "fails": []},
         {"market_id": "0x2", "verdict": "AVOID", "fails": ["BAD_DEBT"]}]
    r = run(m, s, {"0x1": "ChainlinkOracleV2", "0x2": "ChainlinkOracleV2"},
            {"0x1": calm(), "0x2": calm()})
    t = {x["market_id"]: x["target_usd"] for x in r["markets"]}
    check("AVOID market receives 0", t["0x2"] == 0.0, "got %s" % t["0x2"])
    check("REAL market receives capital", t["0x1"] > 0, "got %s" % t["0x1"])

    print("\n=== 2. ALL markets flagged -> 100% unallocated, not an error ===")
    m = [mk("0x1", 50e6, 10e6, 0.625), mk("0x2", 50e6, 10e6, 0.625)]
    s = [{"market_id": "0x1", "verdict": "CAUTION", "fails": ["THIN"]},
         {"market_id": "0x2", "verdict": "AVOID", "fails": ["BAD_DEBT"]}]
    r = run(m, s, {"0x1": "ChainlinkOracleV2", "0x2": "ChainlinkOracleV2"},
            {"0x1": calm(), "0x2": calm()})
    check("nothing eligible", r["n_eligible"] == 0)
    check("allocated == 0", r["allocated_usd"] == 0.0)
    check("unallocated == 100%", abs(r["unallocated_pct"] - 100.0) < 1e-6)

    print("\n=== 3. borrow depth cap is never exceeded ===")
    m = [mk("0x1", 1e6, 10_000, 0.625), mk("0x2", 100e6, 50e6, 0.625)]
    s = [{"market_id": "0x1", "verdict": "REAL", "fails": []},
         {"market_id": "0x2", "verdict": "REAL", "fails": []}]
    r = run(m, s, {"0x1": "ChainlinkOracleV2", "0x2": "ChainlinkOracleV2"},
            {"0x1": calm(), "0x2": calm()})
    for x in r["markets"]:
        check("%s within its borrow-depth cap" % x["market_id"],
              x["target_usd"] <= x["capacity_usd"] + 0.01,
              "target %s > cap %s" % (x["target_usd"], x["capacity_usd"]))

    print("\n=== 4. unknown oracle -> rejected (fail closed) ===")
    m = [mk("0x1", 50e6, 10e6, 0.625)]
    s = [{"market_id": "0x1", "verdict": "REAL", "fails": []}]
    for otype, expect in (("ChainlinkOracleV2", True), ("ChainlinkOracle", True),
                           ("Unknown", False), ("CustomOracle", False), (None, False)):
        r = run(m, s, {"0x1": otype}, {"0x1": calm()})
        got = r["markets"][0]["eligible"]
        check("oracle %-18s -> eligible=%s" % (otype, expect), got == expect)

    print("\n=== 5. missing volatility data -> rejected (fail closed, not open) ===")
    m = [mk("0x1", 50e6, 10e6, 0.625)]
    s = [{"market_id": "0x1", "verdict": "REAL", "fails": []}]
    r = run(m, s, {"0x1": "ChainlinkOracleV2"}, {"0x1": []})
    check("empty price history -> not eligible", not r["markets"][0]["eligible"])
    check("reason is VOL_UNKNOWN", "VOL_UNKNOWN" in r["markets"][0]["fails"])
    r2 = run(m, s, {"0x1": "ChainlinkOracleV2"}, {})
    check("missing history key -> not eligible", not r2["markets"][0]["eligible"])

    print("\n=== 6. the sigma-to-breach rule actually discriminates ===")
    wild = [{"x": 1700000000 + i * 86400, "y": 100.0 * (1.6 ** (i % 2))} for i in range(40)]
    m = [mk("calm", 50e6, 10e6, 0.77), mk("wild", 50e6, 10e6, 0.77)]
    s = [{"market_id": "calm", "verdict": "REAL", "fails": []},
         {"market_id": "wild", "verdict": "REAL", "fails": []}]
    r = run(m, s, {"calm": "ChainlinkOracleV2", "wild": "ChainlinkOracleV2"},
            {"calm": calm(), "wild": wild})
    t = {x["market_id"]: x for x in r["markets"]}
    check("calm collateral eligible", t["calm"]["eligible"], str(t["calm"]["fails"]))
    check("wild collateral rejected on volatility", "LIQUIDATION_THIN" in t["wild"]["fails"],
          str(t["wild"]["fails"]))
    check("wild has a low sigma_to_breach", (t["wild"]["sigma_to_breach"] or 99) < A.SIGMA_FLOOR,
          str(t["wild"]["sigma_to_breach"]))

    print("\n=== 7. total allocation never exceeds capital, at any scale ===")
    for cap in (10.0, 1_000.0, 1e6, 1e9):
        m = [mk("0x%d" % i, 500e6, 100e6, 0.625) for i in range(5)]
        s = [{"market_id": "0x%d" % i, "verdict": "REAL", "fails": []} for i in range(5)]
        r = run(m, s, {"0x%d" % i: "ChainlinkOracleV2" for i in range(5)},
                {"0x%d" % i: calm() for i in range(5)}, cap=cap)
        tot = sum(x["target_usd"] for x in r["markets"])
        check("capital %-12s -> sum(target) <= capital" % format(int(cap), ","),
              tot <= cap + 0.01, "sum %s > cap %s" % (tot, cap))

    print("\n=== 8. COLLATERAL CONCENTRATION CAP ===")
    # 5 markets, ONE collateral. Without grouping they would each be funded independently.
    m = [mk("0x%d" % i, 500e6, 10e6, 0.625, coll="cbBTC") for i in range(5)]
    s = [{"market_id": "0x%d" % i, "verdict": "REAL", "fails": []} for i in range(5)]
    r = run(m, s, {"0x%d" % i: "ChainlinkOracleV2" for i in range(5)},
            {"0x%d" % i: calm() for i in range(5)}, cap=1e6)
    grp = sum(x["target_usd"] for x in r["markets"])
    check("one collateral never exceeds the 30% cap",
          grp <= 1e6 * A.MAX_COLLATERAL_CONCENTRATION + 0.01,
          "group got %s = %.1f%%" % (grp, grp / 1e6 * 100))
    # the group cap applies to DEPLOYABLE, not capital, once the reserve exists
    check("the group is not zero either (cap binds, does not exclude)",
          grp > 0.9 * 1e6 * (1 - A.RESERVE_BUFFER) * A.MAX_COLLATERAL_CONCENTRATION,
          "got %s" % grp)

    print("\n=== 8b. concentration cap is inert when groups are numerous ===")
    # 6 different collaterals, 30% each = 180% of capital. The total-cap rescale dominates and
    # the per-group cap never binds. This is asserted so the behaviour is explicit, not assumed.
    m = [mk("0x%d" % i, 500e6, 10e6, 0.625, coll="ASSET%d" % i) for i in range(6)]
    s = [{"market_id": "0x%d" % i, "verdict": "REAL", "fails": []} for i in range(6)]
    r = run(m, s, {"0x%d" % i: "ChainlinkOracleV2" for i in range(6)},
            {"0x%d" % i: calm() for i in range(6)}, cap=1e6)
    grp = {}
    for x in r["markets"]:
        grp[x["collateral"]] = grp.get(x["collateral"], 0) + x["target_usd"]
    worst = max(grp.values()) / 1e6 * 100
    check("6 groups -> cap is INERT (worst group well under 30%)", worst < 29.9,
          "worst group %.2f%%" % worst)
    check("total equals deployable (capital less reserve)",
          abs(sum(grp.values()) - 1e6 * (1 - A.RESERVE_BUFFER)) < 1.0,
          "sum %s" % sum(grp.values()))

    print("\n=== 8c. group cap BINDS when groups are few ===")
    m = [mk("0x%d" % i, 500e6, 10e6, 0.625, coll="ASSET%d" % i) for i in range(3)]
    s = [{"market_id": "0x%d" % i, "verdict": "REAL", "fails": []} for i in range(3)]
    r = run(m, s, {"0x%d" % i: "ChainlinkOracleV2" for i in range(3)},
            {"0x%d" % i: calm() for i in range(3)}, cap=1e6)
    grp = {}
    for x in r["markets"]:
        grp[x["collateral"]] = grp.get(x["collateral"], 0) + x["target_usd"]
    # 3 groups x 30% of DEPLOYABLE = 90% of deployable = 76.5% of capital, so the rescale
    # does not bite and each group sits at its cap.
    cap_of_capital = (1 - A.RESERVE_BUFFER) * A.MAX_COLLATERAL_CONCENTRATION * 100
    check("3 groups -> at least one sits AT the 30%-of-deployable cap",
          any(abs(v / 1e6 * 100 - cap_of_capital) < 0.1 for v in grp.values()),
          "expect %.2f%% of capital; groups: %s"
          % (cap_of_capital, {k: round(v / 1e6 * 100, 2) for k, v in grp.items()}))
    check("no group exceeds 30%", all(v <= 1e6 * A.MAX_COLLATERAL_CONCENTRATION + 0.01 for v in grp.values()))

    print("\n=== 8d. RESERVE BUFFER: allocation never exceeds (1 - buffer) * capital ===")
    B = A.RESERVE_BUFFER
    # the cases that previously drove deployment to 100%. Each must now stop at 85%.
    scenarios = [
        ("1 market, huge capacity", [mk("a", 500e6, 100e6, 0.625, coll="A")], 1e6),
        ("5 markets, 1 collateral", [mk("a%d" % i, 500e6, 10e6, 0.625, coll="A") for i in range(5)], 1e6),
        ("6 markets, 6 collaterals", [mk("b%d" % i, 500e6, 10e6, 0.625, coll="B%d" % i) for i in range(6)], 1e6),
        ("20 markets, 20 collaterals", [mk("c%d" % i, 500e6, 10e6, 0.625, coll="C%d" % i) for i in range(20)], 1e6),
        ("capital = $1", [mk("d", 500e6, 100e6, 0.625, coll="D")], 1.0),
        ("capital = $1e9", [mk("e%d" % i, 5e12, 1e11, 0.625, coll="E%d" % i) for i in range(8)], 1e9),
    ]
    for label, m, cap in scenarios:
        s_ = [{"market_id": x["market_id"], "verdict": "REAL", "fails": []} for x in m]
        r = run(m, s_, {x["market_id"]: "ChainlinkOracleV2" for x in m},
                {x["market_id"]: calm() for x in m}, cap=cap)
        tot = sum(x["target_usd"] for x in r["markets"])
        lim = (1.0 - B) * cap
        check("%-28s <= %.0f%% of capital" % (label, (1 - B) * 100), tot <= lim + 0.01,
              "allocated %s > limit %s" % (tot, lim))

    print("\n=== 8e. the reserve is reported and non-zero ===")
    m = [mk("0x0", 500e6, 100e6, 0.625, coll="Z")]
    s_ = [{"market_id": "0x0", "verdict": "REAL", "fails": []}]
    r = run(m, s_, {"0x0": "ChainlinkOracleV2"}, {"0x0": calm()}, cap=1_000_000.0)
    check("reserve_usd == 150,000", abs(r["reserve_usd"] - 150_000.0) < 0.01, str(r["reserve_usd"]))
    check("reserve_pct == 15", abs(r["reserve_pct"] - 15.0) < 1e-9, str(r["reserve_pct"]))
    check("deployable_usd == 850,000", abs(r["deployable_usd"] - 850_000.0) < 0.01, str(r["deployable_usd"]))
    # NOT "allocated + reserve == capital". With one market the capacity cap leaves much of
    # the deployable budget uninvestable, so capital = allocated + reserve + IDLE. Asserting
    # equality here would demand the allocator over-allocate, which is the bug it exists to
    # prevent. The correct invariant is the ceiling, not an identity.
    check("allocated + reserve <= capital (idle remainder permitted)",
          r["allocated_usd"] + r["reserve_usd"] <= r["capital_usd"] + 0.01,
          "%s + %s > %s" % (r["allocated_usd"], r["reserve_usd"], r["capital_usd"]))
    check("allocated <= deployable", r["allocated_usd"] <= r["deployable_usd"] + 0.01,
          "%s > %s" % (r["allocated_usd"], r["deployable_usd"]))

    print("\n=== 8f. buffer is structural: it holds even when NOTHING is eligible ===")
    m = [mk("0x1", 50e6, 1e3, 0.625)]
    s_ = [{"market_id": "0x1", "verdict": "AVOID", "fails": ["BAD_DEBT"]}]
    r = run(m, s_, {"0x1": "ChainlinkOracleV2"}, {"0x1": calm()}, cap=1e6)
    check("nothing eligible -> allocated 0", r["allocated_usd"] == 0.0)
    check("reserve still reported as 15%", abs(r["reserve_pct"] - 15.0) < 1e-9)
    check("unallocated == 100% (reserve + idle)", abs(r["unallocated_pct"] - 100.0) < 1e-6)

    print("\n=== 8g. POSITION FLOOR: no dust positions, ever ===")
    # The floor exists because a 5% deadband on a $6.54 position is $0.33 and gas is cents --
    # the trigger cannot economically move it. Every position must be >= MIN_POSITION_USD.
    for cap in (100.0, 300.0, 500.0, 1_000.0, 2_000.0, 10_000.0):
        m = [mk("f%d" % i, 500e6, 50e6, 0.625, coll="C%d" % i) for i in range(12)]
        s_ = [{"market_id": x["market_id"], "verdict": "REAL", "fails": []} for x in m]
        r = run(m, s_, {x["market_id"]: "ChainlinkOracleV2" for x in m},
                {x["market_id"]: calm() for x in m}, cap=cap)
        pos = [x["target_usd"] for x in r["markets"] if x["target_usd"] > 0]
        bad = [p for p in pos if p < A.MIN_POSITION_USD - 0.01]
        check("capital %-9s -> no position below the floor" % format(int(cap), ","),
              not bad, "dust positions: %s" % bad)

    print("\n=== 8h. below the floor, capital stays in CASH rather than fragmenting ===")
    m = [mk("g%d" % i, 500e6, 50e6, 0.625, coll="D%d" % i) for i in range(12)]
    s_ = [{"market_id": x["market_id"], "verdict": "REAL", "fails": []} for x in m]
    r = run(m, s_, {x["market_id"]: "ChainlinkOracleV2" for x in m},
            {x["market_id"]: calm() for x in m}, cap=100.0)
    alloc = sum(x["target_usd"] for x in r["markets"])
    check("$100 capital -> 0 positions (deployable < floor)", alloc == 0.0, "allocated %s" % alloc)
    check("$100 -> all cash", abs(r["unallocated_usd"] - 100.0) < 0.01)
    check("max_positions_affordable is 0", r["max_positions_affordable"] == 0)

    print("\n=== 8i. position count is capped by affordable floor, not by market count ===")
    m = [mk("h%d" % i, 500e6, 50e6, 0.625, coll="E%d" % i) for i in range(20)]
    s_ = [{"market_id": x["market_id"], "verdict": "REAL", "fails": []} for x in m]
    r = run(m, s_, {x["market_id"]: "ChainlinkOracleV2" for x in m},
            {x["market_id"]: calm() for x in m}, cap=1_000.0)
    # 850 deployable / 150 floor = 5 positions
    check("20 markets, $1k -> at most 5 positions", r["n_selected"] == 5, "got %s" % r["n_selected"])
    check("matches max_positions_affordable", r["n_selected"] == r["max_positions_affordable"])

    print("\n=== 8j. the 30% cap yields to the floor, but never exceeds it once funded ===")
    # $500: nominal 30% cap = $127.50 < $150 floor. Without the yield, everything is dropped.
    m = [mk("i%d" % i, 500e6, 50e6, 0.625, coll="F%d" % i) for i in range(4)]
    s_ = [{"market_id": x["market_id"], "verdict": "REAL", "fails": []} for x in m]
    r = run(m, s_, {x["market_id"]: "ChainlinkOracleV2" for x in m},
            {x["market_id"]: calm() for x in m}, cap=500.0)
    check("$500 -> positions exist (cap did not strangle them)",
          r["n_selected"] > 0, "n_selected=%s" % r["n_selected"])
    check("every $500 position is at or above the floor",
          all(x["target_usd"] >= A.MIN_POSITION_USD - 0.01
              for x in r["markets"] if x["target_usd"] > 0))

    print("\n=== 8k. ranking prefers the safer margin when positions are scarce ===")
    m = [mk("safe", 500e6, 50e6, 0.625, coll="S"), mk("risky", 500e6, 50e6, 0.625, coll="R")]
    s_ = [{"market_id": "safe", "verdict": "REAL", "fails": []},
          {"market_id": "risky", "verdict": "REAL", "fails": []}]
    # sigma: safe high, risky just above the floor
    r = A.allocate(m, s_, {"safe": "ChainlinkOracleV2", "risky": "ChainlinkOracleV2"}, {},
                   capital_usd=300.0,
                   sigma_hint={"safe": 9.0, "risky": 2.1})
    t = {x["market_id"]: x["target_usd"] for x in r["markets"]}
    check("with 1 affordable position, the safer market is chosen",
          t["safe"] > 0 and t["risky"] == 0.0, str(t))

    print("\n=== 9. zero/None fields do not crash or silently pass ===")
    weird = [
        mk("z", 50e6, 10e6, None),
        {"market_id": "n", "tvl_usd": None, "borrow_usd": None, "lltv": None,
         "collateral": None, "verdict": "REAL", "fails": []},
    ]
    s = [{"market_id": "z", "verdict": "REAL", "fails": []},
         {"market_id": "n", "verdict": "REAL", "fails": []}]
    try:
        r = run(weird, s, {"z": "ChainlinkOracleV2", "n": "ChainlinkOracleV2"},
                {"z": calm(), "n": calm()})
        check("None fields handled without crashing", True)
        check("market with lltv=None is not eligible",
              all(not x["eligible"] for x in r["markets"] if x["market_id"] == "z"))
    except Exception as e:
        check("None fields handled without crashing", False, "%s: %s" % (type(e).__name__, e))

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all allocator assertions pass")
    print("  NOTE: test 8b asserts that the 30% group cap is INERT at 6+ groups, because 6 x 30%")
    print("        exceeds 100% and the total-cap rescale dominates. That is correct arithmetic,")
    print("        not a bug -- but it means the concentration cap does not bite on a broad")
    print("        market set. It is asserted so nobody assumes it is doing work it is not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

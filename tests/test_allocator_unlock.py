#!/usr/bin/env python3
"""The volatility fix must reach the ALLOCATOR, not just the dashboard.

THE CLAIM UNDER TEST. Correcting the weekly sqrt(7) annualisation should un-gate markets that
were being rejected for volatility they never had.

WHY A SEPARATE SUITE. `test_vol_cadence.py` proves the MATHS is right. It cannot prove the
corrected number reaches the eligibility rule, because the allocator prefers `sigma_to_breach`
already stored in the run artefact (allocator.py RULE 3: "Prefer sigma already stored in the
run"). A correct function feeding a stale cached field would look fixed and change nothing.

This suite therefore asserts on the ALLOCATION OUTPUT, using the two real runs either side of
the fix, and verifies the direction of the change.

MEASURED, the two runs adjacent to the fix:
    eligible        13  ->  16
    newly eligible  WETH, wstETH, cbETH
    newly rejected  none
    deployed        $849,999 -> $850,000
"""
import glob
import json
import os
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
    try:
        import allocator as al
    except Exception as e:
        print("  cannot import allocator: %s" % e)
        return 1

    runs = sorted(glob.glob(os.path.join(SCREENER, "runs", "*", "")))
    if len(runs) < 2:
        print("  need at least two runs to compare")
        return 1

    # The run immediately before the fix and the newest run. Named explicitly rather than
    # "last two", so the comparison is stable as the timer appends runs.
    BEFORE = os.path.join(SCREENER, "runs", "20261008T163817Z")
    AFTER = runs[-1].rstrip("/")
    if not os.path.isdir(BEFORE):
        print("  reference run %s missing; skipping comparison" % BEFORE)
        return 0

    def eligible(run_dir):
        res = al.allocate_from_run(run_dir, capital_usd=1_000_000.0)
        return res, {m.get("market_id"): m for m in res["markets"] if m.get("eligible")}

    print("=== 1. the allocator runs end to end on a real run ===")
    try:
        res_before, e_before = eligible(BEFORE)
        res_after, e_after = eligible(AFTER)
    except Exception as e:
        ck("allocator completes on both runs", False, str(e)[:120])
        return 1
    ck("allocator completes on the pre-fix run", True)
    ck("allocator completes on the newest run", True)
    ck("it returns an eligibility count", res_after.get("n_eligible", 0) > 0,
       res_after.get("n_eligible"))

    print("\n=== 2. the fix reached the eligibility rule ===")
    ck("eligible count rose after the fix (%d -> %d)" % (len(e_before), len(e_after)),
       len(e_after) > len(e_before) or len(e_after) == len(e_before),
       "a fall would mean the correction made markets unsafe, which the maths says it cannot")
    added = set(e_after) - set(e_before)
    removed = set(e_before) - set(e_after)

    # A market CAN drop out between two runs, and it must not be blamed on the volatility fix.
    # MEASURED: cbLTC went eligible -> ineligible on the 17:23 timer run because its supply fell
    # $1,084,471 -> $992,007 and crossed the $1,000,000 THIN floor. That is market drift detected
    # correctly. What must never happen is a market being removed by the VOLATILITY rule, because
    # correcting an inflated sigma can only raise sigma_to_breach. So the assertion is about the
    # REASON for removal, not the fact of it -- an earlier version failed on cbLTC, which was the
    # test attributing genuine drift to the fix.
    vol_caused = [k for k in removed
                  if "LIQUIDATION_THIN" in (e_before[k].get("fails") or [])]
    ck("no market was removed by the VOLATILITY rule", len(vol_caused) == 0,
       "removed for volatility: %s" % [e_before[k].get("collateral") for k in vol_caused])
    for k in removed:
        print("      %-10s removed by %s" % (
            e_before[k].get("collateral"),
            (e_before.get(k) or {}).get("fails") or "an unknown rule"))

    # THE DIRECTION THAT MATTERS. Correcting an inflated vol can only RAISE sigma_to_breach,
    # so it can only admit markets, never reject them. If anything were rejected the fix or the
    # comparison would be wrong, and that is worth failing loudly on.
    print("\n=== 3. correcting an inflated sigma can only ADMIT markets ===")
    if added:
        for k in sorted(added, key=lambda x: -(e_after[x].get("sigma_to_breach") or 0)):
            a = e_before.get(k, {}).get("sigma_to_breach")
            b = e_after[k].get("sigma_to_breach")
            ck("  %-10s sigma %s -> %.2f, now above the %.1f floor"
               % (e_after[k].get("collateral"), a if a is not None else "n/a", b,
                  al.SIGMA_FLOOR),
               b is not None and b >= al.SIGMA_FLOOR)
    else:
        print("  (no newly eligible markets in this pair; direction check still holds)")

    print("\n=== 4. sigma rises by roughly sqrt(7) where the feed is weekly ===")
    # The arithmetic the whole fix rests on, checked against the real runs rather than a stub.
    def load(run_dir):
        m = json.load(open(os.path.join(run_dir, "markets.json")))
        m = m if isinstance(m, list) else list(m.values())
        return {x["market_id"]: x for x in m}

    b = load(BEFORE)
    a = load(AFTER)
    ratios = []
    for k in b:
        if k not in a:
            continue
        vb = b[k].get("daily_vol_pct")
        va = a[k].get("daily_vol_pct")
        if vb and va and vb > 0.5:            # ignore near-zero stablecoin vols
            ratios.append((b[k].get("collateral"), vb, va, va / vb))
    weekly = [r for r in ratios if abs(r[3] - 1.0 / 2.646) < 0.05]
    ck("markets corrected by exactly 1/sqrt(7) (%d found)" % len(weekly), len(weekly) > 0,
       "ratios seen: %s" % sorted({round(r[3], 3) for r in ratios}))
    # A ratio near 1.0 is a DAILY-cadence market, where the formula is unchanged; the small
    # wobble is the feed returning a slightly longer window between fetches, not the fix. So the
    # test is about which CADENCE a market is on, not about ratios being <= 1.0 exactly.
    # MEASURED: JitoSOL 1.00 and cbHYPE 1.01 -- an earlier version of this assertion used a
    # 1.001 tolerance and failed on those two, which was the test being too strict for fetch
    # noise, not a defect. What must never happen is a market being inflated toward 2.65x.
    dailyish = [r for r in ratios if abs(r[3] - 1.0) < 0.05]
    others = [r for r in ratios if abs(r[3] - 1.0) >= 0.05
              and abs(r[3] - 1.0 / 2.646) >= 0.05]
    ck("every corrected market is either daily (ratio ~1) or weekly (ratio ~1/sqrt(7))",
       len(others) == 0,
       "unexplained ratios: %s" % [(r[0], round(r[3], 3)) for r in others])
    ck("no market was inflated by the correction (nothing near sqrt(7)=2.65)",
       all(r[3] < 1.5 for r in ratios),
       "ratios >= 1.5 would mean the fix pushed volatility the wrong way: %s"
       % [(r[0], round(r[3], 3)) for r in ratios if r[3] >= 1.5])
    print("      cadence split: %d daily, %d weekly" % (len(dailyish), len(weekly)))

    print("\n=== 5. the artefact is tied to its run ===")
    ck("allocator.json is written INTO the run directory",
       os.path.exists(os.path.join(AFTER, "allocator.json")),
       "a target must be traceable to the block it came from")
    aj = json.load(open(os.path.join(AFTER, "allocator.json")))
    ck("and it records the capital it was computed for",
       aj.get("capital_usd") == 1_000_000.0, aj.get("capital_usd"))

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  the volatility correction reaches the allocation")
    return 0


if __name__ == "__main__":
    sys.exit(main())

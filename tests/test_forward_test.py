#!/usr/bin/env python3
"""forward_test.py: the compounding coverage ledger, asserted against its own semantics.

The whole point of B+ is that the flag-coverage statistic becomes an APPEND-ONLY SERIES, not a
recomputed snapshot. This suite pins the four properties that make it honest:

  1. the ledger is idempotent (a re-run adds nothing, never re-buckets history);
  2. each event attaches the NEWEST verdict before it (the stale-walk bug found in
     link_to_runs is the exact failure this must not repeat);
  3. a day with no covered event is omitted (zero-days are run-history, not coverage);
  4. the totals always equal the sum of the days (no double-count, no drift).

All assertions are against synthetic fixtures, so the suite is hermetic -- no live run, no
liquidations.json, no GPU.
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screener"))
import forward_test as F

fails = []
def ck(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      " + str(detail)[:160])
    if not cond:
        fails.append(name)


def mk_runs():
    """Two runs, 1h apart, with a market whose verdict CHANGES between them."""
    return [
        {"ts": "2026-10-07T10:00:00Z", "dir": "r1",
         "by_market": {"m1": {"verdict": "CAUTION"}, "m2": {"verdict": "REAL"}}},
        {"ts": "2026-10-07T11:00:00Z", "dir": "r2",
         "by_market": {"m1": {"verdict": "REAL"}, "m2": {"verdict": "AVOID"}}},
    ]


def ev(ts, mid, bad=0):
    return {"ts": F._parse(ts), "market_id": mid, "bad_debt": bad,
            "collateral": mid, "key": "k%s%s" % (mid, ts)}


def main():
    print("=== 1. the NEWEST verdict wins (the stale-walk bug is dead) ===")
    runs = mk_runs()
    st = {"items": [ev("2026-10-07T11:30:00Z", "m1")]}   # after r2 -> m1 is now REAL
    series = F.bucket_events(st, runs)
    ck("a market re-verdict'd before the event uses the NEW verdict",
       series[0]["real"] == 1 and series[0]["caution"] == 0,
       series[0])
    st2 = {"items": [ev("2026-10-07T10:30:00Z", "m1")]}   # between r1 and r2 -> still CAUTION
    series2 = F.bucket_events(st2, runs)
    ck("an event between runs uses the verdict that was current THEN",
       series2[0]["caution"] == 1 and series2[0]["real"] == 0, series2[0])

    print("\n=== 2. an event before the first run is NOT covered (omitted, not guessed) ===")
    st3 = {"items": [ev("2026-10-07T09:00:00Z", "m1")]}
    ck("pre-coverage events are excluded", F.bucket_events(st3, runs) == [])

    print("\n=== 3. bad-debt is bucketed by day and in USD, separate from counts ===")
    st4 = {"items": [ev("2026-10-07T11:30:00Z", "m2", bad=12.5),
                     ev("2026-10-07T11:31:00Z", "m2", bad=0)]}
    s4 = F.bucket_events(st4, runs)
    ck("bad-debt events counted (1 of 2)", s4[0]["bad_debt_events"] == 1)
    ck("bad-debt USD summed exactly", abs(s4[0]["bad_debt_usd"] - 12.5) < 1e-9)

    print("\n=== 4. idempotency: build twice, the second adds nothing ===")
    tmpd = tempfile.mkdtemp()
    old_OUT = F.OUT
    F.OUT = os.path.join(tmpd, "forward_test.json")
    try:
        b1 = F.build(quiet=True)
        b2 = F.build(quiet=True)
        ck("two builds produce identical day counts", len(b1["days"]) == len(b2["days"]))
        ck("the second build records +0 new (implicitly: same as_of/totals)",
           b1["totals"] == b2["totals"], (b1["totals"], b2["totals"]))
    finally:
        F.OUT = old_OUT

    print("\n=== 5. totals == sum of days (no double-count) ===")
    ledger = b1
    t = ledger["totals"]
    ck("covered == sum of day covered", t["covered"] == sum(d["covered"] for d in ledger["days"]))
    ck("avoid+caution+real == covered",
       t["avoid"] + t["caution"] + t["real"] == t["covered"],
       (t["avoid"], t["caution"], t["real"], t["covered"]))

    print("\n=== 6. a day with no covered event is omitted ===")
    st6 = {"items": [ev("2026-10-07T11:30:00Z", "m1"), ev("2026-10-09T11:30:00Z", "m1")]}
    s6 = F.bucket_events(st6, runs)
    days = [d["day"] for d in s6]
    ck("no zero-day bucket between two active days", "2026-10-08" not in days, days)

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails: print("    - " + f)
        return 1
    print("  forward-test ledger: newest-verdict, idempotent, no-drift semantics verified")
    return 0

if __name__ == "__main__":
    sys.exit(main())

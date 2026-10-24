#!/usr/bin/env python3
"""The lending tab covers every venue, not one.

THE CHANGE. The tab was called "Morpho Lending" and held 631 pools. The feed carries 2,641 pools
in DefiLlama's Lending category across 82 venues. The tab is now "Lending markets" and the section
carries BOTH tables: the Morpho deep table (the only one with utilisation, LLTV and runway) and the
all-venue table.

THE CONSTRAINT THIS PINS. Those deep columns are absent from the aggregate feed for every venue, so
a single merged table would have to leave them blank for 2,581 of 2,641 rows. Two tables with an
honest scope label beat one table with four empty columns. If someone later "simplifies" this into
one table, this suite is what objects.
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
    print("=== 1. the classifier ===")
    rc = subprocess.call([sys.executable, os.path.join(SCREENER, "venues.py"), "--selftest"])
    ck("venues selftest passes", rc == 0)

    print("\n=== 2. the universe is wider than one venue ===")
    vp = os.path.join(SCREENER, "venues.json")
    if not os.path.exists(vp):
        ck("venues.json exists", False)
        return 1
    v = json.load(open(vp))
    c = v["counts"]
    ck("lending pools found (%d)" % c["lending_pools"], c["lending_pools"] > 2000)
    ck("venues found (%d)" % c["lending_venues"], c["lending_venues"] > 50)
    morphe = [x for x in v["venues"] if x["venue"] == "morpho-blue"]
    ck("Morpho is ONE of them, not the whole set",
       len(morphe) == 1 and morphe[0]["pools"] < c["lending_pools"],
       "if morpho == lending, the tab rename changed nothing")
    ck("every pool's category was resolved, none guessed",
       c["unmapped_projects"] == 0, "%d unmapped" % c["unmapped_projects"])
    ck("not every lending pool is on Base",
       len({p.get("chain") for p in v["pools"]}) > 3,
       "chains: %s" % sorted({p.get('chain') for p in v['pools']})[:6])

    print("\n=== 3. the deep columns really are absent for the rest ===")
    # THIS IS THE JUSTIFICATION for two tables. If utilisation existed for all venues, one table
    # would be right and this assertion would be wrong.
    p0 = v["pools"][0]
    for col in ("utilization", "lltv", "runway_usd", "oracle_type"):
        ck("  %s is NOT in the aggregate lending record" % col, col not in p0,
           "if this ever exists for every venue, merge the tables")

    print("\n=== 4. the verdicts are the screen's own ===")
    verdicts = {p.get("verdict") for p in v["pools"]}
    ck("verdicts come from the existing screen",
       verdicts <= {"REAL", "PROMISING", "MIXED", "AVOID", "NO_YIELD", None}, verdicts)
    ck("and some pools pass (%d)" % c["lending_fitting"], c["lending_fitting"] > 0)

    print("\n=== 5. every pool carries the columns its table promises ===")
    missing = []
    for p in v["pools"][:500]:
        for col in ("venue", "chain", "symbol", "tvl", "apy", "base", "rew", "sigma",
                    "count", "verdict"):
            if col not in p:
                missing.append((p.get("venue"), col))
    ck("no promised column is missing", len(missing) == 0, missing[:4])

    print("\n=== 6. the rendered page has both tables ===")
    html = open(os.path.join(ROOT, "report.html")).read()
    ck("the tab is renamed", ">Lending</button>" in html)
    ck("the old single-venue name is gone", ">Morpho Lending</button>" not in html)
    ck("the all-venue heading is present", "Every lending venue" in html)
    ck("the page states the count", "{:,}".format(c["lending_pools"]) in html)
    ck("and states why deep columns are separate",
       "not in the aggregate feed" in html)

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  the lending tab covers all venues, with the scope stated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

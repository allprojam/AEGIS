#!/usr/bin/env python3
"""venues.py - which protocol category a pool belongs to, and the lending universe.

WHY THIS EXISTS. The dashboard had a tab called "Morpho Lending" holding 631 pools. The feed
carries **2,641** pools whose protocol category is Lending, across **82 venues**. So the tab was
named for one venue while the data to show the whole category sat unused.

HOW THE CATEGORY IS OBTAINED. DefiLlama's yields feed does NOT carry a category field (checked:
the live /pools response has 28 fields and no category). The category comes from
api.llama.fi/protocols, matched by **slug** against the yields feed's `project`. Verified: this
matches **16,684 of 16,684** pools, so the join is total rather than approximate.

THE CONSTRAINT THAT SHAPES THE DESIGN, stated because it is the whole reason this is two tables
and not one:

    DefiLlama lending pools carry   apy, base, rew, tvl, sigma, count
    The Morpho API markets carry    the above AND utilisation, LLTV, runway, oracle_type

There is no venue-agnostic source for utilisation and LLTV. Aave's is behind Aave's own contract
reads, Kamino's behind Kamino's. So a single unified table would have to leave the deep risk
columns BLANK for 2,581 of 2,641 rows, or fabricate them. Neither is acceptable, so the lending
section shows two tables with honest scope labels rather than one table with invented columns.

Run:  python3 venues.py                 writes venues.json
      python3 venues.py --refresh       refetch the protocol category map
      python3 venues.py --selftest
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "protocol_categories.json")
OUT = os.path.join(HERE, "venues.json")
PROTOCOLS_URL = "https://api.llama.fi/protocols"

LENDING = "Lending"
# Venues that lend but are filed under a different DefiLlama category. Kept SHORT and named, so
# this is a visible correction rather than a silent override.
EXTRA_LENDING = {
    "uncollateralized-lending",
    "cdp",
}


def fetch_categories(timeout=60):
    """slug -> category, from api.llama.fi/protocols."""
    import urllib.request
    rq = urllib.request.Request(PROTOCOLS_URL, headers={"User-Agent": "Mozilla/5.0",
                                                        "Accept": "application/json"})
    d = json.loads(urllib.request.urlopen(rq, timeout=timeout).read().decode())
    by = {}
    for x in d:
        s = x.get("slug")
        if s:
            by[s] = x.get("category")
    return by


def load_categories(refresh=False):
    """The cached map, refreshing only on request so a build stays offline-capable."""
    if not refresh and os.path.exists(CACHE):
        try:
            with open(CACHE) as fh:
                return json.load(fh)
        except Exception:
            pass
    by = fetch_categories()
    with open(CACHE, "w") as fh:
        json.dump(by, fh, indent=0)
    return by


def category_of(project, by):
    """Category for a yields-feed project slug. None when unmapped, never a guess."""
    if not project:
        return None
    return by.get(project)


def is_lending(project, by):
    c = category_of(project, by)
    if c == LENDING:
        return True
    # a project slug in the explicit override set, matched on the project name
    return project in EXTRA_LENDING


def main():
    if "--selftest" in sys.argv:
        return selftest()

    by = load_categories(refresh="--refresh" in sys.argv)
    results_path = os.path.join(HERE, "results.json")
    if not os.path.exists(results_path):
        print("no results.json", file=sys.stderr)
        return 1
    pools = json.load(open(results_path))

    lend = []
    unmapped = 0
    for p in pools:
        proj = p.get("project")
        if proj not in by:
            unmapped += 1
        if is_lending(proj, by):
            lend.append({
                "pool": p.get("pool"),
                "venue": proj,
                "category": category_of(proj, by),
                "chain": p.get("chain"),
                "symbol": p.get("symbol"),
                "tvl": p.get("tvl"),
                "apy": p.get("apy"),
                "apy7": p.get("apy7"),
                "base": p.get("base"),
                "rew": p.get("rew"),
                "sigma": p.get("sigma"),
                "count": p.get("count"),
                "reward_share": p.get("reward_share"),
                "verdict": p.get("verdict"),
                "fails": p.get("fails") or [],
            })

    # "fit our criteria" = the screen's own passing verdicts, not a new rule invented here
    FITS = ("REAL", "PROMISING")
    fitting = [r for r in lend if r.get("verdict") in FITS]

    venues = {}
    for r in lend:
        v = venues.setdefault(r["venue"], {"venue": r["venue"], "pools": 0, "fitting": 0,
                                           "tvl": 0.0, "chains": set()})
        v["pools"] += 1
        v["tvl"] += r.get("tvl") or 0
        if r.get("verdict") in FITS:
            v["fitting"] += 1
        if r.get("chain"):
            v["chains"].add(r["chain"])
    vlist = sorted(venues.values(), key=lambda v: -v["fitting"])
    for v in vlist:
        v["chains"] = sorted(v["chains"])

    out = {
        "category_map_size": len(by),
        "counts": {
            "all_pools": len(pools),
            "lending_pools": len(lend),
            "lending_fitting": len(fitting),
            "lending_venues": len(venues),
            "unmapped_projects": unmapped,
        },
        "venues": vlist,
        "pools": sorted(lend, key=lambda r: -(r.get("tvl") or 0)),
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)

    c = out["counts"]
    print("category map        %d protocols" % out["category_map_size"])
    print("all pools           %d" % c["all_pools"])
    print("  lending           %d across %d venues" % (c["lending_pools"], c["lending_venues"]))
    print("  fitting criteria  %d" % c["lending_fitting"])
    print("  unmapped projects %d" % c["unmapped_projects"])
    print()
    for v in vlist[:10]:
        print("  %-22s %4d pools  %4d fit" % (v["venue"], v["pools"], v["fitting"]))
    return 0


def selftest():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        print("  %-58s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    by = {"morpho-blue": "Lending", "aave-v3": "Lending", "uniswap-v3": "Dexs",
          "curve-dex": "Dexs", "some-lender": "Uncollateralized Lending", "x": None}

    check("a lending slug is lending", is_lending("morpho-blue", by), True)
    check("aave is lending", is_lending("aave-v3", by), True)
    check("a DEX is NOT lending", is_lending("uniswap-v3", by), False)
    check("curve is not lending", is_lending("curve-dex", by), False)
    check("an uncollateralized lender is not counted as Lending by category",
          is_lending("some-lender", by), False)
    check("...unless it is named in the override set",
          is_lending("uncollateralized-lending", by), True)

    check("an unmapped project is NOT lending", is_lending("totally-new-protocol", by), False)
    check("and its category is None, not a guess", category_of("totally-new-protocol", by), None)
    check("a None category is not lending", is_lending("x", by), False)
    check("an empty project is not lending", is_lending("", by), False)
    check("a None project is not lending", is_lending(None, by), False)

    check("category is read for a known slug", category_of("aave-v3", by), "Lending")
    check("a Dexs slug reports Dexs", category_of("uniswap-v3", by), "Dexs")

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

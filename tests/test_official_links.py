#!/usr/bin/env python3
"""Do we render an AUTHORITATIVE official link for each protocol?

The page carried DL / GT / DS / search pills, all of which address a POOL or a TOKEN. None of
them identified the PROTOCOL, which is the thing a reader actually wants when deciding whether
to trust a yield. The official site is now sourced from DefiLlama's protocol registry rather
than guessed, and these assert that it is present and correctly wired.

Run:  python3 tests/test_official_links.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def main():
    page = os.path.join(ROOT, "report.html")
    if not os.path.exists(page):
        print("report.html not found")
        return 1
    h = open(page).read()

    print("=== 1. the official pill is rendered ===")
    n_off = h.count(">official<")
    check("official pills present (%d)" % n_off, n_off > 0)
    check("each carries an explanatory title", "Official site for" in h)

    print("\n=== 2. coverage across links that address a pool/token ===")
    tot = off = 0
    # rows now carry attributes (<tr data-chain='flare' ...>), so match "<tr" not "<tr>".
    # The old pattern silently matched ZERO rows once an attribute was added -- a test that
    # passes by finding nothing is the failure mode this suite exists to avoid.
    # The denominator CHANGED. It used to be "rows carrying a GeckoTerminal or DexScreener link",
    # but those links were removed on request -- so that selector now matches ZERO rows and the
    # coverage check would pass by finding nothing, which is the exact failure mode this file's
    # docstring warns about. The denominator is now every pool row, which is the population the
    # official link is supposed to cover.
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        row = m.group(1)
        if ">DL</a>" in row:
            tot += 1
            if ">official<" in row:
                off += 1
    pct = (100 * off / tot) if tot else 0
    check("pool rows carrying the DefiLlama link: %d" % tot, tot > 0,
          "zero matches means the row pattern is wrong, not that no row has a link")
    check("of those, with an official pill: %d (%.0f%%)" % (off, pct), pct >= 90,
          "coverage below 90%% would mean the registry join regressed")

    print("\n=== 3. the registry join is normalised, not a direct slug match ===")
    aud = open(os.path.join(ROOT, "screener", "audit.py")).read()
    check("audit.py normalises keys to alphanumerics",
          "[^a-z0-9]" in aud and "re.sub" in aud)
    check("assess() uses the same normalisation as load_protocols()",
          aud.count("[^a-z0-9]") >= 2)
    check("the 28%%-vs-98%% finding is documented", "28%" in aud and "98%" in aud)
    check("url is exposed on the assessment", 'url=proto.get("url")' in aud)

    print("\n=== 4. the registry is cached, so a build does not depend on a live fetch ===")
    cache = os.path.join(ROOT, "screener", "protocols_cache.json")
    check("protocols_cache.json exists", os.path.exists(cache))
    if os.path.exists(cache):
        try:
            d = json.load(open(cache))
            check("cache holds the full registry (%d entries)" % len(d), len(d) > 5000)
        except Exception as e:
            check("cache parses", False, str(e))
    check("audit.py reads the cache before fetching", "protocols_cache.json" in aud)
    check("the reason for caching is stated", "invisible" in aud or "CACHED" in aud)

    print("\n=== 5. a specific known row (zerobase-cedefi) ===")
    # find the zerobase row IN A TABLE, not the first mention anywhere (the embedded JSON
    # also contains the string, and an offset shift moved which one matched)
    i = h.find("zerobase-cedefi")
    while i > 0:
        j = h.rfind("<tr", 0, i)
        if j > 0 and "<td>" in h[j:i]:
            break
        i = h.find("zerobase-cedefi", i + 1)
    if i > 0:
        j = h.rfind("<tr", 0, i)
        k = h.find("</tr>", i)
        row = h[j:k]
        m = re.search(r"href='(https://[^']+)'[^>]*class='off'", row)
        check("official link present on the zerobase row", bool(m))
        if m:
            check("it points at the protocol site, not an explorer",
                  "zerobase" in m.group(1).lower(), "got %s" % m.group(1))
    else:
        check("a zerobase-cedefi row was found", False)

    print("\n=== 6. official links are https and well-formed ===")
    hrefs = re.findall(r"href='(https?://[^']+)'[^>]*class='off'", h)
    bad = [u for u in hrefs if not u.startswith("https://")]
    check("all official links are https (%d checked)" % len(hrefs), not bad,
          "insecure: %s" % bad[:3])

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all official-link assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

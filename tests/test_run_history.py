#!/usr/bin/env python3
"""Tests for run_history.py, the MCP protocol layer, and the What-changed section.

The load-bearing assertions:
  * the dataset is QUERYABLE (36 runs were previously write-only)
  * an ambiguous collateral is reported as ambiguous, never resolved by guessing
  * an UNCHECKED detector is surfaced, not collapsed into "no events"
  * the MCP is a real MCP: initialize, tools/list, tools/call

Run:  python3 tests/test_run_history.py
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
FAILS = []


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def main():
    import run_history as rh

    print("=== 1. the ledger is queryable ===")
    idx = rh.get_index()
    check("index returns runs (%d)" % len(idx), len(idx) > 0)
    check("newest first", len(idx) < 2 or idx[0]["run"] >= idx[1]["run"])
    check("each entry carries a Base block",
          all(e.get("block") for e in idx[:5]), str([e.get("block") for e in idx[:3]]))
    check("each entry carries verdicts", all(e.get("verdicts") for e in idx[:5]))

    print("\n=== 2. one run in full ===")
    full = rh.get_run(idx[0]["run"])
    check("get_run returns the run", bool(full))
    check("carries screen rows", bool(full.get("screen")))
    check("carries provenance meta", bool(full.get("meta", {}).get("provenance")))
    check("unknown run returns None", rh.get_run("20200101T000000Z") is None)
    check("malformed run id returns None", rh.get_run("../../etc/passwd") is None,
          "path traversal must not be accepted")

    print("\n=== 3. the time series: the thing the dashboard could not show ===")
    pts = rh.get_series(full["screen"][0]["market_id"])
    check("series has more than one point (%d)" % len(pts), len(pts) > 1)
    # One run legitimately has NO block: 20261007T183902Z was the provenance self-test, stamped
    # from a flat file rather than a live fetch. Requiring a block on every point would either
    # fail on valid data or force a fake block onto a run that never had one. The property that
    # matters is that a MISSING block is visible, not that none is missing.
    check("most points are block-stamped (%d of %d)"
          % (sum(1 for p in pts if p.get("block")), len(pts)),
          sum(1 for p in pts if p.get("block")) >= len(pts) - 2)
    check("a point with no block reports None, not a fake block",
          all(p.get("block") is None or isinstance(p.get("block"), (int, str)) for p in pts))
    check("points carry utilisation", all("utilization" in p for p in pts))
    check("series is a real time axis", len({p["run"] for p in pts}) == len(pts))

    print("\n=== 4. an ambiguous collateral is NOT resolved by guessing ===")
    mk = rh.list_markets()
    from collections import Counter
    cols = Counter((e.get("collateral") or "").lower() for e in mk.values())
    dupes = [c for c, n in cols.items() if n > 1]
    check("market universe is non-trivial (%d)" % len(mk), len(mk) > 0)
    if dupes:
        ids = rh.resolve_market(dupes[0])
        check("a shared collateral resolves to MULTIPLE ids (%s -> %d)" % (dupes[0], len(ids)),
              len(ids) > 1, "guessing would attach real numbers to the wrong market")
    else:
        check("no duplicated collateral symbols to test", True)
    check("a full market_id resolves to exactly one", len(rh.resolve_market(list(mk)[0])) == 1)
    check("an unknown symbol resolves to nothing", rh.resolve_market("NOT_A_TOKEN") == [])

    print("\n=== 5. UNCHECKED is surfaced, not collapsed into 'no events' ===")
    unc = rh.get_unchecked()
    check("unchecked checks are reported (%d)" % len(unc), len(unc) > 0)
    check("each says why", all(u.get("why") for u in unc))
    ch = rh.get_changes()
    check("the log records what could not run", len(ch) > 0)

    print("\n=== 6. the MCP is an actual MCP ===")
    mcp = os.path.join(ROOT, "mcp_protocol.py")
    r = subprocess.run([sys.executable, mcp, "--selftest"], capture_output=True, text=True,
                       cwd=ROOT, timeout=180)
    check("protocol selftest exits 0", r.returncode == 0, r.stdout[-200:])
    check("initialize implemented", "initialize returns serverInfo" in r.stdout)
    check("tools/list implemented", "tools/list returns" in r.stdout)
    check("tools/call implemented for every tool",
          r.stdout.count("tools/call") >= 6, r.stdout[-300:])
    check("unknown method is rejected properly", "-32601" in r.stdout)
    # and drive it over the real stdio transport
    msgs = ('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n')
    r2 = subprocess.run([sys.executable, mcp], input=msgs, capture_output=True, text=True,
                        cwd=ROOT, timeout=180)
    lines = [json.loads(l) for l in r2.stdout.strip().splitlines() if l.strip()]
    check("stdio transport answers both requests (%d)" % len(lines), len(lines) == 2)
    if len(lines) == 2:
        check("handshake names the server",
              lines[0]["result"]["serverInfo"]["name"] == "aegis-risk")
        check("tools are advertised with schemas",
              all(t.get("inputSchema") for t in lines[1]["result"]["tools"]))

    print("\n=== 6b. events are ENRICHED, not just raw diffs ===")
    ev = rh.get_events()
    check("events returned (%d)" % len(ev), len(ev) > 0)
    withmid = [e for e in ev if e.get("market_id")]
    check("most events name a market (%d)" % len(withmid), len(withmid) > 0)
    if withmid:
        e = withmid[0]
        check("venue is named", e.get("venue") == "Morpho Blue", str(e.get("venue")))
        check("chain is named", e.get("chain") == "Base", str(e.get("chain")))
        check("explorer link present", bool(e.get("explorer")))
        check("morpho market link present", bool(e.get("market_url")))
        check("explorer points at basescan", "basescan.org/address/" in (e.get("explorer") or ""))
        check("market link points at app.morpho.org",
              "app.morpho.org/base/market/" in (e.get("market_url") or ""))
        # the collateral ADDRESS is what basescan opens -- a market id is not an address
        ca = e.get("collateral_address")
        check("explorer link uses the collateral address, not the market id",
              bool(ca) and (ca.lower() in (e.get("explorer") or "").lower()),
              "market id is a Morpho-internal key; basescan cannot open it")
        check("market size is attached", e.get("borrow_usd") is not None)
        check("block is attached", e.get("block") is not None)
        check("run ids are attached (both sides)",
              bool(e.get("run")) and bool(e.get("prev_run")))
        check("nothing is invented for a missing field",
              e.get("oracle_type") is None or isinstance(e.get("oracle_type"), str))

    print("\n=== 6c. the enriched table is on the page at full width ===")
    page = os.path.join(ROOT, "report.html")
    if os.path.exists(page):
        h = open(page).read()
        i = h.find("class='dense'")
        check("dense transition table present", i > 0)
        if i > 0:
            j = h.find("</table>", i)
            tbl = h[i:j]
            heads = re.findall(r"<th[^>]*>(.*?)</th>", tbl, re.S)
            check("at least 15 columns (%d)" % len(heads), len(heads) >= 15)
            for want in ("venue", "oracle", "borrowed", "liquidity", "links", "collateral"):
                check("column present: %s" % want,
                      any(want in re.sub(r"<[^>]+>", "", x).lower() for x in heads))
            check("basescan links rendered (%d)" % tbl.count("basescan.org/address/"),
                  tbl.count("basescan.org/address/") > 0)
            check("morpho links rendered (%d)" % tbl.count("app.morpho.org/base/market/"),
                  tbl.count("app.morpho.org/base/market/") > 0)
            # ROWS THAT CANNOT HAVE LINKS, COUNTED RATHER THAN ASSUMED. The old form allowed a
            # slack of 2: the header row plus one. MEASURED today the table has 67 <tr> and 64
            # links -- three rows carry none, and all three are legitimate:
            #   * the header row, which the <tr> count includes
            #   * membership-change events ("1 market present in the previous run is absent",
            #     "1 new market appeared"). Those describe a SET difference, not a market, so they
            #     have no market_id and therefore no contract links by construction.
            # The slack was calibrated when there were ZERO membership events, so a legitimate
            # change made the assertion fail. Count the exemptions instead of hardcoding them.
            header_rows = tbl.count("<th")
            membership = tbl.count("market(s) present in") + tbl.count("market(s) appeared")
            links = tbl.count("basescan.org/address/")
            check("every data row has links (or is a header / membership event)",
                  links >= tbl.count("<tr") - 1 - membership,
                  "%d <tr>, %d links, %d membership row(s)" % (tbl.count("<tr"), links, membership))

    print("\n=== 7. the MCP declares its read-only nature ===")
    # ASK THE MODULE, NOT THE FILE. These asserted substrings of mcp_server.py's TEXT, so a
    # comment containing "read-only" would satisfy the first and a reformat could break the
    # second. Import it and read the OBJECTS the tests are actually about: the docstring (a real
    # runtime value) and the tool descriptions the server publishes.
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("_mcp_under_test", mcp)
    mod = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        check("module imports without side effects", True)
    except Exception as e:
        check("module imports without side effects", False, str(e)[:90])
        mod = None
    if mod is not None:
        doc = (mod.__doc__ or "").lower()
        check("states that no tool writes or spends", "read-only" in doc,
              "checked the MODULE DOCSTRING, not the file text")
        # THE FRAMING MUST REACH THE CALLER. It lives in the dict returned by tool_get_changes(),
        # so CALL it and read the response -- that is the object an MCP client receives. Grepping
        # for the phrase would pass even if the function never returned it.
        got = None
        if hasattr(mod, "tool_get_changes"):
            try:
                got = mod.tool_get_changes({})
            except Exception as e:
                check("tool_get_changes() callable", False, str(e)[:80])
        if isinstance(got, dict):
            fr = str(got.get("framing", ""))
            check("the non-predictive framing is IN the returned payload",
                  "not exploit prevention" in fr,
                  "the caller must receive the framing, not merely have it near the code")
            check("the payload reports unchecked checks alongside the log",
                  "unchecked" in got, "got keys %r" % sorted(got)[:6])
            check("the payload carries the log", "log" in got or "n_intervals" in got)
        else:
            check("tool_get_changes() returns a dict", False, "got %r" % type(got).__name__)

    print("\n=== 8. the What-changed section is on the page ===")
    page = os.path.join(ROOT, "report.html")
    if os.path.exists(page):
        h = open(page).read()
        check("section present", "What changed" in h)
        check("transition-log framing present", "not an exploit warning" in h)
        check("has a watch section", "data-section='watch'" in h)
        check("UNCHECKED is shown when present", "could not" in h and "ORACLE_FLIP" in h,
              "silence from an unchecked detector must not read as stability")
        # A stale gap must be labelled as HISTORY, not shown as a live warning. Measured: 7
        # records from ONE backfill 17 hours earlier kept the banner on forever, while every one
        # of the 56 records logged the next day reported no gap at all. Assert the distinction
        # exists in the markup, so a regression to the single-bucket version fails here.
        check("a gap that ended is labelled by its age, not shown as current",
              ("intervals ago" in h) or ("could not run in the last" in h),
              "the banner must say WHEN a check was blind, or it cannot be told from a live gap")
    else:
        check("report.html exists", False)

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all run-history and MCP assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

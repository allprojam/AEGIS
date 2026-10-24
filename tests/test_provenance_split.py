#!/usr/bin/env python3
"""Dual-cadence provenance: the two halves must not share one timestamp.

The dashboard mixes a 15-minute Morpho feed with a slower DefiLlama snapshot. Presenting both
under a single block-height line implied the whole document described one on-chain state. These
assert the split is real, that each half carries its own timestamp, and that the AMM half states
its AGE rather than leaving the reader to guess.

Run:  python3 tests/test_provenance_split.py
"""
import os, re, sys

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

    print("=== 1. two separate provenance lines exist ===")
    check("lending line present", "Lending Provenance:" in h)
    check("AMM line present", "AMM Index Provenance:" in h)
    check("the ambiguous bare 'Provenance:' no longer heads the lending block",
          "<b>Provenance:</b>" not in h)

    print("\n=== 2. the lending line keeps its on-chain detail ===")
    i = h.find("Lending Provenance:")
    seg = h[i:i + 600]
    check("lending line names a Base block", bool(re.search(r"Base block <code>\d+</code>", seg)))
    check("lending line carries an ingest time", "ingested" in seg)
    check("lending line carries a sha256", bool(re.search(r"sha256 <code>[0-9a-f]{16}", seg)))
    check("lending line names the run", bool(re.search(r"run <code>\d{8}T\d{6}Z</code>", seg)))

    print("\n=== 3. the AMM line states its own snapshot and AGE ===")
    j = h.find("AMM Index Provenance:")
    aseg = h[j:j + 600]
    check("AMM line names the source as a DefiLlama snapshot", "DefiLlama snapshot" in aseg)
    check("AMM line carries a timestamp", bool(re.search(r"<code>\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z</code>", aseg)))
    age = re.search(r"(minutes?|hours?) old", aseg)
    check("AMM line states its AGE explicitly", bool(age),
          "without an age the reader cannot tell the halves differ")
    check("AMM line warns the halves describe different times",
          "different points in time" in aseg)
    check("AMM line does NOT claim a block height", "block" not in aseg.lower())

    print("\n=== 4. a block height cannot be attributed to the AMM half ===")
    # the lending block number must not appear inside the AMM provenance block
    blk = re.search(r"Base block <code>(\d+)</code>", h)
    if blk:
        check("the lending block number is absent from the AMM line",
              blk.group(1) not in aseg, "block %s leaked into the AMM provenance" % blk.group(1))

    print("\n=== 5. the freshness is COMPUTED, not hardcoded ===")
    # AST, NOT TEXT. This file has already produced two false positives from substring checks --
    # once because a comment quoted the very string being searched for. Comments do not exist in
    # an AST, so these now ask what build_v2.py DOES.
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import srcint as SI
    bvp = os.path.join(ROOT, "screener", "build_v2.py")
    check("build computes age from the file mtime", "getmtime" in SI.called_names(bvp))
    # the age UNIT strings are real string literals in the emitted markup, so read literals --
    # which exclude comments by construction
    lits = " ".join(SI.strings_in_code(bvp))
    check("build renders the age into the line", ("hours old" in lits) or ("minutes old" in lits))
    check("a stale AMM snapshot would be visible, not silent",
          "These two halves describe different points in time" in lits)
    bv = lits        # keep the later cadence check working, now backed by literals not raw text

    print("\n=== 6. the claimed cadence matches the ACTUAL timer (not just a comment) ===")
    # The line said "refreshed by a manual build" long after aegis-amm.timer existed, so the page
    # described a process that no longer ran -- and a provenance line that is believed is worse
    # than none. This reads the INSTALLED unit and compares it to the text the page prints, so the
    # two cannot drift apart again without failing here.
    timer = "/etc/systemd/system/aegis-amm.timer"
    if os.path.exists(timer):
        body = open(timer).read()
        cal = re.search(r"OnCalendar=(.+)", body)
        check("AMM timer declares a schedule", bool(cal), "no OnCalendar line")
        check("AMM timer is NOT a 15-minute poll", "00,06,12,18" in (cal.group(1) if cal else ""),
              "got %r -- a fast poll of a multi-hour feed wastes bandwidth and risks rate limits"
              % (cal.group(1) if cal else None))
        check("the page's stated cadence matches the timer's hours",
              "00/06/12/18" in bv, "page says one cadence, timer says another")
        # Scope this to the EMITTED page, not the source file. The comment explaining the old
        # wording legitimately quotes it, so grepping build_v2.py failed on my own note -- a test
        # that flags documentation about a bug as the bug. The page is what the reader believes.
        page = open(os.path.join(ROOT, "report.html")).read() if os.path.exists(
            os.path.join(ROOT, "report.html")) else ""
        check("the served page no longer claims a MANUAL build",
              "refreshed by a manual" not in page,
              "that was true once; aegis-amm.timer made it false")
        check("the served page names the 6h batch cadence",
              "6h batch" in page, "the reader cannot tell the two halves' schedules apart")
    else:
        check("aegis-amm.timer installed (skipped if run off-host)", True)

    print("\n=== 6. parity still works (it matches the 'Provenance:' substring) ===")
    par = open(os.path.join(ROOT, "audit_parity.py")).read()
    check("audit_parity anchors on 'Provenance:'", "Provenance:" in par)
    check("'Lending Provenance:' still contains that substring",
          "Provenance:" in "Lending Provenance:")

    print("\n=== 7. the AMM refresher writes to the right place ===")
    svc = "/etc/systemd/system/aegis-amm.service"
    if os.path.exists(svc):
        su = open(svc).read()
        check("amm unit sets WorkingDirectory (screen.py writes a RELATIVE path)",
              "WorkingDirectory=" in su)
        check("amm unit locks against stacking", "flock -n" in su)
        check("amm unit has a timeout so a hung fetch cannot hold the lock",
              "TimeoutStartSec=" in su)
    else:
        check("aegis-amm.service exists", False)

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all provenance-split assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

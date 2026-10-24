#!/usr/bin/env python3
"""No shadow tree: a module maintained in two places will eventually be edited in the dead copy.

This project hit that three times:
  * runs/ split-brain      -- systemd wrote to root/runs while the dashboard read screener/runs
  * lending_dashboard.py   -- the edit landed in the root copy; build_v2 imported from screener/
  * index.html copy-race   -- a manual cp raced a background build

The fix is structural, not a rule: every duplicated module is now a SYMLINK to one canonical
file, so editing either path edits the same inode. These assertions keep it that way -- if
someone later copies a file back into place, the drift guard fails immediately instead of
silently serving stale behaviour.

Run:  python3 tests/test_no_shadow_tree.py
"""
import os, sys

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
    scr = os.path.join(ROOT, "screener")

    print("=== 1. duplicated modules are symlinks, not copies ===")
    dupes, copies, links = [], [], []
    # EXTENDED TO .html. The guard only checked .py, so screener/index.html survived as a REAL
    # COPY for 8 hours while screener/report.html was a symlink. http.server serves index.html at
    # "/", so the URL people actually open showed a stale run while /report.html showed current
    # -- two front doors, one page, different data. The extension list is the bug: any artifact
    # kept in two places can drift, whatever its suffix.
    ARTIFACT_EXT = (".py", ".html", ".js", ".cjs", ".json", ".md")
    for f in sorted(os.listdir(ROOT)):
        if not f.endswith(ARTIFACT_EXT):
            continue
        if f.endswith(".json") and f in ("package-lock.json",):
            continue
        cand = os.path.join(scr, f)
        if os.path.exists(cand) or os.path.islink(cand):
            dupes.append(f)
            if os.path.islink(cand):
                links.append(f)
            else:
                copies.append(f)
    check("modules present in both trees: %d" % len(dupes), len(dupes) > 0)
    check("all of them are symlinks (%d)" % len(links), not copies,
          "real copies that can drift: %s" % copies)

    print("\n=== 2. each symlink resolves to the root file (one canonical source) ===")
    wrong = []
    for f in links:
        target = os.path.realpath(os.path.join(scr, f))
        if target != os.path.realpath(os.path.join(ROOT, f)):
            wrong.append((f, target))
    check("every symlink points at the root copy", not wrong, str(wrong[:3]))

    print("\n=== 3. the duplicate tests are symlinked to tests/ ===")
    tcopy = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tests"))):
        if f == "__pycache__" or f.startswith("."):
            continue          # a cache dir is not a duplicated module
        cand = os.path.join(scr, f)
        if os.path.exists(cand) or os.path.islink(cand):
            if not os.path.islink(cand):
                tcopy.append(f)
    check("no real test-file copies left in screener/", not tcopy,
          "copies: %s" % tcopy)

    print("\n=== 4. an edit through either path is the same file (live proof) ===")
    probe = os.path.join(ROOT, "lending_dashboard.py")
    mirror = os.path.join(scr, "lending_dashboard.py")
    check("the probe pair exists", os.path.exists(probe) and os.path.exists(mirror))
    if os.path.exists(probe) and os.path.exists(mirror):
        check("same inode", os.stat(probe).st_ino == os.stat(mirror).st_ino,
              "different inodes means two files, and they will drift")

    print("\n=== 5. the shared data dir is a symlink too ===")
    runs_link = os.path.join(scr, "runs")
    check("screener/runs is a symlink", os.path.islink(runs_link))
    if os.path.islink(runs_link):
        check("it resolves to the root runs/",
              os.path.realpath(runs_link) == os.path.realpath(os.path.join(ROOT, "runs")))

    print("\n=== 5b. data files and docs are symlinked too, not copied ===")
    # Found after the first pass: 21 more real copies (morpho_markets.json differed by 24KB,
    # lending_screen.json by 45 bytes, report.html by 75KB). Data drifting is worse than code
    # drifting -- the dashboard would render one snapshot while the daemon wrote another.
    stray = []
    for f in sorted(os.listdir(ROOT)):
        if f in ("screener", "node_modules", "runs", "tests", "audits", "__pycache__"):
            continue
        cand = os.path.join(scr, f)
        if os.path.isfile(cand) and not os.path.islink(cand):
            stray.append(f)
    check("no real file copies left in screener/ at all", not stray,
          "copies that can drift: %s" % stray[:6])

    print("\n=== 5c. screener-only stray regular files (the index.html blind spot) ===")
    # THE BUG THIS CATCHES: screener/index.html was a REAL FILE, a byte copy of ../report.html.
    # index.html exists ONLY in screener/ -- never in ROOT -- so section 1 and section 5b, which
    # both walk os.listdir(ROOT), never looked at it; 5b additionally skipped "screener"
    # outright. `python3 -m http.server` serves index.html at "/", so the URL people actually
    # open showed an 8-hour-stale run while /report.html was current: two front doors, one page,
    # different data. The root cause is the iteration base, not the extension filter.
    #
    # The rule: walk screener/ itself and deny by default. Every entry that is a real regular
    # file is a stray (it can drift and be served stale) unless its name is justified below.
    # Symlinks are the desired state and are fine; directories (incl. __pycache__) are skipped.
    # A NAME allowlist, not a content check: screener/index.html has no ROOT counterpart to
    # compare against, and a byte-identical copy stops being byte-identical the moment the
    # canonical file moves on -- content comparison goes blind exactly when drift turns
    # dangerous. Verified with `ls -la screener/` on this checkout: 23 real regular files, none
    # having a name counterpart in ROOT and none a content twin anywhere under ROOT/ or tests/
    # (repo-wide sha256 scan: 0 twins). They are screener-only canonical artifacts with no
    # second copy to drift from, so allowlisting them is not a blanket exemption.
    SCREENER_ONLY_OK = {
        # canonical screener entry point -- the one path systemd may ExecStart
        "screen.py",
        # canonical pool data: written here, read here, no ROOT counterpart
        "results.json",
        # screener-local UI / API assets, served only from this directory
        "app.js", "table.js", "audit_core.js",
        "build_report.py", "build_v2.py", "mcp_server.py", "report.py",
        "auditread.py", "run_audits.py", "audit_core_lite.py", "test_parity.py",
        # screener-local docs / snapshots
        "AUDIT_READER.md", "BUILD_LOG.md", "PRODUCT.md", "REVIEW_RESPONSE.md",
        # screener-local data. REVIEW CANDIDATES: these look like run artifacts that belong
        # under runs/, and results.json.bak is a backup that will silently go stale.
        "results.json.bak", "addr.json", "audited.json", "audit_reads.json",
        "data.json", "aegis.db",
        # The snapshot store and its reader. These CANNOT live at the root: they resolve
        # screener/snapshots/ relative to their OWN directory, so a root copy would silently point
        # at a different (empty) store and every diff would report "no baseline". The allowlist
        # entry is the honest fix -- the alternative, symlinking them, would break that resolution.
        "snapshots.py", "backfill_pool_ids.py",
        # Exit-impact and forward-stress analysis. These are screener-local for the same reason
        # screen.py is: they read screener/results.json and screener/runs/ by relative path, so a
        # root copy would silently read a DIFFERENT and possibly staler input set. The .json files
        # are generated artefacts of those modules, sitting beside their inputs like results.json.
        "exit_impact.py", "exit_impact.json",
        "stress_forward.py", "stress_forward.json",
        # Runway to the 95% withdrawal lock. Screener-local for the same reason as the two above:
        # it reads screener/runs/<iso>/markets.json by relative path, so a root copy would read a
        # different run than the one being served.
        "runway.py",
        # Venue/category classification. Screener-local: reads screener/results.json and caches
        # the protocol category map beside it, so a root copy would read a different pool set.
        "venues.py",
        # DEX pool fee/volume feed. Screener-local like venues.py: writes dex_pools.json and its
        # cache beside itself from GeckoTerminal, so a root copy would read/write a different set.
        "dex_pools.py", "dex_pools.json", "dex_pools_cache.json",
        # The cached slug -> category map from api.llama.fi/protocols. Regenerated on demand with
        # `venues.py --refresh`; screener-local so it version-locks with the pool data it joins to.
        "protocol_categories.json",
        # Regime segmentation. Screener-local: it reads the runs ledger by relative path via
        # run_history, so a root copy would read a different run than the one being served.
        "regimes.py",
        # Anomalous-velocity alerts. Screener-local like regimes.py: it reads runs/<iso>/ via
        # run_history relative to its own directory. velocity.json is its generated artefact,
        # beside its input the way regimes.json sits beside regimes.py.
        "velocity.py", "velocity.json",
        # Position-risk salvage (read-only sensor math extracted from the legacy daemon). It is
        # pure stdlib and has no data file, but it is screener-local so the MCP's tool_position_risk
        # can import it next to __file__. A root copy would drift from the served code.
        "position_risk.py",
        # Liquidation ingest. Screener-local like every runs/-reading module: it walks
        # runs/<iso>/ relative to its own directory to attach flag coverage, so a root copy would
        # read a different run than the one being served. liquidations.json is its cache/artefact
        # (17MB+, one per-store), sitting beside its inputs the way exit_impact.json does.
        "liquidations.py", "liquidations.json",
        # Forward-test ledger (task B+). Screener-local for the same reason: it walks
        # runs/<iso>/ and liquidations.json relative to its own directory, so a root copy would
        # read a different run than the one being served. forward_test.json is its append-only
        # artefact, like exit_impact.json and runway.json.
        "forward_test.py", "forward_test.json",
        # Portfolio correlation. Screener-local for the SAME reason as runway.py and regimes.py:
        # it reads runs/<iso>/ and price_cache.json relative to its own directory, so a root
        # copy would read a different run than the one being served. Its output
        # (portfolio_corr.json) is a generated artefact sitting beside its inputs, like
        # exit_impact.json and runway.json.
        "portfolio_corr.py", "portfolio_corr.json",
        # Signed-token issuance and its spend ledger. Screener-local: both paths resolve next to
        # this file so a root copy would read a DIFFERENT secret and a different ledger, which
        # would silently invalidate every token issued by the other copy.
        "tokens.py",
        # The signing secret and the spend ledger. These CANNOT be symlinked or moved: both are
        # resolved relative to tokens.py, so a root copy would load a DIFFERENT secret and a
        # different ledger and would silently invalidate every token the other copy issued, or
        # refund spent credits. That is exactly the drift this test exists to prevent, and here
        # the two-file split IS the bug rather than the fix.
        "token_secret.key", "token_ledger.json", "token_ledger.lock",
    }
    real_only = []
    for e in sorted(os.listdir(scr)):
        cand = os.path.join(scr, e)
        if os.path.islink(cand):
            continue                     # symlink -> canonical file lives elsewhere, fine
        if os.path.isdir(cand) or not os.path.isfile(cand):
            continue                     # __pycache__, tests/, fixtures/: dirs are skipped
        if e in SCREENER_ONLY_OK:
            continue
        real_only.append(e)
    check("no un-allowlisted real regular files in screener/ (%d allowlisted, %d stray)"
          % (len(SCREENER_ONLY_OK), len(real_only)), not real_only,
          "stray real files living ONLY in screener/, so the ROOT-based loops above can never "
          "see them: %s. A real copy in screener/ can drift and be served stale -- index.html "
          "did exactly this: an 8-hour-old copy of report.html was served at / by http.server "
          "while /report.html was current. Remove the copy and symlink it to the canonical "
          "file, or add it to SCREENER_ONLY_OK with a reason."
          % ", ".join(real_only))
    missing = sorted(SCREENER_ONLY_OK - set(os.listdir(scr)))
    check("the screener allowlist has no dead entries (%d names)" % len(SCREENER_ONLY_OK),
          not missing, "allowlisted names absent from screener/: %s" % missing)

    print("\n=== 6. systemd runs canonical paths ===")
    units = []
    for name in ("aegis-forward.service", "aegis-amm.service"):
        p = os.path.join("/etc/systemd/system", name)
        if os.path.exists(p):
            units.append((name, open(p).read()))
    check("systemd units found (%d)" % len(units), len(units) > 0)
    for name, body in units:
        bad = [ln for ln in body.splitlines()
               if ln.startswith(("ExecStart", "ExecStartPre"))
               and "/screener/" in ln and not ln.strip().endswith("screen.py")]
        check("%s references no screener/ duplicate" % name, not bad, str(bad[:2]))

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all shadow-tree assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

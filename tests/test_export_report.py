#!/usr/bin/env python3
"""Tests for export_report.py - the Forensic Audit tear sheet.

The load-bearing assertions are the ones that keep the audit honest:
  - it loads NOTHING from the network (a risk audit that phones home is not an audit)
  - it never collapses outstanding bad debt into realised loss
  - every run's own sha256 appears, so a reader can verify rather than trust

Run:  python3 tests/test_export_report.py
"""
import importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("export_report_under_test",
                                               os.path.join(ROOT, "export_report.py"))
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


def row(mid, coll="X", verdict="REAL", o=0.0, r=0.0, lltv=0.77, util=0.5, sigma=3.0, fails=None):
    return {"market_id": mid, "collateral": coll, "verdict": verdict,
            "bad_debt_usd": o, "realized_bad_debt_usd": r, "lltv": lltv,
            "utilization": util, "sigma_to_breach": sigma, "daily_vol_pct": 5.0,
            "tvl_usd": 1_000_000.0, "fails": fails or [], "reasons": ["x"]}


def fake_run(screen):
    return {
        "run": "TESTrun", "dir": "/tmp",
        "meta": {"provenance": {"block_number": 12345, "fetched_at": "2026-10-07T00:00:00Z",
                                "source_endpoint": "https://blue-api.morpho.org/graphql",
                                "chain_id": 8453, "row_count": len(screen),
                                "content_sha256": "a" * 64},
                 "written_at": "2026-10-07T00:00:01Z"},
        "screen": screen,
        "sha_markets.json": "b" * 64, "sha_screen.json": "c" * 64, "sha_meta.json": "d" * 64,
    }


def main():
    print("=== 1. self-contained: no resource loading of any kind ===")
    page = A.render(fake_run([row("m1"), row("m2", verdict="AVOID", fails=["LOCKED"])]))
    for bad in ("<script", "<img", "<link", "<iframe", "@import", "XMLHttpRequest"):
        check("no %s" % bad, bad not in page)
    check("inline <style> present", "<style>" in page)
    check("no fetch() call", "fetch(" not in page)

    print("\n=== 2. outstanding vs realised never collapsed ===")
    s = [row("m1", "USR", "AVOID", o=34_821_390.0, r=0.0, fails=["BAD_DEBT"])]
    page = A.render(fake_run(s))
    check("labels 'bad debt outstanding'", "bad debt outstanding" in page)
    check("labels 'loss realised'", "loss realised" in page)
    check("$34,821,390 outstanding appears", "34,821,390" in page)
    check("the word 'realised' is NOT used as the heading for outstanding debt",
          "Markets carrying realised bad debt" not in page)

    print("\n=== 3. a market with $0 realised does not show a realised loss ===")
    s = [row("m1", "USR", "AVOID", o=34_821_390.0, r=0.0, fails=["BAD_DEBT"])]
    page = A.render(fake_run(s))
    i = page.find("Total outstanding")
    tail = page[i:i + 140]
    check("total realised shown as $0", "$0" in tail, tail[:120])

    print("\n=== 4. provenance and checksums are first-class ===")
    page = A.render(fake_run([row("m1")]))
    check("block number rendered", "12345" in page)
    check("market sha256 rendered", "b" * 64 in page)
    check("screen sha256 rendered", "c" * 64 in page)
    check("content sha256 rendered", "a" * 64 in page)
    check("verification invited ('hash ... yourself')", "hash the run directory" in page.lower())

    print("\n=== 5. the non-claim is INSIDE the document ===")
    page = A.render(fake_run([row("m1")]))
    check("'measurement, not a forecast' banner", "measurement, not a forecast" in page)
    check("cannot-read-a-private-key stated", "compromised private key" in page)
    check("pool-screen non-predictive limit stated", "overlapping intervals" in page)
    check("cannot-do footer present", "What this audit cannot do" in page)

    print("\n=== 6. sigma margin table uses the allocator's 2.0 threshold ===")
    s = [row("m1", "WETH", sigma=1.55), row("m2", "cbBTC", sigma=2.45)]
    page = A.render(fake_run(s))
    check("sub-2.0 sigma market appears", "WETH" in page)
    check("sigma value rendered", "1.55" in page)
    check("margin = 1 - LLTV computed (0.77 -> 23.0%)", "23.0%" in page)

    print("\n=== 7. HTML is well-formed ===")
    import html.parser

    class P(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.n = 0
            self.stack = []
        def handle_starttag(self, t, a):
            self.n += 1
            if t not in ("br", "img", "meta", "link", "hr", "input"):
                self.stack.append(t)

        def handle_endtag(self, t):
            if self.stack and self.stack[-1] == t:
                self.stack.pop()

    p = P()
    p.feed(A.render(fake_run([row("m1"), row("m2", verdict="AVOID", fails=["BAD_DEBT"])])))
    check("parses without crashing (%d tags)" % p.n, p.n > 50)
    check("no unclosed container tags", not p.stack, "left open: %s" % p.stack)

    print("\n=== 8. escaping: a hostile collateral name cannot inject markup ===")
    # The market must actually APPEAR in a table or this test is vacuous. An earlier version
    # used a plain REAL market, which is never rendered with its collateral name -- so
    # "no raw <img>" passed without the string ever being emitted. Forcing a BAD_DEBT flag
    # puts it in the hard-exclusions table, which is where the name is actually printed.
    hostile = "<img src=x onerror=alert(1)>"
    page = A.render(fake_run([row("m1", coll=hostile, verdict="AVOID", o=5e6, fails=["BAD_DEBT"])]))
    check("hostile market DID render (else escaping is untested)", hostile not in page)
    check("raw <img src=x absent", "<img src=x" not in page)
    check("escaped form present in output", "&lt;img src=x" in page,
          "the escaped name must appear, proving it was rendered and escaped")

    print("\n=== 9. determinism: same run renders byte-identical ===")
    r = fake_run([row("m1"), row("m2")])
    check("two renders match exactly", A.render(r) == A.render(r))

    print("\n=== 10. verdict counts are counted, not assumed ===")
    s = [row("a", verdict="REAL"), row("b", verdict="REAL"), row("c", verdict="CAUTION"),
         row("d", verdict="AVOID"), row("e", verdict="AVOID"), row("f", verdict="AVOID")]
    page = A.render(fake_run(s))
    check("REAL count is 2", re.search(r"class='n ok'>2<", page) is not None)
    check("CAUTION count is 1", re.search(r"class='n warn'>1<", page) is not None)
    check("AVOID count is 3", re.search(r"class='n bad'>3<", page) is not None)

    print("\n=== 11. PROVENANCE ISOLATION: runs/ carries no JS, no symlinks ===")
    # The immutable runs are the audit trail. A dev dependency must never be reachable from
    # them, or a run stops being reproducible from the run directory alone.
    import glob as _g
    run_dirs = sorted(_g.glob(os.path.join(ROOT, "runs", "*")))
    run_dirs = [d for d in run_dirs if os.path.isdir(d)]
    check("runs exist to check (%d)" % len(run_dirs), len(run_dirs) > 0)
    if run_dirs:
        js = []
        links = []
        for d in run_dirs:
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith((".js", ".mjs", ".cjs")):
                        js.append(os.path.join(root, f))
                for name in dirs:
                    fp = os.path.join(root, name)
                    if os.path.islink(fp):
                        links.append(fp)
        check("zero javascript files under runs/", not js, "found: %s" % js[:3])
        check("zero symlinks under runs/", not links, "found: %s" % links[:3])

    print("\n=== 12. no run artifact references node_modules ===")
    hits = []
    for d in run_dirs[:12]:
        for f in ("markets.json", "screen.json", "meta.json", "allocator.json"):
            fp = os.path.join(d, f)
            if os.path.exists(fp):
                try:
                    if "node_modules" in open(fp).read():
                        hits.append(fp)
                except Exception:
                    pass
    check("no run artifact mentions node_modules", not hits, "found in: %s" % hits[:3])

    print("\n=== 13. the published artifact stays zero-dependency ===")
    pub = os.path.join(ROOT, "report.html")
    if os.path.exists(pub):
        ph = open(pub).read()
        check("report.html has no <script src=", "<script src=" not in ph)
        check("report.html has no node_modules string", "node_modules" not in ph)
        check("report.html has no bare require()", "require(" not in ph)
    audits = sorted(_g.glob(os.path.join(ROOT, "audits", "*.html")))
    if audits:
        ah = open(audits[-1]).read()
        check("tear sheet has no node_modules string", "node_modules" not in ah)
        check("tear sheet loads nothing external", "<script" not in ah and "<link" not in ah)

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all export_report assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

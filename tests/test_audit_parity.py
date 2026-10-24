#!/usr/bin/env python3
"""Tests for audit_parity.py - keeping the two renderers honest.

The load-bearing case is RUN_MISMATCH: report.html tracks the newest run while an audit is
pinned to one run, so comparing them across different runs fails for a LEGITIMATE reason.
Reporting that as a disagreement would produce a false alarm -- the kind that gets a check
switched off, which is worse than never having it.

Run:  python3 tests/test_audit_parity.py
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("audit_parity_under_test",
                                               os.path.join(ROOT, "audit_parity.py"))
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


def w(path, body):
    open(path, "w").write(body)
    return path


def main():
    import tempfile
    d = tempfile.mkdtemp()

    print("=== 1. RUN_MISMATCH is not a disagreement ===")
    dash = {"run": "20260101T000000Z", "markets": 60, "REAL": 18, "CAUTION": 8,
            "AVOID": 34, "outstanding": 1.0, "realised": 2.0}
    aud = dict(dash, run="20260102T000000Z")
    v, diffs = A.compare(dash, aud)
    check("different runs -> RUN_MISMATCH, not DISAGREE", v == "RUN_MISMATCH", v)
    check("the mismatch names the run field", diffs and diffs[0][0] == "run", str(diffs))

    print("\n=== 2. same run, equal numbers -> AGREE ===")
    v, diffs = A.compare(dash, dict(dash))
    check("identical -> AGREE", v == "AGREE", str(diffs))

    print("\n=== 3. same run, different numbers -> DISAGREE (a real bug) ===")
    bad = dict(dash); bad["REAL"] = 19
    v, diffs = A.compare(dash, bad)
    check("one field differs -> DISAGREE", v == "DISAGREE", v)
    check("the differing field is named", any(f == "REAL" for f, _, _ in diffs), str(diffs))

    print("\n=== 4. bad-debt fields are compared, not skipped ===")
    bad = dict(dash); bad["outstanding"] = 999.0
    v, diffs = A.compare(dash, bad)
    check("outstanding difference is caught", v == "DISAGREE" and any(f == "outstanding" for f, _, _ in diffs))
    bad = dict(dash); bad["realised"] = 999.0
    v, diffs = A.compare(dash, bad)
    check("realised difference is caught", v == "DISAGREE" and any(f == "realised" for f, _, _ in diffs))

    print("\n=== 5. a field absent on one side is not a disagreement ===")
    sparse = {"run": dash["run"], "REAL": 18}          # no outstanding/realised
    v, diffs = A.compare(dash, sparse)
    check("missing field does not produce a false DISAGREE", v == "AGREE", str(diffs))

    print("\n=== 6. dashboard parsing is SCOPED to the lending section ===")
    # AMM block first with REAL=74, lending block after with REAL=18. A naive parser returns 74.
    page = ("<html><body>"
            "<h2>Liquidity pools</h2><div class='big'>"
            "<div class='card'><div class='n ok'>74</div><div class='l'>REAL</div></div>"
            "<div class='card'><div class='n warn'>100</div><div class='l'>CAUTION</div></div>"
            "<div class='card'><div class='n bad'>200</div><div class='l'>AVOID</div></div>"
            "</div>"
            "<h2>Lending markets &mdash; current state risk assessment</h2>"
            "<div class='sub'>Seven structural checks applied to <b>60</b> USDC-denominated morpho</div>"
            "<div class='big'>"
            "<div class='card'><div class='n ok'>18</div><div class='l'>REAL</div></div>"
            "<div class='card'><div class='n warn'>8</div><div class='l'>CAUTION</div></div>"
            "<div class='card'><div class='n bad'>34</div><div class='l'>AVOID</div></div>"
            "</div>"
            "<b>Provenance:</b> block <code>1</code> &middot; run <code>20260101T000000Z</code>"
            "</body></html>")
    p = w(os.path.join(d, "dash.html"), page)
    got = A.extract_dashboard(p)
    check("REAL is 18 (lending), NOT 74 (AMM)", got["REAL"] == 18, "got %s" % got["REAL"])
    check("CAUTION is 8 (lending), NOT 100 (AMM)", got["CAUTION"] == 8, "got %s" % got["CAUTION"])
    check("markets parsed as 60", got["markets"] == 60, "got %s" % got["markets"])
    check("run id parsed", got["run"] == "20260101T000000Z", "got %s" % got["run"])

    print("\n=== 7. audit parsing reads the scorecard and the bad-debt totals ===")
    audit_page = ("<html><body>run <code>20260101T000000Z</code>"
                  "<div class='sub'>60 markets screened</div>"
                  "<div class='card'><div class='n ok'>18</div><div class=l>REAL</div></div>"
                  "<div class='card'><div class='n warn'>8</div><div class=l>CAUTION</div></div>"
                  "<div class='card'><div class='n bad'>34</div><div class=l>AVOID</div></div>"
                  "<div class=sub>Total outstanding $36,394,233 &middot; total realised $132. "
                  "<b>The realised figure is the loss actually taken.</b></div>"
                  "</body></html>")
    a = w(os.path.join(d, "audit.html"), audit_page)
    ga = A.extract_audit(a)
    check("audit REAL parsed", ga["REAL"] == 18, "got %s" % ga["REAL"])
    check("audit CAUTION parsed", ga["CAUTION"] == 8, "got %s" % ga["CAUTION"])
    check("audit markets parsed", ga["markets"] == 60, "got %s" % ga["markets"])
    check("outstanding is 36394233, NOT 132", ga["outstanding"] == 36394233.0, "got %s" % ga["outstanding"])
    check("realised is 132, NOT 36394233", ga["realised"] == 132.0, "got %s" % ga["realised"])

    print("\n=== 8. outstanding and realised are not transposed ===")
    v, diffs = A.compare(
        {"run": "r", "markets": 60, "REAL": 18, "CAUTION": 8, "AVOID": 34,
         "outstanding": 36394233.0, "realised": 132.0},
        {"run": "r", "markets": 60, "REAL": 18, "CAUTION": 8, "AVOID": 34,
         "outstanding": 132.0, "realised": 36394233.0})
    check("a swap of the two bad-debt fields is caught",
          v == "DISAGREE" and len(diffs) == 2, str(diffs))

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all audit_parity assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

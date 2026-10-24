#!/usr/bin/env python3
"""audit_parity.py - assert report.html and audits/<iso>.html agree on the same run.

TWO RENDERERS, ONE DATASET. `report.html` (the live dashboard) and `export_report.py` (the
standalone tear sheet) both render Morpho screening numbers. They are separate code paths, so
they can silently disagree -- and a reader comparing the two would find the discrepancy, not us.

This module provides:
  1. extract_audit(path)     the summary numbers an audit file ADVERTISES
  2. extract_dashboard(path) the summary numbers the dashboard advertises
  3. compare(dash, audit)    assert they match, or say exactly how they differ

THE HARD PART IS NOT PARSING, IT IS IDENTITY. `report.html` always reflects the LATEST run, so
comparing it against an audit of an OLDER run fails for a legitimate reason. Parity is only
meaningful when both carry the SAME run id. When they do not, this reports RUN_MISMATCH -- a
staleness finding, not a disagreement. Conflating the two would produce exactly the kind of
false alarm that gets a check switched off.

SECOND TRAP, FOUND WHILE WRITING THIS: `report.html` contains SEVERAL card blocks using the same
labels (`REAL`, `CAUTION`, `AVOID`) -- AMM pools in one section, Morpho markets in another. A
parser taking the first match can compare AMM `REAL` against Morpho `REAL`. The dashboard parser
is therefore scoped to the lending section, not the document.
"""
import html, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _txt(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or ""))


def _num(s):
    try:
        return float(re.sub(r"[^\d.\-]", "", s))
    except Exception:
        return None


def extract_audit(path):
    """Pull the advertised summary out of an audits/<iso>.html tear sheet."""
    h = open(path).read()
    out = {"path": path, "run": None, "markets": None,
           "REAL": None, "CAUTION": None, "AVOID": None,
           "outstanding": None, "realised": None}

    m = re.search(r"run <code>([0-9T]+Z)</code>", h)
    if m:
        out["run"] = m.group(1)
    m = re.search(r"(\d+)\s+markets screened", _txt(h))
    if m:
        out["markets"] = int(m.group(1))

    for label in ("REAL", "CAUTION", "AVOID"):
        m = (re.search(r"class=['\"]n (?:ok|warn|bad)['\"]>(\d+)</div><div class=['\"]l['\"]>%s<" % label, h)
             or re.search(r"class='n (?:ok|warn|bad)'>(\d+)</div><div class=l>%s<" % label, h))
        if m:
            out[label] = int(m.group(1))

    m = re.search(r"Total outstanding \$([\d,]+) &middot; total realised \$([\d,]+)", h)
    if m:
        out["outstanding"] = _num(m.group(1))
        out["realised"] = _num(m.group(2))
    return out


def _lending_section(h):
    """Isolate the Morpho/lending card block.

    report.html holds multiple card blocks with the same REAL/CAUTION/AVOID labels. Taking the
    first match anywhere risks comparing AMM pool counts against lending counts. Anchored on the
    lending heading and terminated at the provenance line.
    """
    i = h.find("current state risk assessment")
    if i < 0:
        return h
    j = h.find("Provenance:", i)
    return h[i:j if j > i else i + 20000]


def extract_dashboard(path):
    """Pull the advertised Morpho summary out of report.html, scoped to the lending section."""
    h = open(path).read()
    sec = _lending_section(h)
    out = {"path": path, "run": None, "markets": None,
           "REAL": None, "CAUTION": None, "AVOID": None,
           "outstanding": None, "realised": None}

    m = re.search(r"run <code>([0-9T]+Z)</code>", h)
    if m:
        out["run"] = m.group(1)

    t = _txt(sec)
    m = re.search(r"Seven structural checks applied to\s+(\d+)\s+USDC-denominated", t)
    if m:
        out["markets"] = int(m.group(1))

    for label in ("REAL", "CAUTION", "AVOID"):
        m = re.search(r"class='n (?:ok|warn|bad)'>(\d+)</div><div class=['\"]l['\"]>%s<" % label, sec)
        if m:
            out[label] = int(m.group(1))
    return out


FIELDS = ("markets", "REAL", "CAUTION", "AVOID", "outstanding", "realised")


def compare(dash, audit):
    """Return (verdict, diffs). Verdict is one of:
         RUN_MISMATCH - different runs; parity meaningless, and that is a staleness finding
         AGREE        - every comparable field matches
         DISAGREE     - same run, different numbers (a real bug)
    """
    if dash.get("run") != audit.get("run"):
        return "RUN_MISMATCH", [("run", dash.get("run"), audit.get("run"))]
    diffs = []
    for f in FIELDS:
        a, b = dash.get(f), audit.get(f)
        if a is None or b is None:
            continue                     # one side does not advertise it: not a disagreement
        try:
            same = abs(float(a) - float(b)) <= 0.01
        except Exception:
            same = (a == b)
        if not same:
            diffs.append((f, a, b))
    return ("AGREE" if not diffs else "DISAGREE"), diffs


def main():
    dash_p = os.path.join(HERE, "report.html")
    ad = os.path.join(HERE, "audits")
    audits = sorted(os.path.join(ad, f) for f in os.listdir(ad) if f.endswith(".html")) \
        if os.path.isdir(ad) else []
    if not os.path.exists(dash_p):
        print("report.html not found; build it first")
        return 1
    if not audits:
        print("no audits/ found; run export_report.py first")
        return 1

    dash = extract_dashboard(dash_p)
    print("=== renderer parity: report.html vs audits/ ===")
    print("  dashboard run: %s   (%s markets)" % (dash["run"], dash["markets"]))
    print()

    rc = 0
    for ap in audits:
        audit = extract_audit(ap)
        verdict, diffs = compare(dash, audit)
        name = os.path.basename(ap)
        if verdict == "RUN_MISMATCH":
            print("  %-30s RUN_MISMATCH" % name)
            print("       dashboard %s  vs  audit %s" % (dash["run"], audit["run"]))
            print("       -> NOT a disagreement. report.html tracks the newest run; this audit")
            print("          is older. Rebuild the dashboard to compare the same run.")
        elif verdict == "AGREE":
            print("  %-30s AGREE" % name)
            for f in ("markets",) + FIELDS[1:]:
                if audit.get(f) is not None:
                    print("       %-12s %s" % (f, audit[f]))
        else:
            print("  %-30s DISAGREE" % name)
            for f, a, b in diffs:
                print("       %-12s dashboard=%s  audit=%s" % (f, a, b))
            rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())

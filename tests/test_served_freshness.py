#!/usr/bin/env python3
"""The served page must be the ONE canonical file, and it must name the newest run.

WHY THIS EXISTS. screener/index.html was a REAL COPY of ../report.html. `python3 -m http.server`
serves index.html at "/", so the URL a person actually opens rendered an 8-hour-old run while
/report.html rendered the current one -- two front doors, one page, different data. Nothing
failed: the build succeeded, the tests passed, the timer ticked. The staleness was invisible
until the two URLs were compared.

test_no_shadow_tree now catches the COPY. This catches the CONSEQUENCE: that the artifact the
server hands out is stale. They are different failures -- a single canonical file can still be
stale if the build is not wired to the timer -- so both are asserted.

Run:  python3 tests/test_served_freshness.py
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


def run_of(path):
    """The newest run stamp the page names."""
    txt = open(path, encoding="utf-8", errors="replace").read()
    stamps = re.findall(r"\b(20\d{6}T\d{6}Z)\b", txt)
    return max(stamps) if stamps else None


def main():
    scr = os.path.join(ROOT, "screener")

    print("=== 1. the served artifacts are symlinks to one canonical file ===")
    for name in ("index.html", "report.html"):
        p = os.path.join(scr, name)
        check("%s is a symlink" % name, os.path.exists(p) and os.path.islink(p),
              "a real copy here can drift and be served stale")

    print("\n=== 2. every served path resolves to the SAME inode ===")
    canon = os.path.join(ROOT, "report.html")
    if os.path.exists(canon):
        ci = os.stat(canon).st_ino
        for name in ("index.html", "report.html"):
            p = os.path.join(scr, name)
            if os.path.exists(p):
                check("%s resolves to report.html" % name, os.stat(p).st_ino == ci,
                      "different inode = a second copy, which is how this broke")

    print("\n=== 3. the served page names the NEWEST committed run ===")
    runs_dir = os.path.join(ROOT, "runs")
    if os.path.isdir(runs_dir) and os.path.exists(canon):
        newest = sorted(d for d in os.listdir(runs_dir)
                        if re.match(r"^\d{8}T\d{6}Z$", d))[-1]
        got = run_of(canon)
        check("report.html names the newest run (%s)" % newest, got == newest,
              "page says %s, newest run is %s -- the dashboard is behind the timer" % (got, newest))
        # and the served copy must agree, not just the canonical one
        idx = os.path.join(scr, "index.html")
        if os.path.exists(idx):
            check("/ serves the same run as /report.html", run_of(idx) == got,
                  "index.html says %s, report.html says %s" % (run_of(idx), got))
    else:
        check("runs/ and report.html exist to compare", False)

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  the served page is current and singular")
    return 0


if __name__ == "__main__":
    sys.exit(main())

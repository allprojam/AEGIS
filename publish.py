#!/usr/bin/env python3
"""publish.py - rebuild the artifacts for the newest run, then verify parity.

Runs after each committed cycle. Three steps, in order, because each depends on the last:

    1. export_report.py   -> audits/<iso>.html   (tear sheet for the newest run)
    2. build_v2.py        -> report.html         (dashboard, tracks the newest run)
    3. audit_parity.py    -> verifies they agree on the same run

WHY THIS EXISTS. The dashboard and the tear sheets are BUILD ARTIFACTS. The timer commits runs
but nothing rebuilt the dashboard, so it went stale within one tick -- it sat four runs behind,
and the parity check reported RUN_MISMATCH for a reason that looked benign. A verification
tripwire that is permanently tripped teaches people to ignore it.

ORDERING MATTERS: build_v2.py resolves the newest run via screener/provenance, so the audit for
that run must exist before parity can return AGREE rather than RUN_MISMATCH.

FAILURE POLICY. A publish failure must NOT invalidate the run: the run is already committed and
replay-verified, and that is the thing of value. This exits non-zero so systemd records the
failure, but the committed run stands either way.

    python3 publish.py            # rebuild + verify
    python3 publish.py --quiet    # only report problems
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"


def run(args, quiet=False):
    r = subprocess.run([PY] + args, capture_output=True, text=True, cwd=HERE, timeout=300)
    if not quiet:
        for line in (r.stdout or "").strip().splitlines()[-4:]:
            print("    " + line)
    if r.returncode != 0:
        for line in (r.stderr or "").strip().splitlines()[-3:]:
            print("    [stderr] " + line)
    return r.returncode, (r.stdout or "")


def newest_run():
    d = os.path.join(HERE, "runs")
    if not os.path.isdir(d):
        return None
    runs = sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)))
    return runs[-1] if runs else None


def main():
    quiet = "--quiet" in sys.argv[1:]
    run_id = newest_run()
    if not run_id:
        print("publish: no runs available")
        return 1

    print("=== publish: %s ===" % run_id)

    print("  [1/3] tear sheet")
    rc1, _ = run([os.path.join(HERE, "export_report.py"), run_id], quiet)

    print("  [2/3] dashboard")
    rc2, _ = run([os.path.join(HERE, "screener", "build_v2.py")], quiet)

    print("  [3/3] parity")
    rc3, out3 = run([os.path.join(HERE, "audit_parity.py")], quiet=True)
    if not quiet:
        for line in out3.strip().splitlines():
            print("    " + line)

    # parity returning 2 means same-run disagreement: a real bug, and the loud one.
    if rc3 == 2:
        print("  PARITY DISAGREEMENT - two renderers report different numbers for one run")
        return 2
    if rc3 != 0:
        print("  parity could not run (rc=%d)" % rc3)
        return rc3
    if "AGREE" not in out3:
        print("  parity found no run both artifacts cover; dashboard may be stale")
        return 3

    print("  ok: tear sheet + dashboard agree on %s" % run_id)
    return 0 if (rc1 == 0 and rc2 == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

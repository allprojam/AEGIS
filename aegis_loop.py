#!/usr/bin/env python3
"""aegis_loop.py - one command, the whole cycle. Sense -> Evaluate -> Reason -> Commit -> Verify.

This wraps aegis_run.py so there is a single entry point to schedule, test and audit. It is
deliberately NOT a daemon: it runs once, does the work, writes an immutable run, verifies it
replays, and exits. Autonomy, if it ever comes, is a timer calling this.

    python3 aegis_loop.py                # full cycle, no model
    python3 aegis_loop.py --reason       # include LLM triage
    python3 aegis_loop.py --quiet        # only print the final line (for cron)
    python3 aegis_loop.py --check        # preflight: verify dependencies and the model

Exit codes:  0 = success and replay verified
             1 = ran, but replay did NOT reproduce
             2 = preflight failed (nothing was written)
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def preflight(need_model=False):
    """Check everything the cycle depends on BEFORE it runs, so a broken dependency is loud.

    This exists because gemma4:12b returns empty strings and NOTHING caught it. A silent
    dependency failure inside a scheduled job is the worst kind: the job reports success.
    """
    problems = []

    for f in ("provenance.py", "morpho_fetch.py", "lending_screen.py", "aegis_run.py"):
        if not os.path.exists(os.path.join(HERE, f)):
            problems.append("missing module: %s" % f)

    try:
        import morpho_fetch as mf
        rows = mf.fetch_markets(3)
        if not rows:
            problems.append("Morpho API returned no markets")
        else:
            print("  [ok] Morpho API: %d markets" % len(rows))
    except Exception as e:
        problems.append("Morpho API unreachable: %s" % str(e)[:70])

    if need_model:
        import aegis_run as ar
        txt, note = ar.llm_triage("Reply with the single word: ok")
        if note:
            problems.append("model check failed: %s" % note)
        else:
            print("  [ok] model %s responded (%d chars)" % (ar.MODEL, len(txt)))

    return problems


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    do_reason = "--reason" in args

    if "--check" in args or not quiet:
        print("=== preflight ===")
        probs = preflight(need_model=do_reason)
        if probs:
            for p in probs:
                print("  [FAIL] %s" % p)
            print("\npreflight failed; nothing was written.")
            return 2
        print("  [ok] preflight passed\n")

    # BUG FIXED: --check used to fall through and run the whole cycle. Used as
    # ExecStartPre in the systemd unit, that would have run the cycle TWICE per tick --
    # once as the "preflight", once as the real run. A guardrail that performs the
    # dangerous action it is meant to gate is worse than no guardrail: it doubles the load
    # while appearing to protect against it. --check now verifies and exits.
    if "--check" in args:
        return 0

    cmd = [sys.executable, os.path.join(HERE, "aegis_run.py"), "--top", "60"]
    if do_reason:
        cmd.append("--reason")

    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE, timeout=600)
    out = (r.stdout or "") + (r.stderr or "")

    # find the committed run
    run = None
    for line in out.splitlines():
        if line.startswith("[commit]"):
            run = line.split(None, 1)[1].strip()

    ok = r.returncode == 0 and "REPRODUCES EXACTLY" in out

    if quiet:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        print("%s  %s  run=%s  %s  %.1fs"
              % (ts, "OK" if ok else "FAIL", run or "?", "replay-verified" if ok else "REPLAY-FAILED",
                 time.time() - t0))
    else:
        print(out.rstrip())
        print("\n" + "=" * 60)
        print("RESULT: %s   run=%s   %.1fs"
              % ("OK, replay verified" if ok else "FAILED", run, time.time() - t0))

    # Append-only transition log. Runs AFTER a successful commit so it always sees a fresh
    # pair. Failures here must NOT fail the cycle: the run is already written and verified.
    if ok:
        try:
            r2 = subprocess.run([sys.executable, os.path.join(HERE, "alert_diff.py"),
                                 "--last", "1"],
                                capture_output=True, text=True, cwd=HERE, timeout=120)
            n_events = 0
            for line in (r2.stdout or "").splitlines():
                if line.strip().startswith("total events:"):
                    try: n_events = int(line.split(":")[1].strip())
                    except Exception: pass
            if not quiet:
                tail = [l for l in (r2.stdout or "").splitlines()
                        if l.strip().startswith(("[HIGH]", "[WARN]", "[MEDIUM]"))]
                for l in tail[:6]:
                    print(l)
                print("  transitions logged: %d" % n_events)
        except Exception as e:
            print("  [transition log skipped: %s]" % str(e)[:50])

    # LIQUIDATION INGEST + FORWARD-TEST LEDGER (tasks B and B+). Two pages per tick keeps
    # the liquidation store current (the feed bursts ~100/30min), then forward_test.py appends
    # the day's coverage into the append-only ledger. Both run AFTER the commit so they read a
    # fresh pair, and NEITHER may fail the cycle: the run is already written and replay-verified,
    # and these are new streams, not dependencies of the screen.
    if ok:
        try:
            # These three live in screener/ (screener-local by design: they read runs/ and
            # write their artefact next to __file__). They are NOT at root. The prior wiring
            # called os.path.join(HERE, ...) which pointed at the ROOT and failed every tick
            # SILENTLY under --quiet: FileNotFoundError -> rc=1 -> suppressed. Point at the
            # screener/ dir explicitly, and keep cwd=HERE so run_history resolves root runs/.
            _scr = os.path.join(HERE, "screener")
            rL = subprocess.run([sys.executable, os.path.join(_scr, "liquidations.py"),
                                 "--incremental", "--pages", "2", "--quiet"],
                                capture_output=True, text=True, cwd=HERE, timeout=120)
            if rL.returncode != 0 and not quiet:
                print("  [liquidations rc=%d] %s" % (rL.returncode, (rL.stderr or "")[-120:]))
            else:
                rF = subprocess.run([sys.executable, os.path.join(_scr, "forward_test.py"),
                                     "--quiet"],
                                    capture_output=True, text=True, cwd=HERE, timeout=120)
                if rF.returncode != 0 and not quiet:
                    print("  [forward_test rc=%d] %s" % (rF.returncode, (rF.stderr or "")[-120:]))
                # VELOCITY: the real-time signal. Rebuilds from the immutable run ledger; cheap
                # (reads series, no network). Failure must not block the cycle, same as the rest.
                rV = subprocess.run([sys.executable, os.path.join(_scr, "velocity.py")],
                                    capture_output=True, text=True, cwd=HERE, timeout=120)
                if rV.returncode != 0 and not quiet:
                    print("  [velocity rc=%d] %s" % (rV.returncode, (rV.stderr or "")[-120:]))
        except Exception as e:
            print("  [liquidation/forward_test/velocity skipped: %s]" % str(e)[:50])

    # Rebuild the publishable artifacts for this run, then verify the two renderers agree.
    # Without this the dashboard goes stale within a single tick, and audit_parity.py reports
    # RUN_MISMATCH forever -- a permanently-tripped tripwire that people learn to ignore.
    # Failures here are reported but do NOT invalidate the run: the run is committed and
    # replay-verified, and that is the thing of value.
    if ok:
        try:
            r3 = subprocess.run([sys.executable, os.path.join(HERE, "publish.py"),
                                 "--quiet"],
                                capture_output=True, text=True, cwd=HERE, timeout=300)
            if r3.returncode == 2:
                print("  [PUBLISH] parity DISAGREEMENT - renderers report different numbers")
            elif r3.returncode != 0:
                print("  [publish rc=%d]" % r3.returncode)
            elif not quiet:
                print("  published: tear sheet + dashboard agree")
        except Exception as e:
            print("  [publish skipped: %s]" % str(e)[:50])

    # append a line to the run log so there is a single place to see history
    try:
        with open(os.path.join(HERE, "aegis_loop.log"), "a") as fh:
            fh.write(json.dumps({
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run": run, "ok": ok, "reason": do_reason,
                "seconds": round(time.time() - t0, 1),
            }) + "\n")
    except Exception:
        pass

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

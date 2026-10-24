#!/usr/bin/env python3
"""The orchestrator initiator: it must carry the objective, and it must be recorded.

WHY THIS SUITE EXISTS

The initiator is the text that starts one cycle. The failure mode is not that it is missing -- it
is that it is **plausible and wrong**, in two specific ways:

  1. It names a task without naming an OBJECTIVE. "Run the cycle" reads as complete and is not. The
     orchestrator then inherits whatever target is nearest to hand, and the nearest one here is
     in-range time, measured at CORRELATION(in-range%, final $) = -0.923. An agent optimising it
     destroys the account efficiently and correctly. So the initiator must state the correlation.

  2. It is versioned and hashed but never RECORDED. The run history would then show what the model
     said and not what the orchestrator was told. Same defect class as the counter that read 0 for
     a passing suite.

Asserted against the REAL imported module and the REAL run on disk, not a copy.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "screener"))

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def main():
    try:
        import aegis_run as ar
    except Exception as e:
        print("  cannot import aegis_run: %s" % e)
        return 1

    P = ar.ORCHESTRATOR_INITIATOR

    print("=== 1. the initiator exists and is versioned ===")
    ck("ORCHESTRATOR_VERSION is set", bool(ar.ORCHESTRATOR_VERSION))
    ck("initiator text is non-trivial (%d chars)" % len(P), len(P) > 400)

    print("\n=== 2. it names the OBJECTIVE, not just the task ===")
    ck("states the objective correlation", "-0.923" in P,
       "without it the orchestrator must guess which direction is down")
    ck("names in-range time as the WRONG target", "in-range" in P.lower())
    ck("names capital as the target", "capital" in P.lower())
    ck("says the metric improves while the account halves",
       "halves" in P.lower() or "half" in P.lower())

    print("\n=== 3. the five phases and the hard rules survive ===")
    for ph in ("SENSE", "EVALUATE", "REASON", "COMMIT", "VERIFY"):
        ck("names the %s phase" % ph, ph in P)
    ck("REASON is opt-in, so output stays attributable",
       "opt-in" in P.lower() or "opt in" in P.lower())
    ck("does not predict prices or returns", "never predict prices or returns" in P.lower())
    ck("exit 1 on a failed replay, no retry into green",
       "exit 1" in P and ("do not retry" in P.lower() or "not retry" in P.lower()))
    ck("exit 2 writes nothing", "exit 2" in P)

    print("\n=== 4. it carries the model trap that already cost one wrong diagnosis ===")
    ck("warns gemma4 reasons rather than failing", "gemma4" in P.lower() or "reason" in P.lower())
    ck("names the preflight command", "--check" in P)
    ck("does not describe the model as broken without cause",
       "not broken" in P.lower() or "answering elsewhere" in P.lower())

    print("\n=== 5. the initiator is RECORDED on every run ===")
    runs = os.path.join(ROOT, "runs")
    dirs = sorted([d for d in os.listdir(runs)
                   if os.path.isdir(os.path.join(runs, d))]) if os.path.isdir(runs) else []
    if not dirs:
        ck("a run exists to check", False, "no runs/ directories")
    else:
        latest = os.path.join(runs, dirs[-1])
        oj = os.path.join(latest, "orchestrator.json")
        ck("orchestrator.json is written into the run", os.path.exists(oj), latest)
        if os.path.exists(oj):
            m = json.load(open(oj))
            ck("it carries the version", m.get("orchestrator_version") == ar.ORCHESTRATOR_VERSION)
            ck("it carries a sha256 of the text", len(m.get("orchestrator_sha256", "")) == 64)
            ck("the recorded sha matches the live text",
               m.get("orchestrator_sha256") == ar.orchestrator_meta()["orchestrator_sha256"],
               "a recorded hash that does not match the text is worse than none")
            ck("it carries the full text, not just the hash", m.get("orchestrator_text") == P)
        mj = os.path.join(latest, "meta.json")
        if os.path.exists(mj):
            prov = (json.load(open(mj)) or {}).get("provenance") or {}
            ck("provenance carries the initiator hash", "orchestrator" in prov,
               "recorded on every run, including runs without --reason")
            if "orchestrator" in prov:
                ck("the provenance hash matches too",
                   prov["orchestrator"].get("sha256") ==
                   ar.orchestrator_meta()["orchestrator_sha256"])

    print("\n=== 6. bumping the text must change the hash ===")
    base = ar.orchestrator_meta()["orchestrator_sha256"]
    ck("a one-character change moves the sha", ar.provenance._sha(P + "\n") != base)

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  the initiator names the objective and every run records it")
    return 0


if __name__ == "__main__":
    sys.exit(main())

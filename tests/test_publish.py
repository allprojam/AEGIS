#!/usr/bin/env python3
"""Tests for publish.py - the self-maintaining artifact pipeline.

The load-bearing case is the FAILURE POLICY: a publish failure must not invalidate the run.
The run is committed and replay-verified before publish is ever called; a stale dashboard is
a lesser harm than a lost run.

Run:  python3 tests/test_publish.py
"""
import ast, importlib.util, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)      # srcint.py lives beside this test
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("publish_under_test", os.path.join(ROOT, "publish.py"))
A = importlib.util.module_from_spec(_spec)
cwd = os.getcwd()
try:
    os.chdir(ROOT)
    _spec.loader.exec_module(A)
finally:
    os.chdir(cwd)

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def main():
    print("=== 1. newest_run picks the lexicographically last iso dir ===")
    r = A.newest_run()
    check("returns a run id", bool(r), str(r))
    if r:
        runs = sorted(x for x in os.listdir(os.path.join(ROOT, "runs")))
        check("equals max of runs/", r == runs[-1], "%s vs %s" % (r, runs[-1]))
        check("iso format", len(r) == 16 and r.endswith("Z"), r)

    print("\n=== 2. step order is tear sheet -> dashboard -> parity ===")
    # STRUCTURAL, NOT TEXTUAL. This used to find("export_report.py") on the raw source, which a
    # COMMENT mentioning the filename would satisfy -- and which breaks if the file is merely
    # reformatted. Read the AST instead: the ordering of subprocess calls is a real invariant, and
    # the AST is what the interpreter sees.
    import srcint as SI
    pub = os.path.join(ROOT, "publish.py")
    order = []
    for node in ast.walk(ast.parse(open(pub, "rb").read())):
        if isinstance(node, ast.Call):
            for a in ast.walk(node):
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.endswith(".py"):
                    order.append((node.lineno, os.path.basename(a.value)))
    order.sort()
    seq = [b for _, b in order]
    check("the three stages are called", len(seq) >= 3, "got %r" % seq)
    if len(seq) >= 3:
        i_export = seq.index("export_report.py") if "export_report.py" in seq else -1
        i_build = seq.index("build_v2.py") if "build_v2.py" in seq else -1
        i_parity = seq.index("audit_parity.py") if "audit_parity.py" in seq else -1
        check("export_report before build_v2", -1 < i_export < i_build, "%d %d" % (i_export, i_build))
        check("build_v2 before audit_parity", -1 < i_build < i_parity, "%d %d" % (i_build, i_parity))
    # the rationale must be DOCUMENTED -- and a docstring is a real runtime object, unlike a comment
    check("ordering rationale documented", SI.has_comment_mentioning(pub, "before parity"))

    print("\n=== 3. failure policy: run survives a publish failure ===")
    # exit codes: read what main() actually RETURNS, not the text " return 2", which a comment
    # satisfies and a reformat breaks
    rets = SI.function_returns(pub, "main")
    check("exit 2 reserved for parity DISAGREEMENT", 2 in rets, "main() returns %r" % rets)
    # destructive calls: ask the AST which functions are CALLED. Excludes comments by construction,
    # so documenting the hazard no longer looks like committing it.
    bad = sorted(SI.called_names(pub) & {"rmtree", "unlink", "remove", "shutil.rmtree"})
    check("does not delete or rewrite any run", not bad, "calls %r" % bad)
    # a timeout is present on the actual call, whatever the spelling or surrounding prose
    tos = [getattr(k, "value", None) for k in SI.call_kwargs(pub, "run", "timeout")]
    check("subprocess calls carry a timeout so a hung publish cannot hold the timer",
          bool(tos) and all(isinstance(t, int) and t > 0 for t in tos), "got %r" % tos)

    print("\n=== 4. --quiet suppresses normal output (executed, not inspected) ===")
    # This asserted the TEXT of this very test file ('"--quiet" in sys.argv' in src), which is a
    # statement about my own source, not about the program. Run it instead and compare output.
    loud = subprocess.run([sys.executable, pub], capture_output=True, text=True, timeout=300)
    quiet = subprocess.run([sys.executable, pub, "--quiet"], capture_output=True, text=True, timeout=300)
    check("--quiet is accepted", quiet.returncode in (0, 1, 2, 3),
          "rc=%d stderr=%s" % (quiet.returncode, (quiet.stderr or "")[:80]))
    check("--quiet produces less output than a plain run",
          len(quiet.stdout or "") < len(loud.stdout or ""),
          "quiet=%d bytes, loud=%d bytes" % (len(quiet.stdout or ""), len(loud.stdout or "")))

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all publish assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

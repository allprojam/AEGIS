#!/usr/bin/env python3
"""Parity harness — prove the three audit implementations agree.

There are three copies of the six checks:
  1. screener/screen.py      (batch screener)
  2. screener/mcp_server.py  (API)
  3. screener/audit_core.js  (browser)

They were written separately from the same spec, so they drift. This runs the SAME
FROZEN INPUTS through all three and reports every disagreement.

HERMETIC: inputs come from fixtures/parity_cases.json, not the network. The result is
therefore a property of the CODE, not of what the feed returned that minute. Refresh the
fixtures with make_fixtures.py when they need to move forward.

    python3 screener/test_parity.py          # exit 0 = all agree
"""
import json, subprocess, sys, os, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(ROOT, "fixtures", "parity_cases.json")
sys.path.insert(0, HERE)
# NOTE: ROOT is deliberately NOT on sys.path. Putting it there lets ./screen.py
# (a pine-library extractor, unrelated) shadow screener/screen.py -- which is exactly
# what happened the first time this harness ran. Load the module by explicit file path
# instead, so the test can never be fooled by a same-named file elsewhere.

JS_RUNNER = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const pools = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
// audit_core.js is an ES module; strip the exports and eval it in a function scope
const body = src.replace(/export\s+(const|function|default)\s+/g, '$1 ');
const api = new Function(body + '; return {audit, THRESHOLDS};')();
const out = pools.map(p => {
  try { const r = api.audit(p); return {verdict: r.verdict, fails: r.fails}; }
  catch (e) { return {error: String(e).slice(0, 90)}; }
});
console.log(JSON.stringify(out));
"""


def norm(fails):
    return tuple(sorted(fails or []))


def run_js(pools):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(pools, f); poolfile = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(JS_RUNNER); runner = f.name
    res = subprocess.run(["node", runner, os.path.join(HERE, "audit_core.js"), poolfile],
                         capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        raise SystemExit("JS runner FAILED:\n" + res.stderr[:900])
    return json.loads(res.stdout)


def load_by_path(name):
    """Import a module by explicit file path, immune to sys.path shadowing."""
    import importlib.util
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location("aegis_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    # screen.py / mcp_server.py do `sys.path.insert(0,"screener")` internally and are
    # written to be run from the project root, so chdir there for the import.
    cwd = os.getcwd()
    try:
        os.chdir(ROOT)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    return mod


def compare(pools, label):
    """Returns the number of disagreements."""
    screen = load_by_path("screen").screen
    audit_pool = load_by_path("mcp_server").audit_pool

    py_screen = [screen(p) for p in pools]
    py_mcp = [audit_pool(p) for p in pools]
    js = run_js(pools)

    d12, d13 = [], []
    for i, p in enumerate(pools):
        a = (py_screen[i]["verdict"], norm(py_screen[i]["fails"]))
        b = (py_mcp[i]["verdict"], norm(py_mcp[i]["fails"]))
        j = js[i]
        if j.get("error"):
            print("  JS ERROR on %s: %s" % (p.get("symbol"), j["error"]))
            d12.append(p); continue
        c = (j.get("verdict"), norm(j.get("fails")))
        if a != b:
            d12.append((p, a, b))
        if a != c:
            d13.append((p, a, c))

    print("\n=== %s (%d cases) ===" % (label, len(pools)))
    print("  screen.py vs mcp_server.py : %d disagreement(s)" % len(d12))
    for row in d12[:8]:
        if len(row) == 3:
            p, a, b = row
            print("    %-16s py=%-11s%-26s mcp=%-11s%s" % (str(p.get("symbol"))[:15], a[0], ",".join(a[1]), b[0], ",".join(b[1])))
    print("  screen.py vs audit_core.js : %d disagreement(s)" % len(d13))
    for row in d13[:12]:
        if len(row) == 3:
            p, a, c = row
            print("    %-16s py=%-11s%-26s js=%-11s%s" % (str(p.get("symbol"))[:15], a[0], ",".join(a[1]), c[0], ",".join(c[1])))
    return len(d12) + len(d13)


def main():
    if not os.path.exists(FIXTURES):
        raise SystemExit("fixtures missing: %s\n  run: python3 make_fixtures.py" % FIXTURES)
    fx = json.load(open(FIXTURES))
    sample, boundary = fx["sample"], fx["boundary"]
    print("fixtures: %s" % FIXTURES)
    print("  %d live-sampled pools, %d boundary cases (frozen)" % (len(sample), len(boundary)))

    total = 0
    total += compare(sample, "live-sampled pools")
    total += compare(boundary, "boundary cases")

    print("\n=== VERDICT ===")
    if total == 0:
        print("  all three implementations agree on every fixture")
        print("  (deterministic: rerun gives the same answer regardless of the network)")
        return 0
    print("  DRIFT CONFIRMED: %d total disagreement(s)" % total)
    return 1


if __name__ == "__main__":
    sys.exit(main())

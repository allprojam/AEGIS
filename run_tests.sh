#!/bin/sh
# Run the whole suite. Offline, no install step, reliable total.
#
# WHY NOT pytest: these suites are main()-driven scripts, not pytest test functions. `pytest -v`
# collects NOTHING from them (0 files contain `def test_`), prints "no tests ran", and exits 0.
# That is a green result for zero verification -- the same defect class as the counter that read
# 0 for a passing suite and the --check flag that ran the cycle it was meant to gate. So this
# script runs each file directly and verifies that every one of them actually reported.
#
# WHY NOT a dynamic jsdom install: jsdom is a devDependency in package.json. Installing and
# deleting it on every run made the loop slow and the script brittle, and a failed install would
# have surfaced as a test failure rather than a tooling problem.
#
# FAILS LOUDLY if any suite passes while reporting zero assertions, so the silent-zero bug
# cannot return unnoticed.
cd "$(dirname "$0")" || exit 1

TOTAL=0
FAILED=0
ZEROED=""

py_suites=$(ls tests/test_*.py 2>/dev/null)
# `test_*.cjs`, not `*.cjs`: a shared HELPER in tests/ is not a suite. Globbing every .cjs swept
# up _jsdom_util.cjs, which printed no assertions and reported "PASS but reported 0 assertions" --
# a helper masquerading as a passing suite. The suite runner already fails loudly on a zeroed
# PYTHON suite; this closes the same hole on the JS side rather than relying on the name.
js_suites=$(ls tests/test_*.cjs 2>/dev/null)

printf '%-24s %s\n' "SUITE" "RESULT"
printf '%s\n' "------------------------------------------"

for f in $py_suites; do
  n=$(basename "$f" .py)
  out=$(python3 "$f" 2>&1); rc=$?
  c=$(printf '%s\n' "$out" | grep -c 'PASS')
  if [ "$rc" -ne 0 ]; then
    printf '%-24s FAIL (rc=%s)\n' "$n" "$rc"; FAILED=$((FAILED+1))
  elif [ "$c" -eq 0 ]; then
    printf '%-24s PASS but reported 0 assertions\n' "$n"; ZEROED="$ZEROED $n"
  else
    printf '%-24s PASS (%s)\n' "$n" "$c"
  fi
  TOTAL=$((TOTAL+c))
done

# jsdom must resolve locally. Report a missing devDependency as a TOOLING problem, not a
# test failure: conflating the two sends the reader after the wrong bug.
if [ -n "$js_suites" ]; then
  # CHECK LOCALITY, NOT AVAILABILITY. Node walks UP the directory tree, so a bare
  # `require.resolve('jsdom')` succeeds using a SIBLING project's node_modules -- verified:
  # with our own node_modules removed it resolved from /root/agency_bot/node_modules, a
  # different project's install. The suites would then pass against a dependency this project
  # never declared. That is the isolation failure itself, so the guard must demand a LOCAL
  # resolution or refuse to run.
  if ! node -e "process.exit(require.resolve('jsdom').includes('aegis/node_modules') ? 0 : 1)" >/dev/null 2>&1; then
    resolved=$(node -e "try{console.log(require.resolve('jsdom'))}catch(e){console.log('not found')}" 2>/dev/null)
    printf '\nTOOLING: jsdom does not resolve from THIS project.\n'
    printf '  resolved: %s\n' "$resolved"
    printf '  Run:  npm install        (jsdom is a devDependency in package.json)\n'
    printf '  This is NOT a test failure; no assertion was evaluated.\n'
    printf '  Refusing to run: passing against another project'"'"'s dependency would\n'
    printf '  hide the missing declaration rather than reveal it.\n'
    exit 2
  fi
fi

for f in $js_suites; do
  n=$(basename "$f" .cjs)
  out=$(node "$f" 2>&1); rc=$?
  c=$(printf '%s\n' "$out" | grep -c 'PASS')
  if [ "$rc" -ne 0 ]; then
    printf '%-24s FAIL (rc=%s)\n' "$n" "$rc"; FAILED=$((FAILED+1))
  elif [ "$c" -eq 0 ]; then
    printf '%-24s PASS but reported 0 assertions\n' "$n"; ZEROED="$ZEROED $n"
  else
    printf '%-24s PASS (%s)\n' "$n" "$c"
  fi
  TOTAL=$((TOTAL+c))
done

if python3 screener/test_parity.py >/dev/null 2>&1; then
  printf '%-24s PASS\n' "test_parity"
else
  printf '%-24s FAIL\n' "test_parity"; FAILED=$((FAILED+1))
fi

printf '%s\n' "------------------------------------------"
printf 'TOTAL: %s assertions\n' "$TOTAL"

if [ -n "$ZEROED" ]; then
  printf '\nFAIL: these suites passed but reported no assertions:%s\n' "$ZEROED"
  printf 'A green run with a zero count is a REPORTING bug, not success.\n'
  exit 1
fi
if [ "$FAILED" -gt 0 ]; then
  printf '\nFAIL: %s suite(s) failed\n' "$FAILED"; exit 1
fi
exit 0

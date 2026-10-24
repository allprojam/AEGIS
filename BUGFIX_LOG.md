# Bug-fix pass — every fix verified, not assumed

Method: compile everything, then test behaviour rather than reading it. Five bugs found. The parity
harness found one the eye never would have.

---

## 1. `screen.py` crashed on string numerics — a real parity bug

**Found by:** the parity harness feeding adversarial inputs.

```
screen.py      CRASH  TypeError: '>' not supported between 'str' and 'int'
mcp_server.py  AVOID  ['DEAD']
audit_core.js  no crash (Number() coerces)
```

**Same input, three different behaviours.** The feed is JSON and has been seen to return numbers as
strings (`'5.5'`). `audit_core.js` used `Number()` and `mcp_server.py` used `float()`, but `screen.py`
compared raw.

**Fix:** added a `num()` coercer handling `None`, non-numeric strings, booleans and NaN, and routed
every numeric read through it.

**Verified:** all three now agree on that input, and on a case that *should* pass.

---

## 2. Negative APY was flagged `DEAD` — a misleading flag

```
apy = -3%  ->  AVOID:['DEAD']  reason: "daily turnover 0.29% of TVL"
```

**The flag described turnover, not the actual problem.** A pool paying −3% is not "dead", it has no
yield at all. The label sent the reader to the wrong conclusion.

---

## 3. Zero-yield pools were labelled `REAL` — 31% of the list

**The biggest bug of the pass.** Testing found that `apy = 0` passed every check and returned `REAL`,
because zero emissions *is* technically "organic". Then I measured it:

```
REAL pools with apy == 0:  590 of 1,891  (31%)
  WSTETH   Ethereum   $3,720.2M
  CBBTC    Base       $3,327.1M
  ...
```

**A $3.7B pool paying nothing was being called a real yield opportunity.** Technically defensible,
practically misleading — and this is exactly the "a number that looks like skill is usually a
structural artefact" failure the project exists to catch.

**Fix:** a seventh check. `apy <= 0` -> `NO_YIELD`, with its own verdict, in all three implementations.

**Effect on the whole screen:**

| verdict | before | after |
|---|---|---|
| REAL | 1,891 | **1,317** |
| PROMISING | 105 | 74 |
| MIXED | 962 | 966 |
| **NO_YIELD** | — | **4,835** |
| AVOID | 13,872 | 9,557 |

**4,835 pools were being misclassified** — some as REAL, the rest swept into AVOID where the real
reason (no yield) was never stated. **They now report the actual reason.**

---

## 4. `borrow_lp.py` did not compile — unterminated docstring

```
SyntaxError: unterminated triple-quoted string literal
```

The docstring opened with `"""` on line 1 and closed with a single `"` on line 2. **It had been broken
in every compile the whole session** — the earlier "all Python compiles" checks never ran across the
whole tree.

**Fix:** closed the docstring. **Then ran it**, because compiling is not working:

```
band +/-10%: in-range 10.1%  equity $-2692.26
```

It runs and prints the catastrophic equity, which is the script's entire point.

---

## 5. A page that had grown to 5.3MB

Adding `NO_YIELD` to the embedded set pushed the report from 2.2MB to **5.3MB**, because all 4,835
zero-yield pools came with it. **Fix:** only embed `NO_YIELD` pools above $5M — a zero-yield pool you
would never enter is not worth a lookup. Back to **2.2MB**.

---

## What was NOT a bug

**The turnover floor looked broken.** A $2M pool with $100k weekly volume was flagged `DEAD` at
0.71%/day against a 1.0%/day floor. I checked it against the data instead of "fixing" it:

```
REAL pools' turnover, p1:    1.0531%/day   <- just above the 1.0 floor
REAL pools' turnover, median: 9.2368%/day
REAL pools below the floor:  0
```

**The floor is well-calibrated — 0 REAL pools sit below it, and p1 is 1.05%.** The filter works. Left
alone.

---

## Also fixed

**`ETH_USD` was silently included in the pre-mortem headline.** My first filter used `!= "ETH"`, but
the symbol is `"ETH_USD"`, so it never matched and the mislabeled sparse file stayed in. Corrected —
the headline is **45 runs across 9 valid files**, correlation **−0.996**.

**A multiplier expression computed `100/x*100` instead of a ratio.** It printed "3.8x" only after
being fixed; the wrong version would have printed a different number entirely.

---

## The parity harness

`screener/test_parity.py` — runs the same pools through all three implementations and reports every
disagreement. **This is the fix for the underlying problem**, which is that three copies of one spec
will drift.

```
=== screen.py vs mcp_server.py ===  disagreements: 0 / 400
=== screen.py vs audit_core.js ===  disagreements: 0 / 400
=== VERDICT === all three agree on 400 pools
```

Plus **17 hand-built boundary cases** — every threshold tested exactly at, one unit either side:
spot ratio 60% vs 59%, reward share 50% vs 51%, stable base 25% vs 25.1%, TVL $1M vs $999,999, count
30 vs 29, plus nulls, zeroes, negative APY and missing fields.

**All 17 agree across all three implementations. Zero drift.**

## Test suite status

```
python compile, whole tree      pass
js syntax, both files           pass
ledger self-test                pass (free tier, credit drawdown, double-credit refused)
premortem engine regressions    pass (HODL math, ruin floor, SAT_OUT verdict)
parity harness, 400 live pools  pass, 0 drift
parity harness, 17 edge cases   pass, 0 drift
```

## Known, not fixed

- **`test_parity.py` samples live data, so it is not hermetic.** It will drift when the feed changes.
  A frozen fixture set should be committed.
- **The ETH file is still mislabeled on disk.** Excluded from analysis, but `bars_eth_usd_1d_9y.csv`
  still claims to be hourly 3-year data. **Should be renamed or regenerated.**
- **`borrow_lp.py` runs but I did not verify its LP math**, only that it executes. Its conclusions
  looked correct on inspection (equity deeply negative, net short ETH) but the fees/in-range
  accounting has not been independently checked.
- **Duplicate basenames remain** across the tree (`fetch.py` x4, `dex.py` x2, `screen.py` x2). No
  drift confirmed, but they are a hazard.

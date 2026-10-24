# Aegis Structural Backtest v2 — the two findings that survived

**DATASET:** 122 pools, each with >=365 days of DefiLlama chart history, anchored to a point T exactly
12 months ago. Outcome measured from T forward. Source: `structural_backtest_v2.jsonl`, `apy_decay.json`.

---

## FINDING 1 (SOLID): 46.7% of indexed pools lost more than half their liquidity in 12 months

```
57 of 122 pools   =  46.7%      95% CI [38.1%, 55.5%]

FAILED       8   ( 6.6%)    TVL < 10% of baseline, or final TVL < $10,000
IMPAIRED    49   (40.2%)    TVL fell below 50% but not below 10%
SURVIVED    65   ( 53.3%)
```

**The confidence interval is entirely above one third.** This does **not** depend on whether our flags
work — it is a property of the index, measured with the outcome variable you specified.

**Why this matters more than it looks:** under the old binary "dead or alive" definition, **49 of these
pools — 40% of the cohort — counted as SURVIVORS.** They lost more than half their capital while still
reporting. A screen that only counts deaths describes a market that is being drained as healthy.

---

## FINDING 2 (SOLID, AND ON-BRAND): no high-yield pool paid what it advertised

Every pool advertising >8% APY at T, with what it actually paid over the next 365 days:

```
symbol              chain       advertised   realized   retention
WCRO-LTC            Cronos         44.77%     17.68%      39.5%
USD1                Ethereum       29.68%      5.73%      19.3%
TRX                 Tron           12.63%     10.83%      85.8%
CRVUSD              Ethereum       12.35%      4.41%      35.7%
FXSAVE              Ethereum       11.57%      5.99%      51.8%
FXUSDSTABILITYPOOL  Ethereum       10.97%      6.21%      56.6%
SLISBNB             BSC             9.92%      5.45%      55.0%
STCUSD              Ethereum        9.55%      6.09%      63.8%
WSRUSD              Ethereum        9.51%      5.81%      61.1%
USDC                Arbitrum        9.35%      5.30%      56.6%
USDC                Ethereum        9.08%      5.40%      59.5%
USDT                Ethereum        9.03%      4.91%      54.4%

0 of 12 beat their own advertised rate.
mean retention 53.3%      median retention 55.8%
```

**At n=12 the 95% upper bound on the true rate is 24%**, so "most high-yield pools beat their own
number" is very unlikely. In this sample, **none did.**

**This is the product claim, stated precisely:** a yield screen is not predicting whether a pool
survives. It is checking whether the number on the tin is the number that gets paid.

---

## THE NON-RESULT: the flags do not separate on either outcome

**Combined attrition (FAILED + IMPAIRED):**

```
FLAGGED   n=42   52.4%      95% CI [37.7%, 66.6%]
PASSED    n=80   43.8%      95% CI [33.4%, 54.7%]
```

**Overlapping.** The point estimate now leans the right way (52.4 vs 43.8, versus backwards in v1),
but it is not separable.

**Yield retention:**

```
FLAGGED   n=14   retention  61.2%
PASSED    n=80   retention  91.4%
```

**Direction is right, gap is large, but n=14 on the flagged arm.** Not publishable.

**HONEST CONCLUSION: at 122 pools we can measure the market. We cannot yet prove the screen
discriminates.** Those are different claims and only the first is supported.

---

## A tautology I had to remove

The first run reported NO_YIELD pools with **"0.0% retention" (n=28)**. That is not a finding —
`NO_YIELD` is **defined** as apy <= 0 at T, so retention of zero is the definition restated as an
outcome. Including it inflated the flagged arm's apparent badness. **Excluded; every flagged figure
above is computed without it.**

Also: **THIN's median retention of 131% is driven by one pool at 425%.** With n=7 a single outlier
moves the median. Not reported as a result.

---

## The framing, with the number that is defensible

Use the **market fact**, not the flag claim:

> **"46.7% of indexed pools lose more than half their liquidity within 12 months**
> **[95% CI 38.1–55.5%]. Not by exploit — by slow bleed. Aggregators show the APY you are promised,
> not the liquidity you will be left holding.**
>
> **Of the pools advertising above 8%, none paid what they advertised. Median retention 55.8%.
> Aegis checks whether the number on the tin is the number that gets paid."**

**Both numbers hold across their confidence intervals, and neither depends on the flag comparison
resolving.** That is the story we can defend today.

---

## What would earn the flag claim

```
need >=125 pools per arm (251 total) to separate 20% from 10% at 95%
have  42 flagged / 80 passed
```

**The binding constraint is the FLAGGED arm, not the total.** Either collect more, or tighten the flag
definition to THIN-only — the dominant flag, and the one with a mechanism behind it.

---

## State

```
backtest_v2.py                v2 collector, inline de-tracking resolution, 9/9 boundary tests
apy_decay.py                  yield-retention analysis (resumable)
structural_backtest_v2.jsonl  122 pools, outcomes
apy_decay.json                122 pools, advertised vs realized APY
```

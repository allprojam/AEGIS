# Phase 1 results: Lending Screen + Stress Test

**Built:** `morpho_fetch.py`, `lending_screen.py`, `stress_backtest.py`.
**Status: the screen works. The backtest looked spectacular and is circular. Do not ship the number.**

---

## Part 1 - the screen works, and it caught real losses

60 Morpho Blue USDC markets on Base:

```
REAL       18  (30%)
CAUTION     8  (13%)
AVOID      34  (57%)

LOCKED          32      utilisation >95%
OUTLIER         31      net APY >100%
PROTOCOL_RED    30      Morpho's own RED warning
HIGH_LLTV       26      LLTV >94.5%
THIN            13      TVL <$1M
BAD_DEBT         4      realised loss
NO_YIELD         2
```

**Four markets carry realised bad debt, and the screen flags all four:**

```
USR    $34,821,390 bad debt   TVL $36.7M   util 100.0%   LLTV 91.5%  -> AVOID
RSS    $ 1,041,990 bad debt   TVL $ 2.5M   util 100.0%   LLTV 77.0%  -> AVOID
RLP    $   530,853 bad debt   TVL $ 0.6M   util 100.0%   LLTV 86.0%  -> AVOID
```

**USR lost 95% of its supply to bad debt** ($34.8M against $36.7M supplied). That is the thing the
vault was meant to avoid, and the rules name it.

**And it consumes Morpho's own warnings rather than re-deriving them.** 30 of 60 markets carry a RED
flag - including the HERMES cluster at **297,986% APY**, which is `not_whitelisted` +
`unrecognized_collateral_asset` + `sustained_low_liquidity`.

---

## Part 2 - the stress test produced a beautiful number, and it does not hold up

What it printed:

```
FLAGGED  n=35   stressed 30 = 85.7%   95% CI [70.6%, 93.7%]
PASSED   n=12   stressed  1 =  8.3%   95% CI [ 1.5%, 35.4%]

LOCKED      n=28   100.0% [87.9%,100.0%]   without: 15.8%
OUTLIER     n=26   100.0% [87.1%,100.0%]   without: 23.8%
HIGH_LLTV   n=25   100.0% [86.7%,100.0%]   without: 27.3%
```

**Disjoint confidence intervals, 100% detection, 10x lift.** This is exactly the number the vault
pitch wanted. **It is circular, and I checked before believing it.**

### Why it is circular

**The input and the outcome are the same measurement.**

```
input   LOCKED = utilisation at T is above 95%
outcome LOCKUP = utilisation forward reaches 99%
```

**And the "independent" cross-check fails too.** I tested whether `LOCKED` predicts `BLOWOUT` (APY, a
different metric):

```
LOCKED   n=28   BLOWOUT 28 = 100.0%
not      n=19   BLOWOUT  0 =   0.0%
```

**Zero false positives looks like a great result. It is mechanical.** In an isolated lending market,
**100% utilisation and a spiked supply APY are the same event described two ways** - the rate model
maxes out precisely *because* the market is fully drawn. The 297,986% APY is the arithmetic
consequence of 100% utilisation, not a separate signal.

### The selection problem underneath it

```
utilisation at T: median 100.0%   min 0.0%   max 100.0%
markets above 95% at T: 28 of 47  (60%)
```

**Median utilisation is 100%.** When most of the population sits at the ceiling, "this market is at
the ceiling" is not a discriminating observation. The flag is not detecting an anomaly; it is
detecting the modal state.

---

## What this means for the vault thesis

**The honest summary: the rules name losses that already happened, which is useful. They cannot be
shown to predict losses on this data, because every candidate outcome is mechanically coupled to the
inputs.**

That is the same class of finding as the pool backtest - **a metric that looks like skill and turns
out to be a structural artefact.** Third time in this project:

1. a 24% APY that was a 7-day average of 8.9%
2. a positive alpha that was absence of participation
3. a 100% stress detection that was one variable measured twice

**And this is why the vault stays dead.** The pitch required "we flag risky markets before they take
bad debt." What we have is "we flag markets that are already stressed." **Those are different
products, and only the second is true.**

---

## What would actually test the thesis

**The blocker is unchanged: `badDebt` is not in `MarketHistory`.** Only the current cumulative total
is exposed. To test prediction we need to know *when* a market took a loss, which requires
liquidation events - back to the indexer work.

Three options, none free:

1. **Index Morpho liquidation events** from Base logs. Gives real loss timing. Real work, real cost.
2. **Forward test.** Run the screen read-only against live markets, record what it flags, check in
   6-12 months. Free, but slow and small-n.
3. **Study USR.** One market with an actual, large loss. One case is a case study, not a backtest -
   but a well-documented one is more honest than a 47-market circular statistic.

---

## What I would ship today

**The screen, without the backtest claim.**

> *"We read 60 Morpho Blue USDC markets on Base. 34 carry a structural flag. Four have already taken
> realised bad debt - USR lost $34.8M against $36.7M supplied. 30 carry Morpho's own RED warning.
> Here is the full list, the rule that caught each one, and the raw JSON."*

**Every number there is a measurement of current state.** No prediction is claimed, so none can fail.
And it is more useful to a depositor than a circular 10x.

**The rule that keeps this honest: a test is only a test if the input and the outcome can disagree.
If they cannot, it is a restatement.**

---

## Files

```
morpho_fetch.py             read-only GraphQL ingestion, verified schema
lending_screen.py           7 lending checks, consumes Morpho's warnings
stress_backtest.py          labels itself "NOT a bad-debt predictor"
morpho_markets.json         60 markets, current state
stress_backtest.json        47 markets, with the circularity documented
morpho_history_cache.json   cached histories (reruns are instant)
```

# The Pre-Mortem Engine: why 34 of our 45 strategy runs were rejected

**We built five TradingView strategies. Then we ran them against buy-and-hold on three years of real
bars, with next-bar fills, real fees and real gas. Most of them lost. Here are the numbers.**

This is the honest version, including the three bugs the exercise exposed in our own engine.

---

## Method

**Execution model** (`simulate_events`, rewritten this session):
- signal evaluated on the **closed** bar, fill at the **next** bar open — no look-ahead
- **one position at a time**, no pyramiding
- 5 bps round-trip fee + $0.02 gas charged on **every** entry and exit
- **position sized from available equity**, never a fixed notional
- **ruin handling**: trading stops when the account is wiped; ROI floored at −100%
- open position at the end **marked to final close**, not silently dropped

**Baseline** — every result carries buy-and-hold over the identical window:
- HODL buys at bar 0 open, holds to the final close
- **HODL is charged the same round-trip fee and gas as a trade**, which makes the baseline look
  *worse*, not better. A strategy that loses to a fee-charged baseline is robustly bad.
- HODL is measured across the **full window including warmup**, because an investor could genuinely
  have held from bar 0 while the strategy waited for its 200-bar lookback to fill.

**Three verdicts, not two:**

| verdict | meaning |
|---|---|
| `BEATS_HODL` | alpha > 0 with real market exposure |
| `LOSES_TO_HODL` | alpha < 0 — worse than doing nothing |
| `SAT_OUT` | alpha > 0 with zero exposure — **absence, not skill** |

The third verdict exists because of a flaw found during validation: **a strategy that never trades
scores alpha = +100% in a falling market purely by not participating.** That tests as "beating" HODL
and is completely meaningless. It is now reported as `SAT_OUT` so it can never be read as alpha.

---

## Results

**50 runs**: 5 strategy variants × 10 assets, 1h bars.

```
all 50 runs (including the mislabeled ETH file):
  BEATS_HODL        11   (22%)
  LOSES_TO_HODL     39   (78%)

headline figures, 45 runs across the 9 valid 3-year files:
  BEATS_HODL        11   (24%)
  LOSES_TO_HODL     34   (76%)
  SAT_OUT            0
  accounts wiped     18
```

### By strategy

| strategy | beat | lost | median alpha |
|---|---|---|---|
| Keltner bounce, exit on EMA touch | 4 | 6 | **−31.3** |
| Keltner bounce, exit on top band | 3 | 7 | −92.5 |
| BB+RSI v1.1 long only | 4 | 6 | −88.6 |
| Fractal breakout, n_time=3 | **0** | **10** | −163.0 |
| Fractal breakout, n_time=12 | **0** | **10** | −163.0 |

**The fractal breakout failed on every single asset, both parameterisations.**

### By asset

| asset | HODL | strategies that beat it |
|---|---|---|
| SOL | +772% | 0 / 5 |
| BTC | +215% | 0 / 5 |
| XRP | +191% | 0 / 5 |
| DOGE | +53% | 0 / 5 |
| LINK | +73% | 1 / 5 |
| AVAX | +14% | 1 / 5 |
| LTC | +6% | 3 / 5 |
| ADA | +4% | 3 / 5 |
| DOT | −71% | 3 / 5 |

---

## The actual finding

**Correlation between the asset's buy-and-hold return and the strategy's alpha: −0.996.**

That is almost a straight line. Split it out:

```
assets where HODL >  +20%:   25 runs,  1 beat  ( 4%)
assets where HODL <= +20%:   20 runs, 10 beat  (50%)
```

**In a bull market the strategies almost never win — 1 in 25.** On flat or falling assets they win
half the time.

**So the "edge" is not timing skill.** It is the strategies *not being in the market* while the asset
goes nowhere, which reads as outperformance against a flat benchmark. **The moment there is a trend to
capture, they miss it and buy-and-hold runs away.**

**This is the same lesson as the pool screener, in a different market:** a number that looks like skill
is usually a structural artefact. There, it was a 24% APY that was really a 7-day average of 8.9%.
Here, it is a positive alpha that is really just absence of participation.

---

## Three bugs this exercise found in our own engine

The engine is what grades the strategies, so a bug in it invalidates every verdict. All three were
found by testing, not by reading.

**1. Impossible ROIs (−645%).** The engine re-bet the full $250 notional after the account had fallen
below it. **Over-betting.** A $250 account reported −645% ROI, which cannot happen. Fixed by sizing
each position from *available* equity and flooring the account at zero.

**2. Zero-trade "alpha" (+100%).** An all-`False` signal set scored alpha = +100% against a price that
halved. Caught by hand-computing a falling-market case. Fixed with the `SAT_OUT` verdict.

**3. A mislabeled data file.** `bars_eth_usd_1d_9y.csv` **was named `1h_3y` and is neither** — 3,254 bars spanning
**2017→2026**, median gap **24.0h**, 100% of gaps over 2h. It is a daily/sparse series wearing a 1h
filename.

**A fourth bug, found later while writing tests.** The script reported *"ETH share of value 241.5%"* —
a share of value above 100% is impossible, and the cause was a unit mismatch: the token amount was
computed at `L=1` while the denominator was computed at the rescaled `L`. **Fixed, now 47.56%, and
pinned by a closed-form test.** The same audit found an unsourced claim in the script's prose
(*"delta ~0.3-0.5 ETH per ETH supplied"*) which the engine's own numbers contradict — the real
figures are **0.1969 / 0.1000 / 0.0404**. Both are now asserted in `tests/test_lp_engine.py`
(25 assertions, all passing).

**That third bug produced the single most dramatic-looking number in the whole set** — ETH "HODL
+779%", which looks like a devastating indictment of the strategies on ETH. **It is a window
artefact.** ETH spans nine years while every other file spans three.

**ETH is excluded from the headline figures and the file should be renamed or regenerated.** The
correlation above is computed on the 9 valid files (45 runs), and remains −0.99.

---

## What we are selling, and what we are not

**Not:** the strategies. **Our own runs rejected 76% of them.** Packaging them as alpha would make us
the thing this project exists to catch.

**What we sell is the harness:**

> **Bring your strategy or your pool thesis. We run it against next-bar execution, real fees, real
> gas, ruin handling, and a fee-charged buy-and-hold baseline. We show you what fails before you fund
> it.**

**Pricing:** the $0.05/audit pool screener is the front door. The strategy pre-mortem is the premium
tier — **$25–$50 per automated script audit**, custom ingestion quoted separately.

---

## Honest limits of this study

- **10 assets, 5 strategies, long-only, one timeframe.** This is a case study, not a survey.
- **In-sample.** No walk-forward split, so these are not out-of-sample forecasts — they are honest
  measurements of what these rules did.
- **No parameter sweep here.** The `backtest.py` sweep exists for that and should be run before any
  claim about robustness rather than fit.
- **Not investment advice.** It is a measurement, and the measurement says these particular rules
  mostly lost to holding.

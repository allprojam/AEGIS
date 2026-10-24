# The regime classifier: built, tested, and it does not work

## What I built

A classifier to answer the one question the hybrid architecture reduced to: **can we tell a range
regime from a trend regime, so we LP the range and hold spot for the trend?**

Tested metrics (all computed from **past bars only**):
- **Efficiency ratio** (Kaufman): |net move| / sum|path| — 1 = clean trend, 0 = chop
- **Realised volatility**
- **Autocorrelation** of returns
- **Absolute net return** over the window

Test design: 315 windows of real ETH hourly data, 30-day lookback, **30-day forward horizon**,
LP (measured 24.04% pool APR) vs 50/50 spot, both exiting to cash on a 10% band break.

## The result: no metric predicts it

```
315 windows   LP beat spot in 6.3% of them
forward move  median |10.3%|   mean |14.4%|
```

**LP-win rate by metric quartile:**

| metric | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| vol | 0.0% | 22.8% | 1.3% | 1.3% |
| efficiency ratio | 6.3% | 12.7% | 2.6% | 3.8% |
| autocorrelation | 15.2% | 1.3% | 5.1% | 3.8% |
| abs net return | 7.6% | 10.1% | 3.8% | 3.8% |

**None is monotonic.** A real predictor must show LP-win rate rising or falling steadily across
quartiles. Every metric here jumps around — Q1 at 0.0% then Q2 at 22.8% for volatility is **noise**,
not a threshold effect. And the absolute level is the point: **LP loses to spot 93.7% of the time.**

## Walk-forward — the decisive test

The only way to know whether a pattern is real is to fit on one period and test on another.

```
best in-sample rule:  LP when vol in [0.00729, 0.00873]
                      in-sample win rate 64.1%  (78 observations)

OUT-OF-SAMPLE:        5 observations, win rate 20.0%
                      baseline OOS win rate (all obs) 44.9%
```

**A rule that looked good at 64.1% scored 20.0% out of sample — worse than doing nothing (44.9%).**
That is the textbook signature of overfitting, and it is why the in-sample number was meaningless.

## Band sensitivity — where the real pattern lives

| band | APR 24% | APR 50% | APR 100% |
|---|---|---|---|
| ±10% | 6.3% | 17.1% | 47.3% |
| ±20% | 47.9% | 56.5% | 67.6% |
| ±30% | 59.4% | 72.4% | 76.8% |
| ±50% | 70.8% | 84.4% | 98.1% |

**A clear monotonic relationship, and it is not about regime at all — it is about fee APR versus
band width.**

- At **24% APR and ±10%**, LP loses 93.7% of the time.
- At **98.1% win rate (±50%, 100% APR)**, LP wins — but that requires **100% APR**, which is roughly
  4x the best measured organic pool APR in the entire project.
- **Even at the 98.1% win rate, mean LP was 1.059 vs spot 0.995** — a 6.4% edge, on an assumption of
  100% APR that no pool in this project has been measured at.

## The honest conclusion

**The classifier cannot be built from price action, and the test says why: the LP-vs-spot outcome is
determined by the fee APR and the band width, not by the regime.**

```
LP is a short-volatility position. Spot is long the trend.
Which one wins = (fee income) vs (trend magnitude x exposure)
```

**Regime detection is trying to forecast the second term. The first term — 24% APR — is known with
certainty.** So the classifier was aimed at the wrong variable: it tried to predict the unpredictable
term while ignoring the measurable one.

**This is the same finding as every previous chapter, arriving from a new direction.** The hybrid
architecture was not wrong because the plumbing is bad — Base's 3.1s execution is real, the pool's
24.04% is real, the webhooks work. It was wrong because **the LP+webhook construction is a
short-volatility position wearing a market-making costume**, and the classifier was an attempt to
time the volatility. Regime timing is the exact thing this project has failed to find edge in nine
times now.

## What is actually established

**Measured, real, and non-subsidised:**
- **Uniswap v3 WETH-USDC on Base: 24.04% APR, apyReward 0.00, $163M TVL.** The best real-yield
  instrument in the project.
- Base execution: **~3.1s** webhook-to-inclusion.
- Band-break exit genuinely limits drawdown.

**Measured, and negative:**
- LP beat spot in **6.3%** of forward windows.
- No regime metric separated outcomes monotonically.
- Walk-forward: **64.1% in-sample → 20.0% out-of-sample vs a 44.9% baseline.**
- LP only wins at **band/APR combinations** that require ~4x the best measured APR.

## The Pine script

`pine/aegis_regime.pine` — **compiles clean on v6, verified running live** on
BINANCE:ETHUSDC 1h. Real output read back:

```
Efficiency ratio    .036
Regime              CHOP
Realised vol (ann.) 43.1%
In band             yes
```

**It is loaded with the honest framing built in** — the table displays *"context, not a signal"*,
*"LP won 6.3% of windows"* and *"20.0% vs 44.9% base"* on the chart itself. **I built the failure
into the tool rather than shipping a classifier that looks like it works.**

It plots the efficiency ratio with trend/chop thresholds and shades the regime, so you can see
directly that the picture looks obvious in hindsight and does not separate forward outcomes.

## Where this leaves the architecture

**Keep:** the 24.04% zero-emission pool, the Base execution layer, the Pine tooling.

**Drop:** the classifier, and the premise that IL can be avoided by timing the regime.

**The only version of the hybrid that survives measurement:** LP the range-appropriate band width
**knowing** it is a short-vol position, sized so the flat-regime fee income is meaningful and the
trend-regime loss is survivable — with no claim of timing. That is a different strategy from the one
proposed, and it is the honest one.

**Nine chapters, nine short-volatility findings.** The one asset that never required timing was the
one the project started with.

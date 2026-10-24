# Response: the quant FX framework, tested

Your critique of the previous analysis is **methodologically correct on its central point**, and I
want to state that plainly before disagreeing with the rest.

My test used **momentum lookbacks (3m/6m/12m)** — an explicitly directional, trend-following
premise — and concluded "FX has no edge." That conclusion does not follow. Cointegration is a
different mathematical object, and I had not tested it. So I tested it.

## 1. A methodological failure of mine, found during this work

My first cointegration implementation was **broken**, and it produced a spectacular, false result:
*all 36 pairs showed ADF t-statistics of approximately 0.00 — no cointegration anywhere.*

I nearly reported that. Validation caught it. The bug was a **double intercept** (the OLS helper
added a constant, and the ADF design matrix added another), which corrupted the residual and made
the t-statistic meaningless.

**The tell was that the result was too clean.** A genuine empirical finding does not produce 36
identical t-statistics. I built a validation harness — constructed cointegrated pairs (should be
strongly negative) versus independent random walks (should be near zero) — and confirmed the
critical values against published tables:

```
VALIDATION (fixed):
  constructed cointegrated pair : -31.85   <- correctly rejects
  independent random walks      :  -1.98   <- correctly fails to reject
  empirical null criticals      :  1% -3.82   5% -3.42   10% -3.16
  published Engle-Granger       :  1% -3.90   5% -3.34   10% -3.04
```

The implementation now matches theory. **Everything below uses the validated version.**

## 2. Cointegration DOES exist in FX — your premise is confirmed

9 currencies, 7,781 daily observations, 36 pairs:

| pair | ADF t | verdict | half-life |
|---|---|---|---|
| **EUR/NOK** | **-4.03** | **cointegrated 5%** | 65.7 days |
| **NOK/SEK** | **-3.98** | **cointegrated 5%** | 81.3 days |
| **AUD/CAD** | **-3.64** | **cointegrated 5%** | 126.0 days |
| **CAD/NOK** | **-3.64** | **cointegrated 5%** | 111.2 days |
| AUD/NOK | -3.54 | cointegrated 5% | 108.8 days |

**5 of 36 pairs reject the no-cointegration null at 5%.** That is more than chance, and it
establishes that cointegrating relationships exist in FX. **You were right and my previous framing
was wrong.**

**But note which pairs fail:**

| pair you named | ADF t | verdict |
|---|---|---|
| **AUD/NZD** | -2.27 | **no** |
| **EUR/CHF** | -2.69 | **no** |
| CAD/NOK | -3.64 | yes |
| EUR/NOK | -4.03 | yes |

AUD/NZD and EUR/CHF — the two most commonly cited "cointegrated" FX pairs — **do not cointegrate in
this dataset.** EUR/CHF failed because the SNB's 2015 floor removal was a permanent structural break;
no amount of statistics recovers a relationship that was discontinued by policy. This is the first
empirical caution against the framework: the pairs most cited in trading literature are not the ones
the data supports.

## 3. The statistical property does not automatically become profit

This is the critical test, and it is where the framework meets reality.

Backtest: rolling 750-day window for beta, enter at |z| > 2, exit at |z| < 0.3, 2bp round-trip cost.

| pair | trades | return | Sharpe | hit rate | max DD |
|---|---|---|---|---|---|
| EUR/NOK | 15 | **-69.1%** | -0.67 | 50% | -75.3% |
| NOK/SEK | 18 | **-54.4%** | -0.32 | 51% | -56.9% |
| AUD/CAD | 12 | -16.9% | -0.37 | 51% | -28.8% |
| CAD/NOK | 19 | -13.6% | -0.17 | 51% | -32.9% |
| AUD/NOK | 19 | -17.4% | -0.06 | 51% | -40.0% |

**Every pair lost money, including the statistically cointegrated ones. Hit rates ~50-51%.**

Four reasons, and they are all structural:

**(a) The half-lives are far too long to trade.** 65–126 days. A mean-reversion trade holding for
2–4 months is exposed to the same macro forces as a directional trade. "Seconds to days" describes
arbitrage, not cointegration — the reversion timescale in real FX is *months*.

**(b) Beta is unstable out-of-sample.** The hedge ratio fitted on one window does not hold in the
next. This is the known weakness of naive Engle-Granger in live trading, and it is what destroyed the
results above.

**(c) The tails are large.** A z-score of 3 sigma looks like an opportunity and is frequently the
beginning of a permanent structural break (SNB 2015, NOK oil shocks). Fading extremes means being
short the tail.

**(d) The sample is one regime.** 30 years of data, but a handful of major structural breaks
dominate the outcomes.

**This does not prove pairs trading cannot work.** It proves that the naive configuration — in-sample
beta, fixed z-thresholds — does not work, which the literature already knew. A properly specified
version (Kalman-filtered dynamic beta, Ornstein-Uhlenbeck estimation, regime filters) might. But that
is a research programme, not a strategy, and it is what professional desks spend years building.

## 4. On-chain liquidity — the direction you want to focus

Here the data is more encouraging and the constraints are physical rather than statistical.

```
Total on-chain EUR-stable TVL:  $46,730,663   (~$47M)

largest EURC pools:
  EURC / Ethereum        $16,822,552   2.22% APY
  EURC / Base            $10,594,877   0.57%
  EURC-EUR / Ethereum     $4,600,349
  EURCV-USDC / Ethereum   $3,340,992   1.78%
  EURC-USDC / Base        $1,230,099  42.11% APY  <- unsustainable, thin
```

**Aerodrome on Base holds $397M TVL** — so the venue exists — but the **entire on-chain EUR-stable
market is about $47M** across 42 pools. That single number determines what is possible.

**What the $47M implies:**

1. **Range-bound market making (your idea #2) is the most viable of the four.** EURC/USDC does
   oscillate without drift, so the "asset runs away from you" problem genuinely does not apply. The
   concentrated-liquidity logic is sound.
2. **But capacity is tiny.** At $47M total, a market maker can deploy perhaps $50k–$250k before
   dominating a pool and suffering adverse selection. Above that, the position *is* the market.
3. **The 42% APY pool is a warning, not an opportunity.** $1.2M TVL with a 42% yield is either a
   temporary incentive programme or mispriced risk. Treat high APY on thin TVL as a signal of risk,
   consistent with the earlier Morpho finding (a market showed 41,889% APY on broken collateral).
4. **Impermanent loss is real but different.** Without drift, IL does not trend to infinity — but
   EUR/USD still moves 8-9% annualised, and a 2σ band is breached regularly.

**Cross-venue arbitrage (your idea #1) has the same capacity ceiling**, and is dominated by bots
with lower latency and no gas cost. On Base the observable flow measured earlier was $2,450 over 20
minutes with a median swap of $0.07 — that is MEV dust, meaning the spread is already being taken.

## 5. Where I land, honestly

**You were right about:**
- My momentum test did not address cointegration. That was a real gap.
- Cointegration exists in FX (5/36 pairs at 5%).
- Zero drift makes range-bound market making structurally sound in a way it is not in equities.
- Holding period is the key variable, and I had used the wrong one.

**The data says, and this is not a dismissal:**
- The most-cited pairs (AUD/NZD, EUR/CHF) do not cointegrate here.
- Naive cointegration trading lost money on **all five** tested pairs, including the cointegrated ones.
- On-chain FX is a **$47M** market. The mathematics may be sound and the capacity is still a rounding
  error against a $2B/day Solana DEX.
- Arbitrage legs are already being harvested at sub-cent sizes.

**The honest framing:** on-chain liquidity provision in range-bound FX pairs is the one approach here
with a genuine structural rationale rather than a statistical hope. It is a **capacity-constrained
market-making business**, not a strategy that scales — which means it is worth doing *if* the goal is
to learn and earn a small return on a small capital base, and not worth doing as a path to a large one.

**Which is a fair summary of this entire project.**

**Next step if you want it:** I would need pool-level data — actual swap volumes, fee accrual, tick
distribution, and time-in-range for EURC/USDC on Base — to tell you whether a specific concentrated
position would have been profitable. That data needs an RPC connection and a subgraph query, and I
would want to pull it before recommending a range. Say the word and I will.

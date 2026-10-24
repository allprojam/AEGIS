# Hybrid architecture: LP farm + webhook IL avoidance — tested

## The proposal

LP into a real-yield ETH/USDC pool, and use Pine-script signals firing webhooks to exit before
impermanent loss accrues. Base as the settlement layer for sub-second capital movement.

**The target pool is real.** Uniswap v3 WETH-USDC on Base:

```
TVL $163.2M   apyBase 24.04%   apyReward 0.00
```

**24.04% with ZERO rewards — 100% organic swap fees.** This is the best real-yield instrument found
in this entire project. The proposal is aimed at the right target.

## 1. The latency question — answered, and it is not the problem

Realistic webhook-to-exit budget on Base:

```
signal fires (candle close)      0.0s
webhook POST to server           0.3s
server logic + sign tx           0.5s
RPC broadcast                    0.3s
Base inclusion (2s blocks)       2.0s
                                 -----
total                            ~3.1s   (optimistic: no retries, no congestion)
```

**ETH moves 0.019% in that window (1 sigma).** Latency is a non-issue — your claim about Base's
sub-second settlement is correct and the execution layer is genuinely not the bottleneck.

**But the signal latency is:**
```
ETH 1h bar   moves 0.65% on average
ETH 4h bar   moves 1.29%
ETH 1 day    moves 3.16%
```

**A band break is detected on bar close, by which point the move has already happened.** You exit
after the event, not before it. The webhook cannot be faster than the candle.

## 2. The decisive test: LP+exit vs spot+exit, same signal

Same exit rule (band breach → move to USDC), 1 year of real hourly ETH:

| band | LP + webhook exit | 50/50 spot + same exit | winner |
|---|---|---|---|
| ±5% | $963.17 | **$974.82** | spot |
| ±10% | $1031.19 | **$1053.64** | spot |
| ±20% | $865.03 | **$893.98** | spot |

**Spot beat LP in every band, on the identical signal.**

**Why:** the exit is what avoided the loss, not the LP wrapper. Once you have a signal that takes you
to cash, the LP structure only adds:
- **divergence loss while in range** (you sell the winner and buy the loser),
- **gas per rebalance**,
- **range risk** (you can be out of range earning nothing).

**The "IL avoidance" is the directional exit. The LP contributes nothing to it.**

## 3. Regime dependency — LP beat spot in 3 of 6 blocks

| period | ETH | LP+exit | spot+exit | LP wins? |
|---|---|---|---|---|
| 2025-09-24 → 11-25 | **-30.9%** | 710.39 | **1053.64** | NO |
| 2025-11-25 → 2026-01-27 | 0.0% | **1052.40** | 1050.34 | **YES** |
| 2026-01-27 → 03-30 | **-29.6%** | 723.77 | **948.61** | NO |
| 2026-03-30 → 06-01 | -3.1% | **1089.36** | 1056.14 | **YES** |
| 2026-06-01 → 08-02 | -7.5% | **991.46** | 948.84 | **YES** |
| 2026-08-02 → 10-03 | **+45.0%** | 1023.38 | **1062.50** | NO |

**The pattern is clean and it is the answer:**

- **LP wins when ETH is flat** (0.0%, -3.1%, -7.5%) — fees accumulate, no bad exit fires.
- **Spot wins when ETH trends hard**, either direction (-30.9%, -29.6%, +45%) — because spot exits
  early and sits in cash, whereas LP is stuck holding inventory.

**LP is a short-volatility position. Spot is long the trend. The webhook does not change which one
you own — it only decides when you stop owning it.**

## 4. The honest architecture conclusion

**Your tools are good and the architecture is technically sound. The problem is category confusion
about what each component does.**

**What is real:**
1. **Base's execution layer works** — 3.1s round trip, confirmed feasible.
2. **The pool is real yield** — 24.04%, zero emissions, $163M deep. Verified.
3. **Webhooks and the Pine scripts work** — already demonstrated on your own chart.
4. **A band-break exit genuinely avoids large drawdowns** — LP+exit at ±10% returned +3.1% while
   ETH fell 35.7%.

**What does not hold:**
1. **"Avoiding IL" is not a mechanism — it is a directional exit**, and it was already available
   without LPing.
2. **Spot + the same signal beat LP + that signal in every band tested.** The LP added no value on
   top of the signal.
3. **LP only wins in flat regimes**, which means the entire edge is **regime detection**, not the LP.
4. **In-range time collapses as volatility rises** — at ±10% on a 60%-vol asset, the position was in
   range only 3.3% of the time in the trending sample.

**So the architecture question reduces to one thing:** *can your signal tell a range regime from a
trend regime?* If yes, LP the range and hold spot for the trend. If no, the LP is a coin flip against
spot and the extra machinery only adds gas and complexity.

## 5. The fee model caveat — stated plainly

My first pass produced absurd fee figures ($1,165 of fees on a $1,000 position) from a broken
proportional model. **I caught it and discarded it.** The results above use the **measured pool APR**
(24.04%) applied per hour while in range — which is defensible but still an assumption, because it
assumes your concentrated position captures the pool-average rate rather than more (concentrated
positions capture more per dollar while in range, less when out).

**Also flagged:** `bars_eth_usd_1d_9y.csv` is **mislabeled** — it is daily data (86,400s median gap)
despite the filename. I used `bars_eth_1h_365d.csv` (true hourly, 3,600s gaps) instead. Worth
checking what else is mislabeled.

## 6. What I would actually build

**Not the LP harness first — the regime classifier.** The measurement says the edge lives there, and
everything else is plumbing.

**If you do build it:**
1. **Regime gate:** classify range vs trend. LP only in range; hold USDC or spot otherwise.
2. **Band width tied to realised vol**, not fixed — ±10% was out of range 96.7% of the time in a
   trending sample.
3. **Exit on band break is correct** and it works — but recognise it as a **trend exit**, and hold
   spot (not LP) when the regime is trending.
4. **The real yield pool (24.04%, zero emissions) is the right venue** — that part of the plan is
   better than anything in the previous eight chapters.

**One genuine upside your framing identified:** if your signal is *good at range detection*, LPing
captures fees that spot cannot. That is a real, non-subsidised edge — the first one available that
isn't a short-vol premium in disguise. **But it is conditional on the classifier, not on the LP.**

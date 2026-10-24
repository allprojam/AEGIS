# EURC/USDC Pool-Level Extraction — Aerodrome, Base

**Pool:** `0xE846373C1a92B167b4E9cd5d8E4d6B1Db9E90EC7` — EURC/USDC 0.05%, Aerodrome Slipstream
(Uniswap-v3-style concentrated liquidity), created 2024-08-01.
**Window:** 90 days, 2026-07-09 → 2026-10-06. Source: GeckoTerminal OHLCV + trade tape.
**Data limits:** hourly candles cover 41 days (not 90); trade tape sampled 1,500 swaps over ~10.8h
of the final day. Tick-level liquidity distribution could not be pulled — no Base RPC access
(public endpoints return 403).

## 0. TWO FINDINGS THAT CHANGE THE PREMISE BEFORE ANYTHING ELSE

**Finding A — the pool does not trade at parity, and your 1.05–1.10 band is below the market.**

```
90d price range      1.1215 .. 1.1714
last close           1.1258
your assumed range   1.05 .. 1.10        <- ENTIRELY BELOW the traded range
```

EURC is trading **11–22% ABOVE** 1.00 USDC across the whole window. EURC/USDC is not a near-parity
stablecoin pair — it is a **EUR/USD exchange-rate exposure**. A band at 1.05–1.10 would have been
**never in range for 90 days** and would have earned zero fees. This is the single most important
correction in this report: the strategy premise assumed a pegged pair and the asset is not pegged.

**Finding B — turnover is 3x TVL per day, which is the classic toxic-flow signature.**

```
mean daily volume     $3,754,006
current TVL           $1,231,028
volume / TVL          3.05x per day  (278x over 90 days)
```

A genuine stablecoin pair turns over a few percent of TVL daily. **3x/day means the pool is being
repeatedly arbitraged**, not used for payment or holding. Section 3 confirms the mechanism.

## 1. Volume-to-TVL Ratio & Fee APR

```
90-day total volume      $337,860,544
mean daily volume        $  3,754,006
median daily volume      $  4,038,134
```

**Raw swap-fee APR by tier (excludes all emissions):**

| fee tier | 90d fees | raw fee APR |
|---|---|---|
| 0.01% | $33,786 | **11.1%** |
| **0.05%** | $168,930 | **55.7%** |
| 1.00% | $3,378,605 | 1113.1% |

The pool is a **0.05% tier** (per pool name), so the raw swap-fee APR is **≈55.7%**.

**Isolating organic from emissions:** DefiLlama reported this pool at **42.11% APY**. Raw swap fees
alone compute to **55.7%** — *higher* than the reported total. That means **the reported APY is not
emissions-inflated**; if anything it is understated, or the reported window differs. This is the
opposite of the concern raised: emissions are **not** the driver here.

**But that 55.7% is not harvestable, for the reason in Section 3.** The 1,113% at the 1% tier is a
red flag in the other direction — it indicates the pool carries far more volume than a 0.05% tier
should, consistent with arbitrage rather than organic flow.

## 2. Price Deviation Envelope

```
90d range              1.1215 .. 1.1714      (4.5% total span)
max deviation above     +2.31% from window start
max deviation below     -2.05%
realised daily vol      0.366%
annualised vol          6.99%
final vs start          -1.67%
```

**Max drawdown/expansion from parity is meaningless as "deviation from 1.00"** — the correct
framing is deviation from the *EUR/USD rate*, and 6.99% annualised vol is consistent with EUR/USD.

**Tick distribution and active-tick depth could not be extracted.** This requires `slot0()`,
`liquidity()`, and tick bitmap calls against the pool contract. No Base RPC was reachable from this
environment. Marked as a gap, not estimated.

## 3. Flow Toxicity / Adverse Selection — the decisive section

**Swap size distribution (1,500 swaps sampled):**

```
median swap size      $   515.24
mean swap size        $   862.18
90th percentile       $ 1,988.69
99th percentile       $ 4,138.42
largest single swap   $ 5,727.17
```

**Bot detection — the 0x88888888 cluster:**

```
9 addresses with the 0x88888888 vanity prefix
22 swaps = 7.3% of all swaps
volume  = $42,583 = 16.5% of sampled volume
```

**Nine distinct addresses deliberately mining the same vanity prefix** is a single operator running
a fleet of arbitrage contracts. That is not ambiguous.

**Concentration:**

```
unique swapper addresses                    148
top 10 addresses = 51.2% of all volume
addresses with >=3 swaps in 2.1h (14% of addrs) = 56.1% of volume
```

**Machine cadence:**

```
median inter-swap gap   6.0 seconds
gaps < 5 seconds        44.1%
gaps < 1 second         11.4%
```

**A median gap of 6 seconds between swaps, with 44% under 5s, is automated routing.** Human retail
flow does not arrive on a 6-second cadence.

**Retail share (swaps under $1,000):**

```
< $100      17.3% of count      0.5% of volume
< $1,000    66.7% of count     27.9% of volume
```

**Two-thirds of swaps are under $1,000 but carry only 28% of volume.** The pool's economics are
driven by the minority of large, repeated, machine-generated trades.

**Conclusion on toxicity: this is a predominantly toxic flow pool.** The fee APR in Section 1 is
largely compensation for being picked off by arbitrageurs — the 3.05x daily turnover is the arb
bots cycling, and a market maker in this pool is the counterparty.

## 4. Time-in-Range & Divergence Loss by Band

Static band anchored at window start, never rebalanced (v3 behaviour), start price 1.1450:

| band | range | time-in-range | end price |
|---|---|---|---|
| **±0.75%** | 1.1364 – 1.1535 | **44.4%** | **OUT** |
| **±1.5%** | 1.1278 – 1.1621 | **80.0%** | **OUT** |
| ±3.0% | 1.1106 – 1.1793 | 100.0% | in |
| ±5.0% | 1.0877 – 1.2022 | 100.0% | in |

**The tight bands fail in exactly the way the research predicted.** ±0.75% was in range only 44% of
the time and finished out of range — meaning the position is 100% in the losing leg (single-sided
inventory) at the end. ±1.5% spent 80% of the time in range and *still* finished out. Both
accumulated divergence loss while earning fees only part of the time.

**Only ±3.0% or wider stayed in range through the full window.** But at ±3% the capital is spread
thin, so fee capture per dollar falls — the same trade-off, just shifted.

## Bottom line

**The 47M-capacity constraint found earlier was optimistic for this pool.** This specific pool is
**$1.23M TVL**, and the practical constraints are worse than capacity:

1. **The premise was wrong.** The pair trades at 1.12–1.17, not 1.05–1.10. A parity band earns zero.
2. **The flow is 56% machine-driven** with a 6-second median cadence and a 9-address arb fleet.
3. **Turnover of 3x TVL/day is toxic**, not organic volume.
4. **Tight bands fail**: ±0.75% and ±1.5% both ended out of range despite 44–80% time-in-range.
5. **The 55.7% raw fee APR is a toxicity premium**, not an inefficiency to harvest. A market maker
   here is the exit liquidity for arbitrageurs.

**This does not mean range-bound market making is impossible — it means this pool is the wrong
instrument for it**, and the analysis that recommended the approach underestimated how much of the
on-chain FX flow is already being harvested by bots.

**What would change the answer:** a wider band (±3%+), accepting lower fee intensity; a pool with
genuinely organic flow (higher retail share, lower turnover/TVL); or measured tick-level data, which
requires RPC access this environment does not have.

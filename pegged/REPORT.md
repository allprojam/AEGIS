# Which of A / B / C deserves compute

**Answer: B, and only B. I ran it. The result splits your option B into one that works and two that
do not.**

## B, tested — "truly pegged stable pairs"

I took the three categories you named and measured each. 90 days (50 for USDT/USDC), same method as
the EURC work.

| pool | ann. vol | turnover/day | ±0.75% in-range | ±1.5% | ±3% | verdict |
|---|---|---|---|---|---|---|
| **USDT/USDC** | **1.69%** | 6.02x | **100.0%** | 100.0% | 100.0% | **FEASIBLE** |
| EURC/USDC | 6.99% | 3.05x | 44.4% | 80.0% | 100.0% | fails |
| **cbBTC/WBTC** | **39.47%** | 0.70x | **2.0%** | 2.0% | 4.0% | **FAILS** |
| **wstETH/WETH** | **46.50%** | 0.00x | **2.0%** | 2.0% | 3.0% | **FAILS** |
| **cbETH/WETH** | **53.20%** | 0.96x | **2.0%** | 2.0% | 3.0% | **FAILS** |

**Only USDT/USDC is a genuinely pegged pair. The other two categories are not, and the reason is
structural, not incidental:**

- **cbBTC/WBTC at 39.47% vol** is barely different from BTC itself. These are two *different*
  wrapped representations with different custody, redemption, and bridge mechanics. The ratio
  carries redemption and de-peg risk, so it does not sit near 1.00.
- **LST/ETH pairs (wstETH, cbETH) at 46–53% vol** are **trending by design.** A liquid staking token
  accrues staking yield *against* ETH — the ratio is engineered to drift upward. A range band on a
  pair whose ratio increases by design is the same mistake as the 1.05–1.10 EURC band: the band is
  wrong from the start.

**A clean monotonic relationship emerges, and it is the actual finding:**

```
vol 1.69%  ->  ±0.75% band survives 100.0% of the time   USDT/USDC
vol 6.99%  ->  ±0.75% band survives  44.4%               EURC/USDC
vol 39.5%  ->  ±0.75% band survives   2.0%               cbBTC/WBTC
vol 53.2%  ->  ±0.75% band survives   2.0%               cbETH/WETH
```

**Volatility is the predictor. Nothing else matters.**

## The economics, corrected

My first pass had a units bug (a missing ×100). Corrected, on pool-level terms:

| pool | fee tier | fee yield/yr | full-range LVR/yr | ratio |
|---|---|---|---|---|
| EURC/USDC | 0.05% | 55.7% | **0.061%** | 911x |
| USDT/USDC | 0.05% | 110.0% | **0.004%** | 30,674x |

**This corrects a claim in the previous report.** I said the 55.7% APR was "pure LVR compensation."
**That is not supported.** Full-range LVR on EURC/USDC is **~6 basis points per year** — the fee yield
exceeds it by ~900x. LVR is far too small to explain the yield.

**What actually explains it:** the 55.7% is real fee income, but it accrues to whoever holds the
*in-range* position at the moment of the swap. With a ±0.75% band in range only 44% of the time,
and capital concentrated 267x, the *deployed* capital captures fees at a very high rate while being
stranded the other 56% — which is the single-sided-inventory loss. **The problem was never LVR. It
was time-in-range.** That is what Section 4 of the previous report showed and this confirms.

**Note USDT/USDC's 6.02x turnover is HIGHER than EURC's 3.05x.** High turnover is therefore *not*
inherently toxic. EURC's turnover is toxic because the price moves 7% a year; USDT/USDC's is benign
because the price does not move — arbitrageurs cycle a 2bp spread that cannot profitably be pushed
further.

**The residual risk is a USDT depeg tail.** A ±0.75% band survives normal chop 100% of the time and
would be destroyed by a 2022-style USDT break to 0.95. **This is negative skew again** — the same
shape as the variance-risk premium, the carry trade, and the politicians' copy-trade. Every edge this
project has found is a short-volatility trade. Worth stating plainly.

## A, assessed — the stale-quote arb

**Not worth compute, for two reasons.**

**1. A category error in the premise.** FastMCP is the Anthropic Model Context Protocol server
framework — an LLM tool-integration layer. It is **not** a private RPC, mempool, or latency service
and confers no execution advantage. The relevant infrastructure would be a private transaction relay
(Flashbots-style bundles, bloXroute, or a paid low-latency Base RPC).

**2. The data to answer your question is exactly the data this environment cannot reach.** Latency
profile and profitability require mempool visibility, block-level inclusion timing, and per-tx gas/
priority-fee decomposition. **Base RPC is unreachable from here (403 on every public endpoint).** So
the honest statement is: **untestable in this environment**, not "tested and bad."

**What the existing evidence implies** — the 0x88888888 fleet (9 addresses, 16.5% of volume),
6-second median cadence, 44% of gaps under 5s, 56% of volume from addresses with ≥3 swaps in 2 hours.
That is a professional operation with infrastructure. **The sniper side is a latency arms race with
negative expected value for a new entrant** — you would be competing against bots that already hold
the block-builder relationships. It is a red ocean, and unlike B it cannot be validated cheaply.

## C, assessed — wrap up the FX chapter

**Agreed, and it is not a compute question.** The FX chapter ends with:

1. Directional momentum on majors: all six configurations negative Sharpe (measured).
2. Cointegration exists (5/36 pairs) but naive trading lost on **all five** cointegrated pairs.
3. EURC/USDC: wrong price premise, 56% machine flow, tight bands stranded 44% of the time.
4. On-chain EUR is a **$47M** market.

**Caveat before closing it:** the FX chapter's *negative* result is about **retail passive LPing
without hedging**. It does not falsify FX as a market. But nothing in this project has found a
configuration where a retail participant had an edge in it, so closing the chapter is correct.

## Recommendation

**B, restricted to genuinely pegged pairs only — which in practice means USDT/USDC and equivalents.**

That is where the compute should go, and it is cheap: the pipeline now exists. What it does **not**
justify is cbBTC/WBTC or LST/ETH range-making, both of which fail for structural reasons (redemption
drift and designed yield accrual) rather than for lack of testing.

**The honest summary of the whole investigation:** the only on-chain configuration that survives
measurement is **tight-band liquidity provision on a pair whose price genuinely does not move**,
earning a small fee while accepting a depeg tail. That is a real, modest business with a negative
skew — and it is the same trade as everything else this project rejected on those grounds.

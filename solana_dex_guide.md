# Solana DEX Guide — measured, not vibes

## 1. The surprise: Solana is MORE fragmented than Ethereum

77 venues with volume, total **$2,355M/day**. Top-5 concentration is only **55%**:

| venue | 24h | share | cumulative |
|---|---|---|---|
| PumpSwap | $306.6M | 13.0% | 13.0% |
| Orca | $273.3M | 11.6% | 24.6% |
| BisonFi | $234.2M | 9.9% | 34.6% |
| pump.fun | $187.5M | 8.0% | 42.5% |
| Raydium | $152.7M | 6.5% | 49.0% |
| Meteora DLMM | $144.4M | 6.1% | 55.1% |

**This inverts the earlier framing.** Solana does not have "unified" liquidity in the sense of one
deep venue. It has hundreds of shallow ones. Ethereum's problem is fragmented *settlement*; Solana's
is fragmented *venues*.

## 2. Why that does not matter — and this is the actual finding

**Jupiter routing, USDC → SOL, measured live:**

| size | effective price | price impact | route |
|---|---|---|---|
| $100 | 120.39 | **0.00%** | TesseraV |
| $1,000 | 120.39 | **0.00%** | TesseraV |
| $5,000 | 120.39 | **0.00%** | Kipseli → TesseraV → AlphaQ |
| $25,000 | 120.39 | **0.00%** | TesseraV → HumidiFi → BisonFi |
| **$100,000** | 120.40 | **0.01%** | Kipseli → BisonFi → TesseraV |

**A $100,000 order executes at 0.01% impact.** The fragmentation is *abstracted away* by the
aggregator, which splits the order across venues and reassembles the best price.

So the aggregator is not a convenience. **It is the execution layer**, and it is the reason a
fragmented chain is still usable.

## 3. Long-tail tokens — where it actually degrades

**BONK:**

| size | impact |
|---|---|
| $100 | 0.00% |
| $1,000 | 0.09% |
| $5,000 | 0.20% |
| $25,000 | **0.41%** |
| $100,000 | **failed — no route** |

**JUP:**

| size | impact |
|---|---|
| $100–$1,000 | 0.00% |
| $5,000 | 0.01% |
| $25,000 | 0.08% |
| $100,000 | 0.16% |

**Majors route cleanly to six figures. Mid-cap tokens degrade gently. Long-tail tokens break
entirely.** The $100k BONK failure is the important data point: it is not a worse price, it is
*no price*. That is the real risk of trading thin assets — you find out at the moment you need to
exit.

## 4. Aggregators

| aggregator | 24h | 7d |
|---|---|---|
| **Jupiter** | $350.6M | $2,718.9M |
| DFlow | $291.1M | $2,227.2M |
| OKX Swap | $100.7M | $1,035.5M |
| Titan | $48.4M | $275.2M |

Jupiter remains the default. DFlow is a genuine second option with real volume — worth comparing a
quote against Jupiter before a large order, since they split routes differently.

## 5. Practical recommendation

1. **Route through an aggregator, always — do not pick a single DEX.** The venue list is noise;
   the router is the product. Manually choosing "the best DEX" is strictly worse than aggregating.
2. **Execute majors (SOL, USDC, JUP) freely to $100k** at negligible cost.
3. **Treat $25k+ in a long-tail token as an exit-risk problem**, not a price problem.
4. **Verify the route, not just the output number.** The quoted price already includes the split;
   what it does not tell you is whether that route will still exist when you sell.
5. **Ignore the venue rankings.** Orca, Raydium, Meteora and the rest are *liquidity sources the
   router uses*. You are not choosing between them — the router is.

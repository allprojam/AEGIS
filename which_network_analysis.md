# Which Network Would I Trade On — Brutally Honest

All figures measured live this session.

## The table

| chain | TVL | DEX 24h | DEX 30d | fees 30d | velocity (days) | fee/TVL |
|---|---|---|---|---|---|---|
| Solana | $6,785M | **$2,057M** | $77,929M | $448.2M | **3.3** | 6.61% |
| Base | $6,464M | $1,306M | $29,843M | $66.2M | 4.9 | 1.02% |
| Ethereum L1 | $54,261M | $1,098M | $41,411M | $345.5M | 49.4 | 0.64% |
| BSC | $5,798M | $841M | $33,545M | $109.0M | 6.9 | 1.88% |
| Hyperliquid | $1,193M | $275M | $9,816M | $167.8M | 4.3 | **14.07%** |
| Arbitrum | $1,436M | $157M | $5,761M | $19.7M | 9.1 | 1.37% |
| **Flare** | **$133.7M** | **$5M** | **$183M** | **$0.7M** | **26.7** | 0.52% |
| **XRPL** | **$45.4M** | **~$0** | **~$0** | ~$0 | — | 0.00% |

"velocity" = TVL / daily volume = how many days to turn over the entire pool. Lower is more liquid
relative to size.

## On Flare, since it is the user's favourite

**Flare's total DeFi TVL is $133.7M. That is 0.25% of Ethereum's and 2% of Solana's.**

- 24h DEX volume: **$5M**
- 30d fees: **$0.7M**
- velocity: **26.7 days** — eight times slower than Solana

The user's framing — *"what XRP wishes it were"* — is generous but directionally revealing.
**XRPL's DeFi TVL is $45.4M with effectively zero DEX volume and zero fees.** XRPL's on-chain DeFi
is not a functioning trading venue at all. So Flare does beat XRPL on this measure: **$133.7M vs
$45.4M, and $5M/day vs nothing.** That part of the instinct is correct.

But "better than XRPL's DeFi" is a low bar, and clearing it does not make Flare tradeable. Note
where Flare's $133.7M sits against the earlier RWA figure touted on the crypto show — **$2.5B of RWA
"on the ledger"** — because those are different claims: RWA *tokenised* on a network is not the same
as RWA *traded* on it. The $133.7M is what is actually deployed in DeFi.

## What "which network would I trade on" actually turns on

For a trader, the question is not TVL. It is: **can I move a realistic size without moving the
price?**

Rule of thumb: stay under 1% of daily volume.

| chain | 1% of 24h DEX volume |
|---|---|
| Solana | $20.6M |
| Base | $13.1M |
| Ethereum L1 | $11.0M |
| BSC | $8.4M |
| Hyperliquid | $2.8M |
| Arbitrum | $1.6M |
| **Flare** | **$50,000** |
| **XRPL** | **$0** |

## My answer, brutally

**Solana**, for execution — highest raw DEX throughput, fastest pool turnover, and (from the prior
analysis) the only measured favourable asymmetry. It is where the actual trading happens.

**Hyperliquid** for a specific style — leverage without leaving self-custody. $275M/day against
$1.19B TVL gives it the highest fee efficiency in the table (14.07%), meaning the venue is genuinely
*used* rather than merely holding value. If the goal is perps rather than spot, this is the one
structure that did not exist a few years ago and it solves a real problem the user already cares
about (custody).

**Ethereum L1** for size and safety. Its velocity (49.4 days) looks terrible, but that is because
$54B sits there largely as *settlement and collateral*, not as trading volume. For a position large
enough that slippage matters, ETH's depth is the reason to be there.

**Base** as the pragmatic middle: L2 cheapness, Coinbase distribution, $1.3B/day of real volume.

**I would not trade on Flare.** Not as a judgement on the technology — Flare's actual thesis
(FTSO oracle, data from other chains) is a genuine idea, and the user may be right that it is
underrated. But **underrated infrastructure is not a trading venue.** With $5M/day, a $50k order is
already a meaningful fraction of daily flow, and a $500k order would be the market. You cannot trade
a thesis you believe in on a chain that cannot absorb your order.

**The distinction that matters:** Flare may be a good *investment thesis* and is simultaneously a
**bad place to execute.** Those are different questions, and conflating them is exactly how people
end up holding something they cannot exit.

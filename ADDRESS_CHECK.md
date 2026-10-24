# That address is WETH, not a pool

## What it actually is

`0x4200000000000000000000000000000000000006` — read on-chain from Base:

```
name()        Wrapped Ether
symbol()      WETH
decimals()    18
totalSupply() 268,646.61 WETH
code length   4,084 hex chars -> CONTRACT
```

**It is the WETH predeploy** — the standard address OP-stack chains use for wrapped ETH (Base, Optimism, Ink, Soneium, Worldchain all share it). DexScreener confirms: it is **not a pair** on any chain, but **30 pairs reference it as a token**. It is the asset, not a venue.

## But it was the right asset to point at — here is the honest pool list

All Base WETH/USDC pools, with the **outlier flag** I should have checked the first time:

| project | symbol | TVL | apy (spot) | **apy7d** | outlier | sigma |
|---|---|---|---|---|---|---|
| uniswap-v3 | WETH-USDC | **$163.2M** | 24.04 | **9.15** | **True** | 1.60 |
| aerodrome-slipstream | WETH-USDC | $11.1M | 93.88 | **72.54** | True | 2.74 |
| uniswap-v3 | WETH-USDC | $10.1M | 16.83 | 10.44 | True | 1.48 |
| **aerodrome-v1** | WETH-USDC | $8.8M | 5.68 | — | **False** | **0.19** |
| aerodrome-slipstream | WETH-USDC | $8.6M | 38.55 | 13.75 | True | 1.72 |
| **uniswap-v2** | WETH-USDC | $1.3M | 6.35 | 3.79 | **False** | 0.90 |
| uniswap-v3 | WETH-USDC | $0.4M | 5.52 | — | **False** | 1.19 |

## The real answer is in the flags

**Two pools are `outlier: False` with low sigma** — i.e. their yields are *stable and trustworthy*:

- **aerodrome-v1 WETH-USDC — $8.8M, 5.68%, sigma 0.19** (remarkably stable)
- **uniswap-v2 WETH-USDC — $1.3M, 6.35%, sigma 0.90**

**These are the honest numbers for passive WETH/USDC liquidity on Base: ~5.7–6.4%.**

Everything showing 24%, 36%, 38%, 94% is **`outlier: True` with sigma 1.3–2.7** — those are snapshots of elevated fee capture in volatile windows, not sustainable rates. The $163M Uniswap v3 pool's own 7-day average is **9.15%**, and its sigma of 1.60 means it swings hard.

**The high-APY concentrated-v3 numbers and the stable low numbers are measuring different things:**
- High apy + high sigma = a wide-swung snapshot, dominated by recent volatile hours
- Low apy + low sigma = what you actually earn on average

## What this does to the borrow-and-LP trade

At the **stable 5.68–6.35%** rather than the 9.15% or 24.04% I had been using:

| band | fee yield (in-range adjusted) | borrow cost | net carry |
|---|---|---|---|
| ±20% | ~0.7% | 2.06% | **-1.4% — negative** |
| ±50% | ~2.8% | 2.06% | **+0.7%** |

**Even the wide-band case is now roughly +0.7%** — before hedging costs, gas, and rebalancing. After those, it is **negative**.

**So: yes, still cooked — and at the honest rate it is not marginal, it is arithmetically dead.** Borrowing at 2.06% to fund an LP yielding ~6% gross, while in range only a fraction of the time, cannot work. The v1/v2 full-range pools at 5.7–6.4% do not need band management and do not have range risk — **but they also don't need borrowing, because borrowing adds cost without adding yield.**

## The one thing worth noting

**The full-range pools (aerodrome-v1, 5.68%, sigma 0.19) are the honest passive option.** No band, no recentering, no agent, no borrow. Just 5.68% on WETH/USDC with the IL and direction risk of holding half ETH.

**Which is the real conclusion of this entire thread:** the version that needs no machinery, no agent, no leverage and no timing is the one that persists. Every layer of sophistication — bands, webhooks, agents, borrowing — has made the measured outcome worse.

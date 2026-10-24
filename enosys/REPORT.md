# Enosys Loans — the actual product, measured

## 1. What it is

From their own site (`enosys.global/products/loans`):

> "The first Collateralized Debt Position protocol backed by XRP. **Enosys Loans is a friendly fork of
> Liquity V2**... Borrowers are issued a stable currency backed by their collateral, and are able to
> **set their own interest rates**."

| | |
|---|---|
| **DefiLlama TVL** | **$9,285,351** (category: CDP) |
| Collateral accepted | **FXRP, stXRP, wFLR, sFLR** |
| Debt asset | **CDP Dollar** — totalSupply **5,004,640 CDP** |
| Revenue split | **75% of protocol revenue to the Stability Pool** |
| Extra incentives | APS and rFLR |
| Note | wFLR keeps earning delegation rewards while used as collateral |

**The Stability Pool is the actual yield product** — 75% of protocol revenue. That is what a
"loan product" is here: you deposit CDP into the pool, and the pool is what liquidates
under-collateralized borrowers.

## 2. The LP fee is negligible — measured

The largest CDP pool is **CDP / USDt0 0.05%** (`0x975f0369...`):

```
TVL              $1,231,861      (24.6% of the entire CDP supply, in one pool)
median daily vol $   82,998
fee tier         0.05%

median-volume fee APR:  1.23%
mean-volume fee APR:    1.28%
```

**1.2% gross.** Not a business. So LPing the CDP pair is out on arithmetic alone, same as USDT/USDC.

## 3. The peg is already deviating — and this is the finding

CDP Dollar price vs USDt0, 100 days:

```
range           0.985231 .. 1.001505
worst deviation -1.4769%      <- it has already traded 1.5% below peg
current         0.994882 = -0.51% below peg
annualised vol  9.092%
```

| asset | annualised vol |
|---|---|
| USDT/USDC | 1.69% |
| EURC/USDC | 6.99% |
| **CDP Dollar** | **9.09%** |
| APS | 236.50% |

**A stablecoin that has already printed -1.48% is not a stablecoin you can build a band around.**
Compare: in 100 days USDT/USDC never moved more than 0.35% from par. CDP moved 1.48%. That is a
**4x wider excursion**, and it means any tight band is already known to be breachable by this
asset's own history.

That is expected for a CDP backed by **XRP** — a collateral asset whose own volatility passes
straight through to the peg's stability. The peg is only as firm as the collateral.

## 4. The Stability Pool is genuinely different — and I should say so

This is the first structure in this project that is **not** simply selling crash insurance, and the
distinction is real:

- A Stability Pool depositor supplies CDP that is used to **liquidate** under-collateralized
  positions, and **receives the collateral at a discount**.
- So in a crash, you do not just lose — you **acquire FXRP below market**. There is genuine value
  capture, not only premium collection.
- This is why Liquity-style Stability Pools have historically been one of the few DeFi structures
  with a defensible risk/reward story.

**But the trade is still:** you are the backstop, and you receive the collateral *while it is
falling*. Liquity's own history shows Stability Pools getting filled with ETH in March 2020 and
again in 2022 — the depositors did eventually profit, but only after sitting through the drawdown
holding an asset that kept falling, with their CDP fully converted to collateral.

**The honest framing:** it is a *better* version of the trade — you get paid in discounted assets
rather than only in fees — but it is still a trade that pays you to be the buyer of last resort
during a crash.

## 5. The depth problem is worse than it looks

```
CDP total supply        5,004,640
CDP/USDt0 pool TVL     $1,231,861   = 24.6% of face value
```

**One quarter of the entire CDP supply already sits in a single pool.** If 10% of CDP supply tried
to exit, that is $500k against a $1.23M pool — 0.4x the pool, and the excursion to -1.48% is likely
the market showing what a fraction of that flow does.

## 6. What I could not measure — stated plainly

- **Stability Pool current APY**: I could not locate the Stability Pool contract address. Probing
  the CDP token's owner (`0xdedda089...`, a contract) returned only revert-on-empty for every
  Liquity-style getter. **I have no measured figure for the pool's yield**, so I am not going to
  quote one. That is the single number that would decide this, and it needs the contract address
  from their docs or the front-end.
- **Liquidation parameters**: CCR, MCR, mint caps, per-collateral LTVs — not retrieved.
- **APS/rFLR incentive rates**: stated as "additional incentives" with no figure given.

## Verdict

**Better structure than everything before it, and still not the trade I would take at this size.**

**What is genuinely attractive:** the Stability Pool captures discounted collateral rather than only
fees. That is a real mechanism, not a dressed-up short-vol position, and it is the first structure in
this project I would call structurally sound.

**What stops me:**
1. **CDP has already deviated -1.48%** in a 100-day window, on a $5M stablecoin. That is not a peg
   robust enough to build on.
2. **9.09% vol** — higher than EURC, which already failed every tight-band test.
3. **$1.23M pool holding 24.6% of all CDP** — the depth is not there.
4. **LP fee APR 1.23%** — the passive option is out.
5. **The Stability Pool yield is unmeasured** — I could not get the number.

**The next step is one API call, not a position.** If you want this chapter to be real, get the
Stability Pool contract address from their docs or front-end and I will pull its actual TVL, the
realised liquidation history, and the true yield — including how much of it came from liquidations
versus APS emissions. **If the yield is mostly APS emissions, it is not a yield — it is a subsidy
that ends.** That distinction decides the whole thing, and it is currently unmeasured.

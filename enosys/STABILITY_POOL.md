# Enosys Loans Stability Pool — the number we went looking for

## What I got and what I did not

**Got:** the full verified contract set on Flare Blockscout, the real collateral breakdown from
DefiLlama's registry, live on-chain CDP supply, FXRP volatility, the CDP peg history, and the pool
fee economics. **The system collateral ratio — the number that decides this — is measured.**

**Did not get:** the Stability Pool's own TVL and realised yield. I located a verified
`StabilityPool` contract (`0x37FfD5d6...`) but it reads **all zeros** — `getTotalBoldDeposits() = 0`,
`boldToken = 0x0`, and zero CDP balance. Same for `ActivePool`, `TroveManager`, `BorrowerOperations`
and `CollateralRegistry` at the addresses Blockscout returns: every getter returns 0 and no
EIP-1967 proxy slot is set. **These are unused deployments, not the live ones.** DefiLlama's registry
points at a Songbird address (`0x72D93201...`), and the Flare RPC caps `eth_getLogs` at **30 blocks**,
so I cannot enumerate the live branch by event scanning either.

So the Stability Pool APY remains unmeasured. **But I can now bound the thing it protects.**

## The decisive measurement: system collateral ratio

```
CDP supply (on-chain)        5,004,640 CDP
Collateral (DefiLlama, today)   $9,285,351
  FXRP    $7,303,010   (78.7%)
  WFLR    $  855,664
  SFLR    $  657,203
  STXRP   $  469,474
SYSTEM CR                    185.5%
```

**Buffer to the liquidation trigger: 35.5 percentage points. Collateral must fall 19.2% to reach
CCR 150%.**

## Why 19.2% is not a comfortable buffer

The collateral is **78.7% FXRP**, and I measured FXRP's own volatility:

| | value |
|---|---|
| FXRP annualised vol | **65.5%** |
| FXRP daily vol | **3.43%** |
| FXRP max drawdown (100d) | -15.2% |
| **FXRP worst single day** | **-9.1%** |

```
a 19.2% fall = 5.59 daily sigmas
single-day probability ~ 1 in 85,000,000  (i.e. never, in one day)
BUT as a random walk: sigma*sqrt(T) = 19.2%  ->  T = 31 trading days
```

**A 19.2% decline in FXRP is a 31-day event, not a once-in-centuries event.** And FXRP has already
printed **-9.1% in a single day** in the last 100 days — **half the required buffer, in one session.**

That is the whole risk picture. The system is not under-collateralized today (185.5% is healthy),
but the buffer is **one XRP news cycle deep.**

## What a Stability Pool depositor actually faces

When CR breaches 150%, the Stability Pool absorbs the debt and receives the collateral. At that
moment:

1. **You are buying FXRP with your CDP** — and you are buying it *because it just fell 19%+*.
2. You receive a **liquidation penalty** (Liquity V2 typically 5–10% for SP liquidations) as
   compensation, so you get a discount to an already-depressed price.
3. **Your CDP position is gone** — converted entirely into FXRP at the worst moment.
4. You then hold FXRP and must decide whether to hold or sell, into whatever caused the 19% drop.

**This is exactly the March-2020 / May-2022 Liquity pattern**: Stability Pool depositors were filled
with ETH, sat through further drawdown, and eventually profited — but only those who could hold
indefinitely. The mechanism is sound; the timing is brutal.

## The peg is already telling you something

```
CDP/USDt0: last 0.994882 (-0.51%), 100d worst 0.985231 (-1.48%)
vol 9.09% annualised
```

For comparison, USDT/USDC never moved more than **0.35%** from par in 100 days. **CDP has moved
1.48% — 4x wider** — and that is with a 185.5% system CR, i.e. *before* any stress. A CDP that
wanders 1.5% at rest will wander further when 78.7%-XRP collateral moves.

## The LP option, for completeness: dead

```
CDP/USDt0 pool: TVL $1,231,861  median vol $82,998  fee 0.05%
median-volume fee APR: 1.23%
```
Same as USDT/USDC. 1.2% gross does not cover a -60% tail. Out.

## Verdict

**The structure is the best this project has found. The buffer is too thin and the yield is
unmeasured.**

**Better than everything before it, and I want to be precise about why:**
- Liquity V2's Stability Pool pays you in **discounted collateral**, not just fees. That is genuine
  value capture, not premium collection.
- The system is **185.5% collateralized**, not 100% — there is a real 35.5pp cushion.
- Collateral is **XRP-linked**, which is a genuine thesis if you hold one, and it matches the
  "atomic sovereignty" interest that started this.

**What stops it:**
1. **19.2% buffer vs a 65.5%-vol collateral** — a 31-day event at 3.43% daily vol.
2. **FXRP printed -9.1% in one day** in the last 100 days. Half the buffer, one session.
3. **The peg already deviates -0.51%, worst -1.48%** with no stress present.
4. **The yield is unmeasured** — and *this is the deciding gap.*

## The one thing to do next

**Get the Stability Pool APY, split by source.** If it is predominantly **liquidation revenue**, a
small unlevered position is defensible: you are being paid a real, structural premium to be the
buyer of last resort on XRP-collateralized debt, with a 35.5pp cushion. If it is predominantly
**APS and rFLR emissions**, it is not a yield — it is a subsidy, and the 185.5% CR number becomes
irrelevant because your return does not depend on the protocol working, only on the emissions
continuing.

**I cannot make that call without the number, and I will not guess it.** The contract address is
on their front-end — one page fetch, or you can read it off the deposit transaction. Give me that and
this becomes answerable in one call.

**What I can say now: this is the first structure in this project I would consider at all, and it is
disqualified by exactly one unmeasured figure.** That is a very different position from every
previous chapter, where the arithmetic itself said no.

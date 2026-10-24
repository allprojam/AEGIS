# APS / USDt0 on Flare — measured

## 1. Your supply claim is exactly right — verified on-chain

```
APS 0xff56eb5b1a7faa972291117e5e9565da29bc808d
  symbol()        APS
  name()          Apsis
  decimals()      18
  totalSupply()   14999999999959013607887 wei
                  = 14,999,999,999.959 APS
                  = 15,000.0 APS   <- VERIFIED
```

Called directly against Flare RPC (`flare-api.flare.network`, chain 14). **The 15k figure is real.**

Price: **$557.60/APS** → **$8.36M FDV**. Pool created 2025-05-02.

## 2. But here is the inversion — low supply is not low risk

The reasoning was that a small total supply makes a better market to make. **Measured, the opposite
is true.** I pulled APS's own price history (100 days):

| | annualised vol | max drawdown | worst single day |
|---|---|---|---|
| **APS** | **236.5%** | **-60.3%** | **-57.6%** |
| EURC/USDC | 6.99% | — | — |
| USDT/USDC | 1.69% | -0.35% | — |

**APS's volatility is 140x USDT/USDC's — which is ~19,600x the variance.** Volatility scales with
variance, and as a market maker your loss term scales with variance, not volatility.

**A ±0.5% band on an asset with 236% annual vol:** daily vol is 12.38%, so the band is
**0.04 daily sigmas wide**. It would be exited essentially immediately. There is no band you can
set that survives this asset's normal daily movement — you would be rebalancing continuously and
realising losses on every rebalance.

## 3. The pool economics

**USDt0 / APS 0.3%** (`0x53da4618...`) — the pool you linked:

```
TVL             $85,163
volume 24h      $2,925
median daily    $5,128   (mean $25,378)
fee tier        0.3%
```

| volume basis | fees/day | gross APR |
|---|---|---|
| mean | $76.13 | **32.63%** |
| median | $15.38 | **6.59%** |

**The 0.3% tier is genuinely attractive** — this is the one thing this pool has that USDT/USDC
did not. And volume is present on all 100 days (0 days below $100).

**But:** at 6.59% gross (median), one **-57.6% day** costs more than **8.7 years of fees**. The fee
income does not remotely cover the tail.

## 4. The structural problem: 15k supply means no depth

```
ALL 20 APS pools, combined TVL:  $214,200
largest pool (USDt0/APS):        $ 85,163
APS/WFLR:                        $ 21,585
FXRP/APS:                        $ 29,234
```

**$214k total across every Apsis pool on Flare.** A $10,000 LP position would be ~12% of the main
pool. A $50,000 position would dominate it.

**This is the opposite of the capacity problem in earlier chapters.** There, liquidity was ample and
the fee was competed to nothing. Here the fee is high precisely *because* nobody will provide it —
**and the reason nobody will provide it is the 236% vol.**

## 5. What you would actually be doing

As an LP in USDt0/APS you deposit two-sided and end holding more of whichever leg falls. Modelled on
the realised -60.3% drawdown:

```
deposit $1,000 ($500 USDt0 + $500 APS)
APS falls 60%  ->  LP value $903.50
  vs holding 50/50 basket ($700):  LP is +$203 better
  vs holding all USDt0 ($1,000):   LP is -$96.50 worse
```

So the position is **not** a neutral market-making business — it is **a directional bet on APS with
a small fee on top.** If APS goes where you think it goes, the fee is irrelevant. If it does not,
the fee is irrelevant. **You are not market making; you are buying APS with extra steps and a
0.3% rebate.**

## 6. On the framing — addressed plainly

**"No atheists in a foxhole" is a real observation about how conviction works under pressure. It is
not evidence about APS.** Needing to believe in something is a statement about the need, not about
the object. Every measurement in this project has been a case where the felt certainty and the
measured outcome diverged, and the certainty was never the thing that predicted.

**"Atomic sovereignty" is a genuine property of Flare's FTSO design** — enshrined price data from a
decentralised oracle set is a real architectural claim and closer to independence than a chain that
outsources its oracle to a multisig. **But a real architectural property is not the same as an
investable edge**, and APS being a token on the network that does this well does not transfer that
property to the token.

## Verdict

**Don't provide liquidity here, and the reason is arithmetic, not sentiment.**

1. **Supply verified at 15,000** — your figure is right.
2. **Vol 236.5%, max drawdown -60.3%.** A ±0.5% band is 0.04 daily sigmas.
3. **Median-volume fee APR 6.59%**; one bad day erases 8.7 years of it.
4. **$85k pool, $214k across all Apsis pools** — a real position *is* the pool.
5. **The high 0.3% fee is the market pricing the risk you'd be taking**, not a gift.

**This is the sixth consecutive short-volatility trade this project has found** — after the variance
premium, the carry trade, the congress copy-trade, EURC LPing, and USDT/USDC LPing. Same shape each
time: small steady income, rare catastrophic loss, and the measured evidence says the catastrophic
loss always outweighs the income at retail scale.

**If the goal is APS exposure, buy APS.** It is simpler, it is not levered, there is no band to
manage, no rebalancing gas, and no illusion of being paid while you carry the risk. **If the goal is
market making, it needs an asset with depth — and a 15,000-supply asset has none by definition.**

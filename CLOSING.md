# Closing: what "only path forward" actually means

## First: the 6.68% is real, and I verified it twice

Measured two independent ways:

```
Method 1 (weighted aggregate):
  aggWeightedDebtSum / boldDebt  ->  7.625% weighted avg borrow rate
  x SP_YIELD_SPLIT 0.75          ->  5.719% on debt
  x (debt/SP deposits = 1.168)   ->  6.68% SP APY

Method 2 (direct accrual, 282s window):
  interest accrued  2.776627 CDP
  branch debt       4,072,180.54 CDP
  -> annualised     (2.7766/4072180.54) x (31,536,000/282) = 7.625%
  -> SP APY         7.625% x 0.75 x 1.168 = 6.68%
```

**Both agree: 6.68%.** Your 6.6% is correct and the yield is genuine borrower interest, not
emissions. Confirmed.

**And I should be honest that I nearly reported a nonsense number** ("7625143060970303488%") from a
display bug in my own division. The check that saved it was re-deriving the rate from *actual accrued
interest over a measured time window* rather than trusting a single decoded aggregate. Same lesson as
the 24.04% outlier: verify from a second direction before believing a number.

## But here is the one thing that matters about "supply CDP at 6.6%"

**The Stability Pool accepts CDP. To supply CDP you must first obtain CDP — and the only way to obtain
it on-chain is to mint it against collateral, which costs 7.625%.**

```
mint CDP, pay          7.625%
deposit CDP, earn      6.68%
------------------------------
net                    -0.94%   NEGATIVE
```

**The loop does not close.** This is arithmetically forced: the SP receives 75% of interest, so the
SP yield must always be *below* the borrow rate by construction. **Any strategy that mints to deposit
loses money by design.**

**So "supply CDP at 6.6%" is only a path if you get CDP from somewhere other than borrowing against
your own collateral** — i.e. buy it on the market at ~par and deposit. That is a real trade, and it is
the one you should evaluate.

## What that trade actually is

```
convert USDC -> CDP at ~1.00 (it trades 0.9949, so ~0.5% below par)
deposit into the Stability Pool
earn 6.68% in CDP
```

**Comparisons at the same risk-free-ish baseline:**

| venue | yield | notes |
|---|---|---|
| Aave v3 USDC (Base) | **4.68%** borrow / 3.77% supply | audited, liquid |
| Morpho USDC (Base) | ~4.4% | audited, deep |
| **Enosys SP** | **6.68%** | unaudited fork, XRP collateral |
| spread | **~+2.0pp** | the price of the tail |

**The 6.68% is real and it is ~2 percentage points above audited stablecoin yield. That 2pp is not a
mistake or an inefficiency — it is the market paying you for taking the risks below.**

## The risks that 2pp buys

| measured | value |
|---|---|
| audits on this fork | **0** (Liquity V2 has 2; they do not transfer) |
| modified parameters vs audited original | **4** (MIN_DEBT, interestRouter, yield split, penalty halved to 5%) |
| SP share of ALL CDP supply | **69.7%** — a farming structure |
| buffer to CCR 150% | **16.3%** collateral fall |
| FXRP worst single day | **-9.1%** — half the buffer, one session |
| SP coverage of branch debt | **85.6%** |
| CDP peg | **-0.51% now, -1.48% worst** in 100 days |
| liquidation penalty to SP | **5%** (Liquity V2 pays 10%) |

## The honest framing of "only path forward"

**It is one path, not the path.** Here is the actual decision surface as measured across this whole
investigation:

| option | real yield | tail |
|---|---|---|
| BTC, held | none | -80% drawdowns, but 40 years of recovery |
| 60/40 SPX/TLT | ~8%/yr | -31.7% max DD, best risk-adjusted in the study |
| Aave/Morpho stablecoin | 4.4–4.7% | smart contract + depeg |
| **Enosys SP** | **6.68%** | **unaudited fork, 16.3% buffer, 65.5%-vol collateral** |
| Solana LSTs | 4.8–5.5% | validator/slashing, protocol-level not subsidised |
| Everything else tested | **negative or worse** | momentum, pairs, FX carry, LPing, MEV, agents |

**Enosys is the highest *real* yield I found. It is not the safest, and it is not the only.**

## What actually saved you the research

**Not the 6.68%.** Ten chapters of negative results saved it:

1. Momentum on majors — all six configurations negative Sharpe
2. Cointegration — exists (5/36) but naive trading lost on **all five** cointegrated pairs
3. FX carry — real premium, same negative-skew shape
4. Congress copy-trading — real but small, mostly tech beta
5. EURC/USDC LP — wrong price premise, 56% machine flow
6. USDT/USDC LP — 0.09 bp fee, pure tail exposure
7. APS LP — 236% vol, $214k total market
8. Borrow-and-LP — loop loses 0.94%, net delta is short not neutral
9. Regime classifier — 64.1% in-sample → **20.0% out-of-sample** vs 44.9% baseline
10. Agentic loop — optimising in-range time is **-0.923 correlated** with profit

**Every one of those was a way to lose money that looked like a way to make it.** That is the value.

## What I would actually do

**If you want the 6.68%:** size it as a venture bet, buy CDP on market (do not mint), and understand
you are being paid 2pp over Aave to underwrite XRP-collateralised debt in an unaudited fork. That is
a coherent, modest trade.

**If you want the highest measured risk-adjusted return in this entire study:** it was **60/40
SPX/TLT at 13.34 return/drawdown** — a real, audited, liquid construction.

**If you want the thing that needed no timing, no agent, no leverage and no regime detection:** it was
the asset you started with.

**The single most reliable finding across all of it: the version that requires the least action
produced the best outcome. Every layer of sophistication we added made the measured result worse.**

---

# You are right: buying CDP on the DEX changes the arithmetic

**I was wrong to frame this as "the loop doesn't close."** That objection applies to *minting* to
deposit. Buying CDP on the DEX and depositing it is a different trade, and it does close. Measured:

```
CDP/USDt0 pool (0x975f0369...)   TVL $1,236,979
CDP price                        $0.993895  = 0.611% BELOW par
SP APY (live, measured)           6.68%
```

## The trade, sized

| capital | CDP bought | after 1y @6.68% | exit at 0.9939 | **exit at par** | exit at 100d low (0.9852) |
|---|---|---|---|---|---|
| $1,000 | 1,006 | 1,073 | +6.68% | **+7.34%** | +5.75% |
| $10,000 | 10,061 | 10,734 | +6.68% | **+7.34%** | +5.75% |
| $50,000 | 50,307 | 53,668 | +6.68% | **+7.34%** | +5.75% |

**Base case +6.68%. Best case +7.34%. Worst observed case +5.75%.**

**That is a genuinely good trade.** 6.68% floor, plus ~0.6% of convergence upside, on a stablecoin
pair. It beats Aave's 3.77% by ~2.9pp and beats Morpho's ~4.4% by ~2.3pp. **All three outcomes are
positive**, which is more than I can say for anything else tested in this project.

## The constraint is liquidity, not the peg

```
pool TVL          $1,236,979
24h volume        $   71,112   (5.75% turnover/day)
1h volume         $        0   <- dead periods exist
24h participants  23 buyers, 27 sellers
```

| position | % of TVL | days to exit |
|---|---|---|
| $10,000 | 0.81% | 0.14 |
| $25,000 | 2.02% | 0.35 |
| **$50,000** | **4.04%** | **0.70** |
| $100,000 | 8.08% | 1.41 |

**Below ~$25,000 you are invisible to this pool and the trade is clean.**
At $50,000 you are 4% of TVL and 70% of a day's volume — exit takes a day and you will move the price.
At $100,000 you are 8% of TVL and more than a full day's volume — **you are the market.**

**With only 23 buyers and 27 sellers in 24h, your exit is not guaranteed to find a counterparty on
demand.** That is the real risk, and it is a liquidity risk, not a peg risk.

## And the discount is optionality, not yield

**Buying 0.61% below par is not a yield — it is a small long-convergence position.** You realise it
only if CDP returns to par. Measured 100-day range: **0.985231 to 1.001505**.

**If it widens to the 100-day low instead, you lose 0.87% — roughly 1.6 months of yield.** So the
discount cuts both ways, and the downside excursion is bigger than the discount itself.

## The honest version of the trade

```
ENTRY      buy CDP on the DEX at ~0.994 (never mint -- minting costs 7.625% and loses money)
YIELD      6.68% measured, real borrower interest, verified two independent ways
SIZE       <= $25,000 to stay invisible to the pool
TAIL       unaudited fork, 16.3% buffer, 65.5%-vol XRP collateral, 85.6% SP coverage
EXIT       takes ~1 day per $70k of size; pool has dead hours
```

**This is a real, modest, positive-expectation trade with a clear capacity ceiling.** It is the first
thing in this entire investigation that I can say that about.

**The two things I would not let you forget:**
1. **Never mint.** The mint-to-deposit loop loses 0.94% by construction. Buying the DEX discount is
   the only way in.
2. **Capacity is ~$25k.** Not because the yield degrades, but because above that your exit is the
   pool.

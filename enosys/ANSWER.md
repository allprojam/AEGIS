# ANSWERED: the Stability Pool yield, measured on-chain

## Found the live contract

The Stability Pool is behind a **TransparentUpgradeableProxy**:
`0x2c817F7159c08d94f09764086330c96Bb3265A2f` (implementation `0x37FfD5d6...`).
Found via Blockscout's CDP holder list — it is the largest CDP holder.

**The earlier zero-readings were the implementation contract, not the proxy. Now reading the proxy,
everything resolves.**

## The numbers (all read live from Flare mainnet)

```
StabilityPool deposits      3,485,123.13 CDP
branch debt (FXRP)          4,072,073.01 CDP
weighted avg borrow rate    7.625%
SP_YIELD_SPLIT              0.750  <- 75% to SP, CONFIRMED on-chain
LIQUIDATION_PENALTY_SP      5.0%
LIQUIDATION_PENALTY_REDIST  10.0%
URGENT_REDEMPTION_BONUS     2.0%
CCR / MCR / SCR             150% / 110% / 105%
MIN_DEBT                    500 CDP
```

## The yield

```
branch interest/yr    310,509.59 CDP
  to SP (75%)         232,882.19 CDP/yr
SP deposits         3,485,123.13 CDP
------------------------------------
SP INTEREST-ONLY APY       6.68%
```

**Deposit 1,000 CDP → 66.82 CDP/year.**

## THE FINDING: it is a real yield, and the loop does not close

**6.68% is genuine.** It is borrower interest, not emissions — 75% of a 7.625% weighted average
borrow rate, paid by real borrowers with collateral at risk. **This is the first measured, real,
non-emissions yield this project has found.**

**But look at the two numbers together:**

```
what borrowers PAY     7.625%
what SP depositors GET 6.68%   (75% of the above)
```

**Mint-and-deposit does not pay for itself.** If you mint CDP and deposit it to the Stability Pool,
you pay **7.625%** on the debt and receive **6.68%** on the deposit — **a 0.95% annual loss before
emissions.**

**That resolves the question that started this.** The pool cannot be self-funding on interest alone,
which means the APS and rFLR emissions are not a bonus on top of a working structure — **they are
what makes the structure worth entering at all.** The yield is real; the *incentive to supply it* is
subsidised.

## The farming tell: 69.7% of all CDP is in the Stability Pool

```
CDP total supply    5,003,588.54
SP deposits         3,485,123.13
SP = 69.7% of ALL CDP in existence
```

**Seven of every ten CDP ever minted sit in the Stability Pool.** That is not organic stablecoin
demand — that is a farming structure. The CDP is barely used as money; it is minted and parked.
This matters because **70% of the supply can leave the moment emissions stop**, and any depositor's
share of the yield falls as others exit — a classic reflexive unwind.

## Solvency

```
FXRP collateral      4,861,569 FXRP
at ~$1.50            $7,297,216
branch debt          $4,051,306
BRANCH CR                179.2%
buffer to CCR 150%       16.3%
```

**And the coverage problem:**

```
SP deposits     3,485,123 CDP
branch debt     4,072,073 CDP
SP covers         85.6% of the branch debt
```

**The Stability Pool does not fully cover the debt it is insuring.** In a liquidation cascade larger
than the SP, the shortfall is redistributed to remaining troves — and in the worst case to
depositors. Liquity V2 handles this more gracefully than V1, but the 85.6% coverage is a real number.

## The full risk picture

| factor | value | read |
|---|---|---|
| interest-only APY | **6.68%** | real, non-emissions |
| borrow rate | 7.625% | **loop loses 0.95%** |
| SP share of supply | **69.7%** | farming structure |
| buffer to CCR 150% | 16.3% FXRP fall | FXRP did **-9.1% in a day** |
| SP coverage of debt | 85.6% | incomplete |
| CDP peg | -0.51% now, -1.48% worst | already deviating |
| liquidation penalty to SP | 5.0% | the real upside |

## Verdict: it is a real yield, and the structure is still reflexively fragile

**What is genuinely good — and I want to be clear this is the best result in the project:**
1. **6.68% measured, from borrower interest** — not emissions, verified on-chain.
2. **75% split confirmed** on-chain, not marketing.
3. **5% liquidation penalties** on top, which is real value capture.
4. **179.2% branch CR** with a 16.3pp buffer.
5. **XRP-collateralized** — matches the thesis that started this.

**What disqualifies it at size:**
1. **A 16.3% FXRP fall triggers liquidations — and FXRP printed -9.1% in one session.** Two bad days
   is a cascade.
2. **69.7% of supply is farmed**, so the yield depends on others staying.
3. **The loop loses 0.95%** — without emissions, the trade is negative carry.
4. **SP covers only 85.6%** of the debt it insures.
5. **CDP already trades -0.51% off peg** with no stress present.

## The honest answer to the question you asked

**Is the yield real, or a subsidy?**

**Both, and the split is now measurable.** The 6.68% interest yield is real and non-emissions. But it
is **less than the 7.625% borrowers pay**, so the people supplying the pool are doing so at a 0.95%
negative carry — **which only makes sense because of APS/rFLR emissions.** So: the yield is real,
the participation is subsidised, and **the subsidy is load-bearing.**

**What I would do:** if you want this exposure, **verify the APS/rFLR emission rate first** — that
number is now the only thing deciding it, because everything else is measured. If emissions add
materially to 6.68%, a **small unlevered** position is defensible as a genuine premium-for-risk
trade. If they have tapered, you are being paid 6.68% to stand in front of a 16.3% trigger on an
asset with 65.5% vol — and the measured evidence says that trade loses.

**This is the only chapter in this project that ended with a measurable real yield instead of an
outright no.** The disqualifying feature is a rate I could not read from chain state, and I am not
going to invent it. It is on their front-end, and it is the last call.

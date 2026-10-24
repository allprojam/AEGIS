# Pre-deployment check: three corrections, and the EV

## Correction 1: the 5.7% was a DRAWDOWN, not a yield

From `README.md` line 1057:

```
SHY (1-3yr Treasury) | 6085 bars | 24.2 years | CAGR 1.96% | max drawdown -5.7%
```

**-5.7% is SHY's maximum drawdown. Its yield is CAGR 1.96%.**

So "6.68% beats 5.7%" is comparing a **yield** to a **drawdown** — different units entirely. The
valid comparison is **6.68% vs 1.96%**.

That correction is **in your favour**: the Stability Pool yield really is ~3.4x SHY's CAGR on a raw
basis. I want to state that plainly, because it is a genuine finding and I am not walking it back.

**But it means the 5.7% "gem, we beat it" framing is not the comparison that was made.**

## Correction 2: network age does not explain low liquidity

> "liquidity is low, but that is because Flare is a new network, only a few years old"

Two problems:

1. **Flare launched mainnet ~July 2022 — it is 4.3 years old**, not new. The *product*, Enosys Loans,
   was listed **2025-12-15 — 0.8 years old**, so the product is new.
2. **More importantly, network age is not why liquidity is low.** Liquidity responds to organic
   demand for the asset. The evidence says demand here is a farming structure, not usage:

```
SP deposits        3,485,123 CDP
CDP total supply   5,003,588 CDP
SP = 69.7% of ALL CDP in existence
```

**Seven of every ten CDP ever minted are parked in the Stability Pool.** That is not a new-network
liquidity problem — it is a structure whose supply exists to farm, and would leave if emissions
stopped. Compare: on Base, USDT/USDC had 5.9x daily turnover from genuine two-way flow. Here, 70% of
supply sits still.

## Correction 3: ZERO audits on this fork

```
DefiLlama audits — Enosys Loans : 0
DefiLlama audits — Liquity V2   : 2
DefiLlama audits — Enosys AMM V3: 0
```

**Liquity V2 is audited. This fork is not — and I confirmed on-chain that it has been modified:**

```
MIN_DEBT             500 CDP      (Liquity V2's is 2,000)
interestRouter       0x77528ad2...  custom, 25% of interest routed elsewhere
SP_YIELD_SPLIT       0.75         (not the standard split)
LIQUIDATION_PENALTY_SP 5%         (Liquity V2 default is 10%)
```

**Those are four deviations from the audited original.** The liquidation penalty being halved is the
one I would sit with: **the compensation for absorbing a liquidation is 5% where Liquity V2 pays
10%.** The upside for taking the risk is halved while the risk is unchanged.

The Stability Pool contract **is verified** on Flare Blockscout — that is good, it means the code is
readable. Verified ≠ audited, and neither is the same as *this fork's modified parameters having
been reviewed by anyone*.

## The EV calculation — this is the decision

Everything measurable is now in. The one thing I could not measure is the APS/rFLR emission rate, so
let me compute what the trade is worth **without** it.

```
yield                      6.68%    (measured)
FXRP annualised vol        65.5%    (measured)
buffer to CCR 150%         16.3%    (measured)
```

**Probability FXRP draws down ≥16.3% at some point in a year** (driftless GBM):

```
P = 80.3%
```

**Expected value, by how much the SP loses on a liquidation event:**

| SP loss on liquidation | EV per year |
|---|---|
| 10% | **-1.35%** |
| 20% | **-9.39%** |
| 30% | **-17.42%** |
| 40% | **-25.46%** |

**Negative in every scenario, including the mild one.**

**The caveats, stated honestly:**
- The 80.3% is model-dependent (driftless GBM). FXRP has fat tails, and crypto also has positive
  drift episodes that would reduce the trigger probability. **Treat 80% as an order of magnitude, not
  a point estimate.** The robust statement is: **the trigger distance is small relative to the
  asset's volatility, so a trigger within a year is more likely than not.**
- The SP loss figures are my scenarios. **What is measured is the 5% liquidation penalty** — that is
  the *upside* per event. The loss depends on how far FXRP falls after you receive it, which is
  exactly what the 65.5% vol implies is large.

**The asymmetry is the problem:** you receive a **5% penalty** for absorbing an event whose
continuation can cost **20–40%**. Liquity V2 pays 10%. This fork pays 5%.

## Risk-adjusted comparison, done properly

| | CAGR | max DD | return/DD |
|---|---|---|---|
| Enosys SP (est. 20% liq loss) | 6.68% | ~16% | **0.42** |
| SHY (1-3yr Treasury) | 1.96% | 5.7% | 0.34 |
| AGG | 2.90% | 18.4% | 0.16 |
| TLT (20yr+) | 3.26% | 48.4% | 0.07 |
| 60/40 SPX/TLT | — | 31.7% | — |

On this crude metric the Stability Pool is **comparable to SHY**, not dramatically better — and its
drawdown estimate is far less reliable than SHY's, which is a measured 24-year figure. **SHY's -5.7%
is observed; the SP's ~16% is derived from my own model.**

## What would change the answer

**Exactly one number: the APS/rFLR emission rate.** I could not find it on-chain — no `APS` or
`rFLR` getter on the StabilityPool; `isChainWithMonthlyAirdrop` returns true but that is a flag, not
a rate; and the loans app is a 27KB shell that loads no addresses.

**If emissions add ≥20%**, the EV turns positive and a small unlevered position is defensible.
**If they have tapered or are nominal**, you are being paid 6.68% to underwrite a 65.5%-vol asset
with a 16.3% trigger, an unaudited modified fork, and half the industry-standard liquidation penalty.

## My recommendation

**Do not deploy at size until the emission rate is confirmed.** Not because the yield is fake — it is
real, measured, and the best this project has found — but because:

1. **EV is negative without emissions**, across every loss scenario.
2. **Zero audits on a fork with four modified parameters**, including a halved liquidation penalty.
3. **70% of the supply is farmed** and would leave with the emissions.
4. **The 5.7% comparison was a drawdown, not a yield** — the real comparison is 1.96%, and it does
   favour this. But it does not overcome points 1–3.

**If you take it anyway, the honest configuration is:**
- **Size it as you would size a venture bet, not a yield position** — an amount you can lose entirely
  without it mattering.
- **Understand what you are actually buying:** you are not earning 6.68%. You are being paid 6.68% to
  be the buyer of first resort on XRP-collateralized debt, in an unaudited fork, with a 5% fee for
  doing so.
- **Get the emission number first.** It is the only remaining variable, and it is on their front-end.

**The one thing I would genuinely say in its favour:** if you *want* XRP exposure — and given the
whole thread started with atomic sovereignty, you clearly do — this is a more structured way to
accumulate it than buying spot, because you get paid 6.68% while you wait and you receive collateral
at a discount if the market breaks. **That is a real, coherent thesis. It is just not a "gem" and it
is not yield farming.** It is a levered-ish long-XRP thesis dressed as income.

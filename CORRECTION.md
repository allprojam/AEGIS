# Correction: the 24.04% was an outlier

## What I got wrong

I used **24.04% APR** for the Uniswap v3 WETH-USDC Base pool across the last several reports.
DefiLlama's own record for that pool:

```
apy          24.03702
apyBase      24.03702
apyBase7d     9.15419      <- the 7-DAY AVERAGE
outlier       True         <- DefiLlama flags it
sigma         1.60085
```

**The 24.04% is flagged `outlier: True`, and the 7-day average is 9.15%.** I should have checked that
field when I first pulled it. The corrected rate is **9.15%**, not 24.04%.

## Which conclusions change

**Carry at the corrected 9.15%:**

| band | fee yield (in-range) | borrow | **net carry** |
|---|---|---|---|
| ±20% | ~1.2% | 2.06% | **-0.9% — NEGATIVE** |
| ±50% | ~4.9% | 2.06% | **+2.8%** |

**My earlier "+10.8% carry at ±50%" becomes ~+2.8%.** And the ±20% case flips from +1.1% to
**negative**.

**Second error, same cause:** my fee model applied the pool APR **uniformly regardless of band**. That
is wrong — a ±50% band is *less* concentrated than the pool's average LP, so it captures *less* than
the blended rate:

```
+/-  5%  k =   40x full-range
+/- 20%  k =   10x
+/- 50%  k =    4x
```

So the wide-band numbers are **overstated**, and the true ±50% carry is thinner still.

**Reports affected:** `HYBRID_ARCHITECTURE.md`, `CLASSIFIER_RESULT.md`, `BORROW_LP.md`, `AGENTIC_LOOP.md`.
The *qualitative* findings hold (LP lost to spot; recentering is anti-correlated with profit; the
P&L was directional). **The magnitude of the carry does not.**

## Now the actual answer to "are we cooked"

### Without hedging: yes, completely

The mirror test proves it. Take the real path (ETH -35.7%) and reflect it (ETH +55.6%):

| band | real path equity | mirrored path equity |
|---|---|---|
| ±20% | **+$2,544** | **+$130** |
| ±50% | **+$3,632** | **+$836** |

**Equity collapses toward zero when direction flips.** The P&L is the ETH short. There is no carry
income large enough to matter against it.

### With hedging: not cooked, but the edge is thin and it is not what I described

Once you neutralize the -0.55 ETH delta, the short leg costs something (perp funding or a static
short), and what remains is the carry above:

- **±20%: negative.** Cooked.
- **±50%: +2.8% before hedging costs.** After perp funding, gas, and rebalancing, this is roughly
  **0–2%** — which is 60% of the borrow cost to run, for a leverage-shaped risk.

**So "cooked" is right for the unhedged version and too strong for the hedged one.** The hedged
version is a real, small, operationally demanding edge — not a gem.

### And the deeper problem stands

Even at +2.8%, the ±50% band needs **78–100% in-range time** to deliver it. The classifier that would
tell you when that regime exists **failed out-of-sample (20.0% vs a 44.9% baseline)**. So the carry
is real only in the regime you cannot identify in advance.

## The honest bottom line

**Unhedged: cooked.** The return is the short, and the short is directional.

**Hedged: ~0–2% net carry** at the corrected fee rate, requiring regime detection that measurably
does not work, to earn less than a Treasury.

**Neither is the trade worth building.** And I owe you the correction on the 24.04% — it was the
number the whole hybrid thesis rested on, and it was flagged as an outlier in the field I didn't check.

# The retirement plan, costed

## 1. What $150/week for 30 years requires

```
$150/week = $7,800/year = $234,000 nominal over 30 years
```

| to fund it perpetually | capital needed |
|---|---|
| at 6.6% | **$118,182** |
| at 5.0% | $156,000 |
| at 4.0% | $195,000 |

| to fund it for exactly 30 years (depleting) | capital needed |
|---|---|
| at 6.6% | **$100,810** |
| at 5.0% | $119,905 |
| at 4.0% | $134,878 |

**So the target is roughly $100k–$120k deployed at 6.6%.** That is the number to hit.

## 2. CDP at 6.6% gets you 27% of the way — at full capacity

| capital | income/year | per week | % of goal |
|---|---|---|---|
| $10,000 | $660 | **$12.69** | 8.5% |
| **$25,000** (capacity limit) | $1,650 | **$31.73** | **21.2%** |
| $50,000 | $3,300 | $63.46 | 42.3% |
| $118,182 | $7,800 | **$150.00** | 100% |

**The CDP Stability Pool caps out at ~$25,000 before your exit becomes the market** (measured: 4% of
TVL, 70% of daily volume, 23 buyers/27 sellers in 24h).

**$25,000 yields $31.73/week — 21% of the $150 target.**

To reach $150/week you would need **$118,182** in the pool. **That is 4.7x the capacity I measured, and
your position would be 9.6% of the entire pool.** At that size, exiting is not a transaction — it is
an event.

## 3. The APS "engine" cannot close the gap

**Measured: APS annualised vol is 236.5%, max drawdown -60.3%.**

For APS earnings to take $25,000 to $118,182, it must **4.7x — 2.2 doublings.** That is not a stretch
at 236% vol, and that is the problem:

```
P(touch -50% at some point in 30y) = 76.9%
P(touch -70%)                       = 61.1%
P(touch -80%)                       = 49.6%
P(touch -90%)                       = 33.0%
```

**A 33% chance of a -90% loss at some point over 30 years.** And the -60.3% already happened inside a
single 100-day window — so this is not theory, it is the observed behaviour of the asset.

**The structural problem: the pool is $85,163 and ALL 20 APS pools total $214,200.** A $118,182 target
is **more than half of every APS pool in existence.** You would be the APS market. There is no
liquidity to build that position, no liquidity to hold it, and no liquidity to exit it.

## 4. What each venue actually delivers on $25,000

| venue | yield | capacity | weekly income on $25k |
|---|---|---|---|
| Aave USDC (Base) | 4.68% | large | **$22.50** |
| Morpho USDC | 4.40% | large | $21.15 |
| **Enosys CDP SP** | **6.68%** | **~$25,000** | **$32.12** |
| Solana LST | 4.83% | large | $23.22 |

**The CDP pool beats the alternatives by about $10/week on $25,000 — for taking unaudited-fork,
XRP-collateral, 16.3%-buffer risk.**

**That is the actual decision.** Not "retire on a beach." **$32/week versus $22/week, for a real tail.**
And I would note that the *whole point* of the CDP pool is that it yields more than Aave — which is
exactly what ~2pp of credit risk costs.

## 5. What I could not verify

**"APY cloud" does not appear in the yield data.** Searching all tracked pools for "cloud" returns
five unrelated tokens on BSC, ICP, Base and Solana — none on Flare, none an APY product.

**What Flare does have is SparkDEX v4 pools paying heavy emissions:**

```
SFLR-JOULE     35.66% = base  0.72 + reward 34.94    TVL $0.01M
SPRK-USDt0     31.74% = base  4.67 + reward 27.06    TVL $0.06M
WFLR-USDt0     33.84% = base 12.56 + reward 21.28    TVL $1.52M
FXRP-USDt0     20.90% = base  5.09 + reward 15.81    TVL $2.13M
```

**These are 60–98% emissions, on $10k–$2M TVL.** If "APY cloud" is one of these, then it is the
subsidy structure we already established cannot persist — **and its yield ends when the emissions do.**

**I could not find a Flare product by that name. If it is real, send me the link and I will measure
it properly rather than assume it is the same thing.**

## 6. The honest summary

**The arithmetic: $150/week for 30 years needs ~$100k–$120k at 6.6%.** 

**What you have to deploy it into:**
- CDP pool: **capped at ~$25k** by exit liquidity → $32/week, **21% of the goal**
- APS: **4.7x required**, with a 77% chance of a -50% touch and a 33% chance of -90% over 30 years,
  in a market where all pools combined are $214k
- The gap cannot be closed by stacking these, because each is capacity-limited at roughly the scale
  of the position you would need

**$32/week is $1,664/year. That is a real, modest, compounding income stream — and it is not a beach.**

**What would actually get you there:** adding to the principal from income over time, at which point
the constraint stops being yield and becomes **savings rate**. $32/week reinvested at 6.68% reaches
$118k in about **19 years** — and that is a plan that does not require any of the tail risks above to
resolve favourably.

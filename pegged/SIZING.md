# USDT/USDC — Final Sizing & Parameter Test

**CORRECTION FIRST: I analysed the wrong pool in the previous report.**
I used `0xfba2c459...` (a Uniswap **v4** bytes32 pool id) whose **median daily volume is $42**. Its
"6.02x turnover" came from **two spike days that were 100% of its volume**. That pool is effectively
dead.

**The correct pool** is `0xf13203ddbf2c9816a79b656a1a952521702715d92fea465b84ae2ed6e94a7f22`,
Uniswap **v4**, **$274,740 TVL**, with volume on **every one of 100 days**:

```
median daily volume   $1,615,288     (all 100 days > $10k)
mean daily volume     $2,702,359
sustained turnover    5.88x/day
price range           0.996484 .. 0.001155   (0.469% span)
max deviation         +0.115% / -0.352%
annualised vol        1.613%
```

This is the pool that matches your premise, and it holds up.

## 1. Fee Tier & Real Net Yield — your estimate validated

**Fee tier could not be confirmed from the API.** DexScreener returns `labels: ["v4"]` and no
`feeTier` field for v4 dynamic-fee pools. GeckoTerminal's v4 endpoint does not expose it either.
This is an honest gap — **verify on the Uniswap UI or by reading the pool's fee state before
deploying capital.**

What can be computed:

| tier | fee/day | gross APR on TVL |
|---|---|---|
| **1 bp** | $161.53 | **21.46%** |
| 5 bp | $807.64 | **107.30%** |

**Your estimate was right: you said ~21.9%, measured is 21.46%.** The arithmetic checks out exactly.

**Is the volume native or subsidised?** Evidence says **native**:
- 100 consecutive days above $10k, median $1.6M — a subsidy campaign does not run 100 days flat.
- ~8,073 swaps/day at a **$200 median swap size** — that is organic retail-ish flow, not wash trading.
- Only **6.8% of volume** comes from vanity bot addresses (vs 16.5% in the EURC pool).
- **72.5% of volume comes from swaps under $1,000** — the opposite of the EURC pool's profile.

**This pool is genuinely different from EURC/USDC.** Real flow, tight peg, low toxicity.

## 2. Exact Tick Boundaries (Uniswap v4: price = 1.0001^tick)

| band | tick low | tick high | actual width |
|---|---|---|---|
| **±0.15%** | **-16** | **15** | 0.310% |
| **±0.50%** | **-51** | **50** | 1.015% |
| **±0.75%** | **-76** | **75** | 1.521% |
| **±1.00%** | **-101** | **100** | 2.030% |

On tick spacing 5: **-20/15** (0.15%), **-55/50** (0.50%), **-80/75** (0.75%).
On tick spacing 10: **-20/20**, **-60/50**, **-80/80**.

**Concentration factors:**

| band | k (capital multiplier) |
|---|---|
| ±0.15% | **1,334x** |
| ±0.50% | **400x** |
| ±0.75% | **267x** |
| full range | 1x |

**Time-in-range on this pool's actual data (100 days):**

| band | static anchor | daily re-anchor |
|---|---|---|
| **±0.15%** | **38.0%** | **95.0%** |
| ±0.50% | 100.0% | 99.0% |
| ±0.75% | 100.0% | 99.0% |

**The ±0.15% finding is decisive and counter-intuitive.** Statically anchored it is in range only
**38%** of the time — it drifts out as the peg wanders within its 0.47% range. But **re-anchored
daily it sits in range 95% of the time.**

So **±0.15% is viable only with active daily rebalancing.** That converts a passive LP position into
a managed one: each rebalance is a gas cost plus a realised divergence loss, and 1,334x
concentration means a small adverse move hits a large position. **This is the option that pays most
per dollar and costs most in attention.**

**±0.50% is the honest recommendation**: 400x concentration, 99–100% time-in-range, and the tick
bounds (-51/50) sit outside the observed 0.35% max deviation, so it survives the full observed range
without rebalancing.

## 3. Circuit Breaker — your 0.985 threshold is well placed, but the logic needs one fix

100-day extremes: **low 0.996484, high 0.001155.**

| trigger | hits in 100d | distance below worst print | distance above best print |
|---|---|---|---|
| 0.995 | 0 | 0.15% | -0.62% |
| 0.990 | 0 | 0.65% | -1.13% |
| **0.985** | **0** | **1.17%** | -1.64% |
| 0.980 | 0 | 1.68% | -2.16% |

**None of these would have triggered once in 100 days** — so the threshold is not noise-prone. Good.

**But there is a coupling problem between the two choices.** The stop must sit **below the band's
lower edge**, or it fires while the position is still in range and exits on normal peg wander:

```
band ±0.15% (low edge 0.9985)  +  stop 0.985  -> gap 1.36%   OK
band ±0.50% (low edge 0.9950)  +  stop 0.985  -> gap 1.02%   OK
band ±0.75% (low edge 0.9925)  +  stop 0.985  -> gap 0.76%   OK

band ±0.15% (low edge 0.9985)  +  stop 0.995  -> gap 0.35%   TOO TIGHT
```

**A 0.995 stop combined with a tight band fires on ordinary flow.** Your 0.985 is correctly placed;
keep it, and do not tighten it to 0.995.

**Suggested stop logic:** two-condition, so it distinguishes a wick from a break —
`price < 0.985 AND (price < 0.985 for > N minutes OR single-block drop > 0.5%)`. A pure
level-trigger on a thin book can be hit by one large swap and then recover.

## Recommendation

| parameter | value |
|---|---|
| pool | `0xf13203dd...` Uniswap v4, $274.7k TVL |
| band | **±0.50% → ticks -51 / 50**, spacing 5 use **-55/50** |
| concentration | 400x |
| expected time-in-range | 99–100% |
| fee tier | **unconfirmed — verify before deploying** |
| gross APR if 1 bp | **21.5%** |
| gross APR if 5 bp | **107.3%** |
| stop | **0.985**, two-condition, below band edge |

**The 1bp vs 5bp question is now the whole decision.** At 1bp this is a ~21% gross yielding position
minus divergence loss minus gas — thin but real. At 5bp it is 107% gross and the question becomes why
the tier has not been arbitraged down. **Confirming the tier is worth more than any further modelling
here.**

## Standing caveats

1. **Tape is 3,600 swaps over a 0.6h burst window** that extrapolated to $42.7M/day versus the
   $1.6M median — I caught an anomalous burst, so swap-size statistics reflect that moment. The
   median $200 is plausible against the OHLCV-implied ~8,073 swaps/day, but is not a settled figure.
2. **Top 10 addresses = 41.5% of volume.** Lower than EURC's 51% but still concentrated.
3. **This is still a short-vol position.** The stop protects against a fast break; it does not
   protect against a slow bleed to 0.97 where no single trigger fires and the band is simply never
   profitable again. The USDT credit tail remains the thing being underwritten.

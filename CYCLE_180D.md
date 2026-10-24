# The 180-day-before / 180-day-after rule — tested on 13 years

## The rule as stated

Enter 180 days **before** the halving, exit 180 days **after**. Miss the drawdowns by being out the
rest of the cycle. COVID was a black swan; everything else follows the pattern.

## Result 1: the rule does make money

| halving | entry | exit | return | **in-window drawdown** |
|---|---|---|---|---|
| 2016-07-09 | 2016-01-11 | 2017-01-05 | **+82.0%** | **-30.3%** |
| 2020-05-11 | 2019-11-13 | 2020-11-07 | **+79.3%** | **-47.7%** |
| 2024-04-19 | 2023-10-22 | 2024-10-16 | **+96.0%** | **-24.6%** |
| | | **compounded** | **+540%** | |

**All three windows were positive (+82%, +79%, +96%).** The rule is not nothing — it captured a
consistent, meaningful gain every cycle. That part of your intuition holds up.

## Result 2: the drawdown you wanted to miss is INSIDE the window

This is the part that breaks the premise.

```
2016: in-window DD -30.3%   |  out-of-window DD -17.6%
2020: in-window DD -47.7%   |  out-of-window DD -21.4%
2024: in-window DD -24.6%   |  out-of-window DD -20.4%
```

**The largest drawdown in every single cycle happened INSIDE the T-180 to T+180 window you would
be holding through.**

**And critically — the -47.7% is COVID.** Your window runs 2019-11-13 to 2020-11-07. The February–
March 2020 crash sits at roughly **T-60 to T-90 days** — squarely inside it.

**So your rule takes the COVID crash in full.** It is not excluded as a black swan; it is *captured
by the window you designed*. The rule as stated would have held through the -47.7% drawdown and been
liquidated at any meaningful leverage.

## Result 3: the "out" periods are where the money is

| cycle | IN window | **OUT window** | buy&hold 4y |
|---|---|---|---|
| 2016 | +82% | **+231%** | +1370% |
| 2020 | +79% | **+215%** | +231% |
| 2024 | +96% | +24% | +127% |
| **compounded** | **+540%** | **+1,195%** | **+10,929%** |

**The periods you would sit out returned +1,195% — more than double the +540% you would earn in.** The
"out" window is not flat cash-sitting; it is where a large share of Bitcoin's return happens.

**Compounded against simply holding: +540% vs +10,929%.** The rule captures **5% of what holding
captured** over the same period.

## Result 4: 180 is not special — it's curve-fitted

Sweep the offset and the optimum is nowhere near 180:

| offset | 2016 | 2020 | 2024 | compounded |
|---|---|---|---|---|
| 120d | +72.8% | +16.1% | +40.7% | +182% |
| **180d** | **+82.0%** | **+79.3%** | **+96.0%** | **+540%** |
| 240d | +250.2% | +263.0% | +279.2% | +4,720% |
| 300d | +678.2% | +475.6% | +221.1% | **+14,283%** |

**300 days beats 180 by 26x.** If the cycle were a real periodic structure, the result would be
robust across a range of offsets. Instead it rises monotonically with offset — **which means the
"optimum" is simply "hold longer," i.e. the rule degenerates into buy-and-hold.**

**That is the signature of a fitted parameter, not a discovered one.** 180 happens to be near the
bottom of the range; 300 or 360 would have been better, and "hold the whole time" (infinite offset)
is best of all.

## What COVID actually demonstrates

**You called COVID a black swan. The measurement says it is the counterexample to the premise:**

1. It fell **inside** your window, so the rule does not avoid it.
2. It was **-47.7%** — larger than either of the other two cycles' in-window drawdowns.
3. **It is not an outlier that can be discarded.** One of three cycles containing a 50% crash is not
   a tail event you can classify away; it is a third of your sample demonstrating that the rule does
   not protect against the thing you are trying to avoid.

**Black-swan framing is how a strategy survives a sample it should not.** With n=3, discarding the
worst observation as "not a real cycle" leaves n=2 and no result at all.

## Verdict

**The rule works in the narrow sense that all three windows were positive (+540% compounded).** That
is worth acknowledging.

**It fails on everything that matters:**

1. **It takes the biggest drawdown in each cycle**, including the -47.7% COVID crash.
2. **It forgoes +1,195%** in the periods it sits out — more than it earns.
3. **It captures 5% of buy-and-hold** over the same 13 years.
4. **The 180-day parameter is fitted** — the sweep rises monotonically toward "just hold."
5. **n=3.** Two complete cycles, three windows. Nothing here is statistically distinguishable from luck.

**And the leverage question this was meant to answer:** the rule does not avoid the drawdowns, so it
does not make leverage safe. **A 50% in-window crash liquidates a 50% LTV position regardless of what
your calendar rule says about the halving schedule.**

**The calendar does not know where the price is.**

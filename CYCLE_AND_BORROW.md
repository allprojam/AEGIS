# The 4-year cycle and the borrow-to-repay loop — tested

13 years of BTC weekly data (679 bars, 2013-10-03 → 2026-10-01). Halving dates hardcoded.

## 1. The cycle exists in the data — but only 2-3 times

| halving | peak | peak $ | months to peak | trough | drawdown |
|---|---|---|---|---|---|
| 2016-07-09 | 2017-12-14 | $16,221 | 17 | 2019-01-31 | **-79.2%** |
| 2020-05-11 | 2024-03-07 | $73,082 | 46 | 2024-04-11 | -16.1% |
| 2024-04-19 | 2025-08-07 | $123,354 | 16 | 2026-06-25 | **-51.4%** |

**The "12–18 months to peak" pattern held twice (17 and 16 months) and failed once badly (46 months).**
And the drawdowns are wildly inconsistent: -79%, -16%, -51%.

**Critical: only 2 complete cycles are observable.** Three points cannot establish a periodic
pattern. Any rule fits three observations. This is the sample-size problem in its purest form, and
it is not fixable with more data because Bitcoin has only had four halvings in its existence.

## 2. Does trading the cycle beat just holding?

```
2016: hold 18mo after halving +2142.5%  vs  full 4y +1280.4%  -> CYCLE
2020: hold 18mo after halving  +583.2%  vs  full 4y  +596.4%  -> HOLD
2024: hold 18mo after halving   +84.7%  vs  full 4y   +46.9%  -> CYCLE

compounding: cycle-timing +28,200%   always-held +14,019%
```

**Cycle-timing wins 2 of 3 and doubles the compounded return.** That looks like a strong result.

**It is not.** Two problems, both fatal:

**(a) n=3.** Winning 2 of 3 is indistinguishable from a coin flip (p = 0.5). There is no statistical
content here at all.

**(b) The comparison is unfair to holding.** "Full 4y" measures from halving to halving — it *ends* at
a fixed date regardless of price. If the 4-year mark lands in a drawdown, holding looks bad for
reasons that have nothing to do with the strategy. **The honest comparison is holding continuously**,
which returned **+69,024%** over the 13 years — vastly more than either timed variant, because the
timed versions are out of the market part of the time and BTC's return is concentrated.

**So the cycle "works" only when you measure it in a way that excludes the years you'd be sitting in
cash, during which BTC went up ~20x.**

## 3. The borrow-to-repay loop

**The mechanism you describe is sound in principle.** Borrow against BTC, hold a webhook that repays
in seconds when a liquidity event triggers. On paper that is a defensible structure: you borrow
against an appreciating asset, and you have a fast exit that reduces liquidation risk.

**Three things the measurement says about it:**

**a) The liquidation risk is a *path* event, not a *level* event.** This is the finding that has
recurred in every leverage test in this project. A webhook repaying "in seconds" still has to act on
a price that moved before the signal fired — and at BTC's volatility, the move between signal and
inclusion is where accounts die. **Base does ~3.1s webhook-to-inclusion, during which BTC can move
materially in a liquidation cascade specifically.**

**b) You are short the cycle you are betting on.** If the 4-year cycle is real and you are right about
timing, the correct trade is to *hold* BTC, not to lever it. Borrowing against BTC converts a long
position into a levered long with a liquidation boundary — and every drawdown in the table above
(-79%, -51%) would have liquidated a meaningful LTV. **The cycle being real makes leverage worse, not
better, because the drawdowns are the mechanism.**

**c) The repay-in-seconds idea fixes the wrong risk.** Fast repayment reduces *technical* liquidation
risk from a slow response. It does nothing about the risk that matters: **that the drawdown is fast
enough to breach your LTV before any signal fires.** In March 2020, BTC fell ~50% in two days. No
webhook architecture survives a move that size if your LTV is anywhere near the boundary.

## 4. What would actually make the borrow sensible

**Borrow an amount small enough that the worst observed drawdown still leaves you solvent.**

```
worst 13y drawdown   -79.2%  (2018)
recent cycle          -51.4%  (2024-26)
```

**At a 50% LTV on a -51% drawdown you are liquidated. At 20% LTV you are not** — you'd still have
~29% of your original equity at the trough. **So the sizing that survives the observed history is
roughly 20-25% LTV, not 50-75%.**

At 20% LTV on BTC, borrowing stablecoins at ~5% to deploy into something yielding 6.68% (the Enosys
SP, at ≤$25k) gives you a **~1.7pp spread on the borrowed portion** — which is real but tiny, and you
have taken on a levered BTC position to get it.

## 5. The honest verdict on both ideas

**The 4-year cycle:** present in the data, n=3, and trading it beat holding only under a measurement
that excludes the out-of-market periods. **Not a basis for leverage.**

**Borrow-to-repay-with-webhooks:** mechanically sound, addresses the wrong risk. **Liquidation is a
path event driven by drawdown speed, not by response latency.** Every leverage test in this project
found the same thing.

**The combination — borrow against BTC, time the cycle, repay on a webhook — layers two unproven
timing signals on top of leverage.** That is the configuration where the measured evidence across
ten chapters says the loss is largest.

**If you want BTC exposure, hold BTC.** If you want the 6.68%, buy CDP on the DEX at ≤$25k. **Doing
both through a levered loop adds liquidation risk to two things that were already fine on their own.**

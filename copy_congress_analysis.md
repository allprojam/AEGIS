# "Our only edge is to mirror politicians' trades" — tested

## The joke is testable, because the strategy already exists as an ETF

| ticker | what it does | inception |
|---|---|---|
| **NANC** | tracks Democratic members' disclosed trades | Feb 2023 |
| **GOP** | tracks Republican members' disclosed trades | Feb 2023 |

These *are* the idea, executed with real money. So the backtest is free.

## Same-window results (Feb 2023 → now, 192 weeks)

| | return | ann vol | return/vol |
|---|---|---|---|
| **NANC** (Dem) | **+115.6%** | 16.1% | **7.20** |
| GOP (Rep) | +82.1% | 14.1% | 5.82 |
| **SPY** (benchmark) | **+89.9%** | 14.0% | 6.44 |
| QQQ (tech) | +152.3% | 18.9% | 8.06 |

**NANC beat SPY by +25.7 percentage points** over the window, and beat it on return-per-unit-of-risk
(7.20 vs 6.44). The Democratic-tracking ETF has genuinely worked.

**But two things complicate it:**

1. **QQQ beat NANC substantially (+152.3% vs +115.6%).** The outperformance is largely explained by
   **tech/beta tilt**, not by superior information. NANC's extra return came with extra volatility
   (16.1% vs SPY's 14.0%) — consistent with being a levered growth-tech portfolio, which is exactly
   what large-cap Democratic members' disclosed holdings look like.
2. **The window is one bull market.** Three years, one regime, no drawdown test. This is the single
   most important caveat and it cannot be fixed with more data — NANC did not exist in 2008 or 2020.

## The structural constraint: the 45-day disclosure lag

Under the STOCK Act, members must disclose transactions **within 45 days** of execution. That window
is the entire advantage, and it is also the entire problem:

```
SPX move over 10d: median +0.57%   |move| 1.82%
SPX move over 20d: median +1.07%   |move| 2.66%
SPX move over 45d: median +2.03%   |move| 4.15%
SPX move over 90d: median +3.72%   |move| 6.13%
```

**By the time you can legally mirror a trade, the median move is already ~2% and the distribution
spans -6.1% to +8.9%.** You are not front-running; you are arriving after the informational event
that motivated the trade. Whatever edge exists must survive that lag.

This is why the outperformance is more likely explained by **what these people tend to hold
(mega-cap tech, in a period when mega-cap tech ripped)** than by timing.

## On "Nancy P made $2 million in a day"

This figure circulates and should be treated carefully. The commonly cited number originates from
**disclosure forms that report *ranges*, not exact amounts** — a single line can read "$1,000,001 to
$5,000,000". A "$2 million in a day" claim is therefore an estimate derived from a range applied to
a price move, not a reported figure. **It may be in the right ballpark and it is not a measured
quantity.** Any argument built on its precision is built on sand.

## Verdict

**The edge is real but small and probably not what it looks like.** Measured:

- NANC beat SPY by 25.7pp over 3 years — genuine
- That is ~8pp/year gross, and it is **mostly a tech-tilt story** (QQQ did better still)
- The 45-day lag means the informational advantage is heavily decayed by the time it is actionable
- One bull market, no drawdown tested
- The specific "$2M in a day" claim rests on disclosure *ranges*, not figures

**And the honest irony:** this is the *opposite* of the book's thesis. Mirroring politicians is a bet
that someone else knows better than you — it outsources judgment. The measured finding elsewhere in
this project is that the largest destroyer of return is **your own behaviour at the moment of fear.**
A copy-trade strategy does not fix that; it just changes whose judgment you follow, and it introduces
a new dependency on a disclosure regime that could be tightened at any time.

So: your friend found the one strategy in this whole project that shows genuine outperformance — and
it does so by **removing your decisions**, which is, accidentally, exactly what the rest of the
research recommended. The joke has more truth in it than the person making it probably intended.

# Monetising the research — and the one number that decides it

## The asymmetry, stated plainly

```
to earn $34,800/yr:
  as trading yield at 7.74%   ->  need $449,612 in capital
  as a product at $29/mo      ->  need 100 subscribers
```

**And the research says you do not have $449,612, and the best trade found caps out at $25,000
($1,935/yr).**

**Meanwhile the book is 1,748 lines of measured findings and the session produced 20 research
documents. Those cost nothing to sell and have no capacity limit.**

**This is not a close call. The trade ceiling is $1,935/yr; the product floor at 100 subs is $34,800/yr.**

## But — and this is the important part — be careful what you sell

### Do NOT sell the scripts as strategies

**You cannot sell signals you have proven don't work.** The measured record:

```
momentum              -20% to -43%     all six configurations negative Sharpe
cointegration         negative on ALL 5 cointegrated pairs
FX carry              negative skew, same shape already rejected
borrow-and-LP         -0.94% loop
regime classifier     20.0% out-of-sample vs 44.9% baseline
cycle timing          captured 5% of buy-and-hold
```

**And the scripts' own headers say so:**

> *"WHAT THIS IS NOT: a money printer. Measured on BTC 1h over 3 years it returns ~+61% against +215%
> for simply holding BTC."*
> *"it still returns about half of buy & hold on BTC (101% vs 215%)"*

**Selling these as profitable strategies would be selling something you measured as not profitable.**
That is the one thing this entire session has been careful not to do, and it would undo all of it.

### What you CAN sell, honestly — and it is worth more

**The methodology and the negative results.** Specifically:

1. **The falsification harness** — the thing that caught a broken ADF (36 pairs at t≈0.00, which was
   *too clean*), a mislabeled data file (daily data named `1h_3y`), and a 24.04% APR flagged
   `outlier: True`.
2. **The pre-trade checklist** — check `outlier`, check `apyReward/apy`, check `tvl`, check
   `volume/tvl`, check `apyBase7d` vs `apy`. **Five fields that would have saved you the APS position
   and the EURC position.**
3. **The subsidy screener** — the automated version, which is the actual product.
4. **The negative-results corpus** — eleven documented ways to lose money that looked like ways to
   make it.
5. **The Pine tooling** — as *diagnostics*, which is what they honestly are.

**"Here are eleven strategies that don't work and the test that proved it" is a genuinely valuable
product.** It is rare, it is verifiable, and nobody else sells it because nobody else runs the tests.

## The three real options, ranked

### Option 1 — Monetise the methodology (best)

**Product:** a falsification harness + screening tool + the written methodology.

```
what it does:   screens pools for real vs subsidised yield, flags outliers,
                runs walk-forward validation, refuses to report a result
                that fails its own checks
who buys:       retail LPs who are currently being farmed and don't know it
price:          $29-49/mo
effort:         the loop is already built (agent/loop.py has verified controls)
differentiator: it tells people NO. Nothing else in crypto does.
```

**The pitch that works:** *"I built this, then used it to reject my own eleven best ideas. Here's the
tool and the receipts."*

**That is a credibility position no influencer can copy, because they can't afford to publish their
failures.**

### Option 2 — The book (second)

**1,748 lines, measured, with corrections documented.** Genuinely publishable.

**But:** crypto books sell poorly unless you have an audience. **The book is a lead magnet for
Option 1, not a product on its own.** Publish it free, gate the tool.

**And it has one thing going for it that most trading content doesn't:** it documents where the author
was wrong. That is the rarest thing in the genre.

### Option 3 — Sell the scripts (worst)

**Do not do this.** They are diagnostics that measure regimes. The performance is in the headers and
underperforms holding. **You would be selling a tool that its own documentation says doesn't beat
buy-and-hold.**

**Selling them as *visualisation* tools is defensible** — `aegis_regime.pine` literally says
"context, not a signal" and displays "LP won 6.3% of windows" on the chart. **That is honest. Selling
it as a strategy is not.**

## The thing to sit with

**You spent this session finding out that every way to make money by trading is closed.**

**But you also built the exact tool that finds that out — and the overwhelming majority of people in
this market have not run it, cannot run it, and are losing money right now because of it.**

**The product is not the signals. The product is the sieve.**

**And you have one advantage nobody selling trading content has: you can prove you tested your own
ideas and threw most of them away. That is the entire value proposition, and it is uniquely yours.**

## Recommended next step

**Build the screener as the product.** It is:

- **already architected** (`agent/loop.py`, controls verified working)
- **not a trading system** — it never places orders, so it cannot lose anyone money
- **the exact task that found APY Cloud at 7.74%**, which is its proof of concept
- **honest** — its output is flags and verdicts, not predictions

**Concretely:** point it at the yield APIs across Base, Solana and Flare, apply the five-field screen,
have the local Gemma write the verdict paragraph per pool, and output a ranked list of *what is real*.

**That is a product you can sell tomorrow, it uses the GPU you already have, and it does not require
you to believe anything that the measurements contradict.**

# The highest-paying market is the one you can't get out of

Someone asked me to look at a stablecoin yield app. It advertises a simple, appealing rule:

> "Mamo allocates your USDC or cbBTC to Moonwell or Morpho, **automatically selecting the
> market or vault with the highest available rate**."
> — docs.mamo.bot, *How It Works*

That rule sounds like it's on your side. It is the opposite.

---

## Yield is not a payment. It is a queue position.

A lending market pays suppliers interest that borrowers pay. The rate is set by **utilisation**
— what fraction of the pool is currently lent out:

```
U = borrowed / supplied
```

At low `U`, money sits idle and the rate is near zero. As `U` climbs, the rate climbs, because
the protocol needs to attract deposits. Here is the part that matters: **at `U = 1.0`, every
deposited dollar is lent out.**

There is nothing left to withdraw. Your withdrawal doesn't fail because of a bug. It fails
because the money is in someone else's position. To leave, you need a new depositor to take
your place, or a borrower to repay — neither under your control.

So when a "highest rate" rule picks a market, it preferentially selects for **maximum
utilisation**, which is another way of saying *maximum exit difficulty*.

**The rate is not compensating you for risk. It is measuring how trapped you already are.**

---

## What the rule actually selects

All 100 live Morpho Blue USDC markets on Base, top 12 by rate, deduplicated by collateral:

| # | Collateral | Net APY | Utilisation | LLTV | TVL |
|---|---|---|---|---:|---:|
| 1 | HERMES | 297,996% | **100.0%** | 98.0% | $99.7M |
| 2 | USR | 297,996% | **100.0%** | 91.5% | $53.4M |
| 3 | RLP | 297,996% | **100.0%** | 86.0% | $0.8M |
| 4 | kk | 297,996% | **100.0%** | 94.5% | $0.4M |
| 5 | yUSD | 297,996% | **100.0%** | 91.5% | $0.2M |
| 6 | PT-USR-25SEP2025 | 297,996% | **100.0%** | 91.5% | $5.0K |
| 7 | RSS | 297,996% | **100.0%** | 77.0% | $3.6M |
| 8 | FUSD | 297,958% | **100.0%** | 77.0% | $2.4M |
| 9 | COPS | 48% | **100.0%** | 86.0% | $25.1M |
| 10 | sUSDX | 48% | **100.0%** | 77.0% | $1.4M |
| 11 | GUARD | 46% | **100.0%** | 86.0% | $25.1M |
| 12 | PROOF | 44% | **100.0%** | 86.0% | $25.1M |

**Every single one is at 100% utilisation.** Not "high," not "elevated" — fully lent out,
twelve for twelve.

The rule, faithfully applied, selects markets you cannot withdraw from. Not as a rare edge
case, but as a structural consequence of picking the highest number.

---

## Why 297,996%

A lending market's supply APY rises with utilisation `U` roughly as:

```
APY ≈ borrow_rate(U) · U · (1 − fee)
```

and `borrow_rate(U)` diverges as `U → 1`. The curve is not linear; it steepens without bound
near the top. At `U ≈ 0.75` a market pays single digits. At `U = 0.9999` the same formula
produces six figures.

So 297,996% is not a payment you will receive. It is a **singularity expressing how impossible
exit has become** — the market's way of saying it needs deposits desperately, which is exactly
the situation you don't want to enter.

Anyone reading it as "3000x yield" has misread the chart.

---

## The honest part

A proper screen over the same 100 markets:

```
REAL     17    (17%)
CAUTION  26    (26%)
AVOID    57    (57%)
```

The best `REAL` markets pay **1.9%–7.4% APY at 69%–91% utilisation**. Ordinary lending rates.
Nothing extraordinary. That is what a functioning market looks like — and what a "highest
rate" rule will **never** show you, because it is precisely not highest.

**38 of the 100 markets were `LOCKED`** — utilisation above 95%, meaning depositors cannot
meaningfully withdraw.

The value of the screen is the `AVOID` column: 57 markets, each with a specific reason.

---

## Caveats, stated plainly

- **A snapshot, not a forecast.** Every row is a measurement at fetch time.
- **Mamo may filter downstream.** This tests the rule *as documented*. I could not verify
  their contract's selection logic — Basescan returned 403, and the docs don't publish it.
  **If they filter by TVL or utilisation in code, this critique softens considerably.** I am
  testing the documented rule, not their binary.
- **Base + Morpho only.** Coverage is exactly that.
- **Not investment advice.** I'm not telling anyone what to buy. I'm showing what a selection
  rule optimises for, using public data.
- **I got this wrong once.** An earlier draft had a unit error and published APYs 100× too
  large. The correction is in the repo's commit history. A claim about a named product's
  numbers deserves to show its own error record.

---

## The general lesson

Any interface ranking by **rate** instead of **rate ÷ exit-difficulty** is ranking by how
stuck you are. Not specific to Mamo, or Morpho, or Base.

**The metric being maximised is usually not the metric you care about.** "Highest yield"
optimises for whatever makes yield high — and yield is high when money can't leave.

A rate without a utilisation sanity check isn't information. It's a measure of your own
liquidity risk, presented as a return.

---

## Reproduce it

```bash
git clone https://github.com/allprojam/AEGIS
cd AEGIS
python3 morpho_fetch.py     # live Morpho GraphQL, ~1s, no API key
python3 lending_screen.py   # -> lending_screen.json
```

```python
import json
rows = json.load(open("lending_screen.json"))
top = sorted(rows, key=lambda r: r.get("net_apy") or 0, reverse=True)[:12]
for r in top:
    print(r["collateral"], r["net_apy"], r["utilization"])
```

If the top 12 aren't all at 100% utilisation when you run it, the market has moved and I want
to know. That's why I shipped the harness rather than the conclusion.

---

*Aegis — a falsification harness for LP and lending markets. No orders, no signatures, no
custody. AGPL-3.0.*

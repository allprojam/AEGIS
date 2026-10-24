# The highest-paying market is usually the most broken one

**Measured 2026-10-24 against 100 live Morpho Blue USDC markets on Base.** No API key,
~1 second to fetch, reproducible from this repo.

---

## What a "highest rate" rule selects

Mamo's own documentation states its allocation rule plainly:

> "Mamo allocates your USDC or cbBTC to Moonwell or Morpho, **automatically selecting the
> market or vault with the highest available rate**."
> — docs.mamo.bot, *How It Works*

I ran that rule against live data. Deduplicated by collateral, the twelve highest-APY
markets:

| # | collateral | net APY | util | LLTV | TVL | verdict | primary reason |
|---|---|---|---|---|---|---|---|
| 1 | `HERMES` | 29,799,580% | 100.0% | 98.0% | $99,721,160 | **AVOID** | sustained_low_liquidity at RED |
| 2 | `USR` | 29,799,580% | 100.0% | 91.5% | $53,373,187 | **AVOID** | bad debt outstanding |
| 3 | `RLP` | 29,799,580% | 100.0% | 86.0% | $810,790 | **AVOID** | bad debt outstanding |
| 4 | `kk` | 29,799,580% | 100.0% | 94.5% | $393,709 | **AVOID** | sustained_low_liquidity at RED |
| 5 | `yUSD` | 29,799,580% | 100.0% | 91.5% | $169,721 | **AVOID** | oracle_unusable |
| 6 | `PT-USR-25SEP2025` | 29,799,580% | 100.0% | 91.5% | $5,049 | **AVOID** | bad debt outstanding |
| 7 | `RSS` | 29,799,579% | 100.0% | 77.0% | $3,598,498 | **AVOID** | bad debt outstanding |
| 8 | `FUSD` | 29,795,767% | 100.0% | 77.0% | $2,391,464 | **AVOID** | oracle_unusable at RED |
| 9 | `COPS` | 4,848% | 100.0% | 86.0% | $25,112,173 | **AVOID** | sustained_low_liquidity at RED |
| 10 | `sUSDX` | 4,816% | 100.0% | 77.0% | $1,434,938 | **AVOID** | sustained_low_liquidity at RED |
| 11 | `GUARD` | 4,593% | 100.0% | 86.0% | $25,106,828 | **AVOID** | sustained_low_liquidity at RED |
| 12 | `PROOF` | 4,353% | 100.0% | 86.0% | $25,101,740 | **AVOID** | sustained_low_liquidity at RED |

**Twelve of twelve fail.** Every one sits at 100% utilisation.

---

## Why 29,799,580%

That is not a yield. It is a division by nearly zero.

A lending market's supply APY rises with utilisation `U`:

```
supplyAPY ≈ borrowAPY × U × (1 − reserveFactor)
```

As `U → 1`, the borrow curve runs to its asymptote and `supplyAPY` explodes. At `U = 100%`
the market has **no liquidity left to withdraw** — the number that looks like the highest
return is a direct measurement of how impossible exit has become.

32 of the 100 markets were flagged `LOCKED` (utilisation > 95%): depositors cannot withdraw.

---

## The honest part

Screening the same data gives:

```
REAL     17    (17%)
CAUTION  26    (26%)
AVOID    57    (57%)
```

The best `REAL` markets still show **188%–735% APY at 69–90% utilisation**. Those numbers
are also elevated, also depend on incentive emissions, and are not a promise. The screen
says *"no obvious solvency defect at this timestamp"* — it does not say "safe," and it does
not predict.

The value of the screen is the `AVOID` column: 57 markets it tells you to skip, and the
specific reason for each.

---

## Caveats, stated plainly

- **A snapshot, not a forecast.** Every row is a measurement at fetch time.
- **Mamo may filter downstream.** This tests the rule *as documented*. I could not verify
  their contract's selection logic — Basescan's API returned 403, and the docs do not
  publish it. If they filter by TVL or utilisation in code, this critique softens.
- **Base + Morpho only.** Coverage is exactly that.
- **Duplicate markets are real.** 25 distinct HERMES market IDs exist with identical
  collateral and LLTV; the table is deduplicated by collateral.

---

## Reproduce

```bash
python3 morpho_fetch.py     # live Morpho GraphQL, ~1s, no key
python3 lending_screen.py   # -> lending_screen.json
```

Then:

```python
import json
rows = json.load(open("lending_screen.json"))
top = sorted(rows, key=lambda r: r.get("net_apy") or 0, reverse=True)[:12]
print([(r["collateral"], r["verdict"]) for r in top])
```

---

*Aegis — a falsification harness for LP and lending markets. No orders, no signatures, no
custody. AGPL-3.0.*

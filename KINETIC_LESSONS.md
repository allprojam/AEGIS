# Kinetic lessons applied to the Morpho allocator

**Built:** `allocator.py`, `tests/test_vault_allocator.py`. **Simulation only** — no signing, no
chain writes, no vault. **88 assertions passing across the whole suite.**

---

## The three rules, and what changed

### Rule 1 — Borrow depth. Implemented as specified.

`max_alloc = 20% of the market's current borrow volume`. Real effect: **2 markets rejected on
depth** out of 60.

### Rule 2 — Oracle provenance. Implemented, but WEAKER than the brief asked for.

The brief wanted *"minimum update threshold verified against on-chain block frequency."* **I could
not implement that, and I will not describe it as if I did.**

What the API exposes:

```
Oracle.type   -> ChainlinkOracle | ChainlinkOracleV2 | CustomOracle | Unknown
Oracle.data   -> baseFeedOne, baseFeedTwo, quoteFeedOne, quoteFeedTwo, scaleFactor
```

**There is no heartbeat, no update interval, no last-update timestamp.** A real latency check needs
per-feed on-chain reads — a different cost basis, and the same indexer work deferred earlier.

**What I implemented instead is a provenance check:** reject unless the oracle is a recognised
Chainlink type. Rationale: Morpho allows a custom oracle per market, and an unrecognised oracle is
not a judgement about quality — **it is the absence of any information, and that cannot be
underwritten.**

Live result across the 60 markets:

```
ChainlinkOracleV2   27
Unknown             32
null                 1
```

**33 rejected on oracle provenance.** A third of the market set declares an oracle we cannot
identify.

### Rule 3 — Volatility-weighted LLTV. Implemented, with a CORRECTION to the brief.

**The brief's framing was dimensionally wrong, and applying it literally would have rejected the
safest markets.** It suggested rejecting where historical drawdowns violate the liquidator margin,
comparing LLTV to volatility directly. But LLTV is a ratio and annualised vol is a rate.

Measured consequence of the literal reading:

```
cbBTC   LLTV 86%, annualised vol 109%   -> would be REJECTED
WETH    LLTV 86%, annualised vol 172%   -> would be REJECTED
```

**cbBTC holds $1.7B and is the largest, steadiest market in the set.** Rejecting it is wrong.

**The correction: the liquidation window is intraday, so the units must be daily.**

```
margin          = 1 - LLTV              how far price can fall before bad debt
daily_vol       = annualised / sqrt(365)   how far price MOVES in a day
sigma_to_breach = margin / daily_vol_x     how many daily moves kill the position
```

That is a genuine risk statement:

```
cbBTC   LLTV 86.0%   margin 14.0%   daily vol 5.71%   -> 2.5 sigma
WETH    LLTV 86.0%   margin 14.0%   daily vol 9.01%   -> 1.6 sigma
USR     LLTV 91.5%   margin  8.5%   daily vol 26.94%  -> 0.3 sigma
yoUSD   LLTV 91.5%   margin  8.5%   daily vol 79.71%  -> 0.1 sigma
```

**cbBTC needs a 2.5-sigma day to breach. USR needed 0.3 — a routine day ends the market.** That
distinction is only visible in the correct units.

`SIGMA_FLOOR = 2.0` is a **policy parameter, not a finding.** It is exposed as configuration for
that reason. **7 markets were rejected on this rule** that passed everything else:

```
WETH     sigma 1.55      wstETH   sigma 1.49      cbETH  sigma 1.49
USR      sigma 0.32      RLP      sigma 0.90      yoUSD  sigma 0.11
```

---

## The allocation today

```
capital        $1,000,000
allocated      $646,741   (64.67%)
UNALLOCATED    $353,258   (35.33%)
eligible       13 of 60

NOT_REAL             42
ORACLE_UNVERIFIED    33
VOL_UNKNOWN          32
LIQUIDATION_THIN      7
NO_DEPTH              2
```

**35% unallocated is a defined state, not a failure.** A vault that cannot find a defensible market
should hold cash, and the allocator returns that rather than forcing capital into the least-bad
option.

---

## Kinetic lesson now IMPLEMENTED: collateral grouping

`MAX_COLLATERAL_CONCENTRATION = 0.30`. Markets are grouped by collateral symbol and each group
receives a budget, distributed across the markets inside it weighted by sigma-to-breach (clamped
at `SIGMA_WEIGHT_CAP = 10.0` so one very safe market cannot absorb its whole bucket).

**Why it belongs in the curator and not the protocol:** Morpho isolates *markets*. A curator
allocating across several markets that share a collateral has **re-created the pooled exposure
Morpho removed**. Five cbBTC markets with different ids are one position. That is exactly the
concentration Kinetic prevents with protocol-level supply caps.

### What it changed, and an honest limit on the parameter

```
before grouping   cbBTC  2.94%   (split by capacity)
after grouping    cbBTC  9.37%   (re-weighted by sigma)
```

**But the 30% cap is currently INERT.** With 11 collateral groups, budgets sum to 11 x 30% = 330% of
capital, so the total-cap rescale dominates and every group lands at ~9.4%. **The cap only binds
when there are fewer than four groups** — verified: at 3 groups one sits exactly at 30%.

**That is correct arithmetic, not a bug, and it is asserted in test 8b so nobody assumes the cap is
doing work it is not.** The grouping still usefully re-weights *within* buckets; the group ceiling
is a limit that will start to bite as the eligible set narrows — which is precisely when
concentration risk is highest.

**First-loss reserve / yield retention.** Not implemented. The allocator sizes *targets*; it does
not model a retained buffer. Adding one means modelling performance fees, which requires a vault,
which does not exist. Deferred rather than faked.

**Close factor and liquidation incentives.** Not implemented. Morpho fixes these per market at
creation (`1/LLTV - 1`) and they are not exposed as parameters we can vary. The sigma-to-breach rule
is the closest available proxy.

---

## Two bugs, both mine, both caught by the tests

**1. `VOL_UNKNOWN` on all 60 markets.** My caching code re-implemented the GraphQL unwrapping and
forgot the `{"marketById": ...}` envelope, so every price history came back empty. **It failed
silently** — the output looked like "no volatility data available" rather than "wrong nesting".
Fixed by calling the already-tested `fetch_history()` instead of duplicating it.

**2. The test fixture had zero volatility.** `flat()` returned a constant price, so standard
deviation was 0 and the allocator correctly rejected it as `VOL_UNKNOWN`. **The fixture was wrong,
not the rule** — zero volatility is unmeasurable, not safe. Renamed to `calm()` with real variance.

**That second one is the fifth time in this project a test error nearly caused a "fix" to working
code.** The pattern is consistent enough to be a rule: when a rule rejects something surprising,
check the input before the logic.

---


---

## RULE 4 — the reserve buffer, and why 100% deployment was a regression

`RESERVE_BUFFER = 0.15`. Deployable capital is `capital * (1 - RESERVE_BUFFER)`; **every downstream
budget derives from that figure**, so the reserve cannot be bypassed by a later rescale.

**Why this was not optional.** The collateral grouping took deployment from 64.7% to **100%**, and
that is a solvency regression, not an efficiency gain:

- a vault's deposit side is **demand-driven** — depositors withdraw on their schedule, not ours
- Morpho markets can sit at **100% utilisation with no redeemable liquidity**
- so a buffer is **not** a fallback for when opportunities are scarce — it is a structural cost of
  accepting deposits at all

**100% deployment arose from arithmetic, not from a decision.** With 11 eligible groups and a 30%
cap that does not bind, the rescale distributed everything. A cap that fills only because nothing
stopped it is not a policy.

**The buffer is asserted across every scenario that previously reached 100%** — 1 market, 5 sharing
one collateral, 6 collaterals, 20 collaterals, capital from $1 to $1e9. All stop at 85%.

### A real rounding bug this surfaced

Per-market `round(x, 2)` **summed above the budget**: six markets each rounding up by under a cent
pushed the total **$0.02 past the 85% limit**.

**A cap that can be exceeded by rounding is not a cap.** Fixed: floor to the cent, then trim the
largest holdings if the total still exceeds the ceiling. Verified exact at 2, 6, 20 and 60 markets.

### An assertion of mine that was simply wrong

Test 8e asserted `allocated + reserve == capital`. **That is false and should be false.** With one
market, the capacity cap leaves most of the deployable budget uninvestable:

```
capital = allocated + reserve + IDLE
```

Asserting the identity would have **demanded the allocator over-allocate** — the exact bug it
exists to prevent. Replaced with the correct invariant: `allocated + reserve <= capital`, plus
`allocated <= deployable`.

**That is the sixth time in this project a test error nearly forced a change to working code.**
The pattern is now unambiguous enough to be the first rule of the suite: *when an assertion fails,
establish whether the code or the assertion is wrong before touching either.*

---

## Status

```
compile, project root        PASS
LP position math             PASS  (25)
LP economics                 PASS  (19)
vault allocator              PASS  (44)
parity harness               PASS
replay, all stored runs      PASS
                             ------
                             88 assertions
```

**Simulation only. No signing, no chain writes, no vault.** The allocator produces target weights so
the arithmetic can be tested before capital is ever at risk.

## Suite status

```
compile, project root        PASS
LP position math             PASS  (25)
LP economics                 PASS  (19)
vault allocator              PASS  (44)
parity harness               PASS
replay, all stored runs      PASS
                             ------
                             88 assertions
```

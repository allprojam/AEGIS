# Morpho Blue / MetaMorpho integration — plan and feedback

**Nothing built. Read-only reconnaissance only.** Every fact below was verified against the live
Morpho API and Base RPC during this session.

---

## What I verified

| item | result |
|---|---|
| Morpho GraphQL API | **works** — `https://blue-api.morpho.org/graphql` (POST, JSON) |
| Base RPC | **works now** — `base-rpc.publicnode.com`, `mainnet.base.org`, `base.drpc.org`, `1rpc.io/base` all return chainId 8453. (An earlier 403 was transient.) |
| Base USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` — confirmed, matches your prompt |
| Morpho Blue Base | live, 12+ USDC-denominated markets returned |
| MetaMorpho vaults on Base | exist at scale: Gauntlet USDC Prime **$413.9M**, Spark **$359.3M**, Steakhouse **$123M** |

**Field names in the prompt are wrong.** The real schema:

```
prompt said            actual field
uniqueKey              marketId
lltv (percent)         lltv  (BigInt, divide by 1e18)
supplyAssetsUsd        state.supplyAssetsUsd     OK
supplyApy              state.supplyApy           OK
rewardApy              state.netSupplyApy        ALREADY NETTED
```

---

## Feedback, in order of importance

### 1. DISTRIBUTING 100% OF CAPITAL IS A SOLVENCY BUG — the spec's most serious flaw

Phase 3 says *"evenly distribute 100% of hypothetical vault capital."* **That cannot be right.**

A MetaMorpho vault's depositors can withdraw at any time, but the vault's capital is lent into
markets that can be **100% utilized**. Live example from the API right now:

```
HERMES   LLTV 98.0%   TVL $229.9M   utilization 100.0%
```

**Utilization 100% means there is nothing to withdraw.** If the vault lends out everything and
depositors queue up, the vault cannot pay them — and a vault that cannot pay is a bank run.

**The allocator must hold a liquidity buffer.** This is a parameter, not an afterthought:
`max_lendable = deposits * (1 - buffer)`, with buffer sized to observed withdrawal volatility.
**Without this, the "institutional" vault is the least safe thing in this repo.**

### 2. Two of our seven checks do not transfer to lending markets

`screen.py` was built for AMM liquidity pools from the DefiLlama feed. Lending markets are a
different instrument.

| check | transfers? | why |
|---|---|---|
| THIN (TVL < $1M) | **yes**, but the floor should be higher | a lending market needs depth to absorb exits |
| SUBSIDISED | **redundant** | `state.netSupplyApy` already nets rewards against organic |
| NO_YIELD | **yes** | trivially |
| OUTLIER | **yes, and critical** | see the HERMES row below |
| SPIKE | **yes, better data available** | `weeklySupplyApy`, `monthlySupplyApy`, `avgSupplyApy` |
| TURNOVER / DEAD | **no** | there is no "turnover" in a lending market |
| IMPLAUSIBLE | **partially** | maps better to utilization + LLTV |

**And two lending-specific risks are missing entirely, which the prompt does not mention:**

- **UTILIZATION** — the lending equivalent of THIN. A 100%-utilized market cannot be exited.
- **BAD DEBT** — `badDebt { usd }` and `realizedBadDebt { usd }` are **live fields**. This is
  *realised loss*, the one metric that is unambiguous. It should be a hard exclusion.
- **LLTV** — 98% LLTV is one depeg away from bad debt.

**The live data proves the point immediately.** Pulling USDC markets on Base by TVL:

```
collateral     LLTV    TVL$M   util supplyAPY           warnings
cbBTC         86.0%   1703.5  90.1%     4.43%           -
USDe          91.5%    390.5  90.0%     3.71%           -
HERMES        98.0%    229.9 100.0% 297986.41%  not_whitelisted, unrecognized_collateral,
                                                 sustained_low_liquidity (RED)
WETH          86.0%    104.5  90.1%     4.51%           -
HERMES        98.0%     84.4 100.0%  41889.30%  + sustained_low_liquidity (RED)
```

**A 297,986% supply APY.** That is the OUTLIER class exactly — and note **Morpho publishes its own
warnings**, including a RED-level `sustained_low_liquidity`. **We should consume those warnings, not
re-derive them.** Where the protocol itself flags a market, ignoring it and computing our own
equivalent is strictly worse.

### 3. The 10% performance fee is above market and will not sell

Existing Base USDC vaults:

```
Gauntlet USDC Prime   $413.9M   fee = 0      timelock 604800 (7d)
Spark USDC Vault      $359.3M   fee = 0.10   timelock 864000 (10d)
Steakhouse USDC       $123.0M   fee = 0.25   timelock 604800
Steakhouse Prime       $14.0M   fee = 0.05   timelock 604800
Pangolins USDC         $12.2M   fee = 0.10   timelock 259200
```

**The largest vault in the category charges 0%.** At 4.43% gross (the cbBTC market's real rate), a
10% fee takes ~0.44% and leaves the depositor ~3.99%. **Gauntlet delivers the same yield for 0%.**

**This is a business problem, not a technical one, and the plan does not address it.** What does Aegis
offer that Gauntlet does not? If the answer is "a screen that rejects markets," note that Gauntlet and
Steakhouse are professional risk curators doing exactly that — with track records, audits and
$500M+ AUM between them.

### 4. A 1-day timelock is LESS safe than every competitor

```
Gauntlet    7 days
Spark      10 days
Steakhouse  7 days
Aegis       1 day    <-- your parameterisation
```

**The timelock is the parameter that protects depositors from a malicious or compromised curator.**
Choosing the shortest one in the category, on a vault marketed to institutions, is backwards.
**Recommend 7 days.** It costs nothing and it is the single cheapest credibility signal available.

### 5. The CI test as specified is nearly vacuous

*"Assert that no capital is ever allocated to a flagged market."* That is the filter restated — the
test passes as long as `if flagged: 0` is in the code. It proves nothing.

**The tests that matter are adversarial:**

```
- all markets flagged          -> what is the target? (0% is a defined but bad state)
- zero markets pass            -> vault holds 100% idle USDC and still charges a fee. Define.
- one market's data is stale   -> fail closed, not open
- capacity < total capital     -> over-allocation must be impossible
- correlated collateral        -> 5 markets, one collateral asset, is ONE position
- malformed/missing fields     -> must not silently become 0 or NaN
- utilization 100%             -> cannot deposit, must be excluded regardless of verdict
- buffer respected             -> sum(allocations) <= 1 - buffer, always
```

**Property-based testing, not one assertion.**

### 6. The screen adapter is where the bugs will be

`screen.py` reads DefiLlama-shaped dicts. Morpho returns a different shape, and `LLTV` is a BigInt
needing `/1e18`, `supplyApy` is a fraction not a percentage, and `apyBase7d` does not exist.

**The adapter needs its own tested boundary.** Every unit conversion is a place a wrong number can
enter silently. This is the same class of bug as the `241.5%` share and the `str`-vs-`int` crash.

---

## Where your plan is right, and it is mostly right

**The key-segregation architecture is correct and it is the best part of the brief.**

- **Safe + hardware wallet as curator** — right, and Morpho's vault state exposes exactly these roles:
  `curator`, `owner`, `guardian`, `allocators`. Deploying to a Safe is directly supported.
- **Do not send gas from the personal wallet** — right, and worth stating plainly: a direct transfer
  permanently links the two identities on-chain.
- **The Keeper wallet concept maps to a real role.** MetaMorpho has an **`allocator`** role whose only
  power is to allocate. Confirmed live:
  ```
  Gauntlet USDC Prime allocators:
    0xA090dD1a701408Df1d4d0B85b716c87565f90467
    0xffD6bF4906a6BCe134B70dd74Afe01c917B9119b
  ```
  **So the contract-enforced restriction you want already exists** — the Keeper does not need a
  bespoke permission contract. That is a genuine simplification.
- **VPS never holds the curator key** — correct, keep it.
- **Timelock exists to protect depositors** — correct, see point 4 for the parameter.

**Two small corrections:**

- **Outbound RPC anonymity is low-value here.** The Keeper key is low-balance and contract-limited, so
  proxying adds a failure point mid-transaction for little gain. Reads through a proxy: fine. Writes
  through a proxy: a new way to fail.
- **Cloudflare for inbound is right, but nothing is deployed yet.** Currently the page is on plain
  HTTP behind `tailscale serve` on the tailnet only. That is the correct state for now.

---

## The plan I would actually run

**Phase 0 — adapter and screen extension (before any vault work)**

1. `morpho_fetch.py`: GraphQL, USDC markets on Base, fields from the **verified** schema, including
   `badDebt`, `realizedBadDebt`, `warnings`, `lltv`, `oracle`, `utilization`.
2. `morpho_adapter.py`: Morpho shape -> the screen's shape. **Unit conversions tested** (`/1e18` on
   LLTV, fraction-vs-percent on APY, missing `apyBase7d` handled explicitly).
3. Extend the screen with **UTILIZATION** and **BAD_DEBT**; mark TURNOVER as not-applicable rather
   than silently absent.
4. Consume Morpho's own `warnings` as a **separate input**, not a re-derivation.
5. Run it. **Report what it flags on live Base markets before writing a line of vault code.**

**Phase 1 — allocator logic with the buffer**

6. `allocator.py` with: liquidity buffer, per-market capacity cap, utilization exclusion,
   correlated-collateral grouping, and a defined behaviour for "nothing passes."
7. Adversarial tests per point 5. Property-based: `sum(alloc) <= 1 - buffer` as an invariant.

**Phase 2 — deploy script, DRY RUN ONLY**

8. `morpho_vault_deploy.py`: encode the `createVault` calldata, **print the hex and estimated gas,
   broadcast nothing.** Confirm which factory is current first — the API shows **two distinct factory
   addresses** on Base (`0xFf62A7c278C62eD665133147129245053Bbf5918`, `0xA9c3D3a366466Fa809d1Ae982Fb2c46E5fC41101`)
   and I could not resolve which is canonical from the API alone. **That must be confirmed against
   Morpho's docs before encoding anything** — a wrong factory address is an unrecoverable error.
9. **Fee and timelock revisited** in light of points 3 and 4.

**Phase 3 — you deploy, with hardware wallet, after reviewing the dry run.**

---

## The question the plan does not answer

**What does Aegis offer that Gauntlet and Steakhouse do not?**

They are professional risk curators with $500M+ on Base, charging 0-0.25%, with 7-10 day timelocks.
"We run a screen that rejects bad markets" describes their product too, and they have a track record.

**Our defensible asset is the thing we measured**: we can state, with a confidence interval, that
46.7% of indexed pools lose more than half their liquidity in a year and that no high-yield pool paid
what it advertised. **That is a marketing and disclosure asset.** Whether it is a vault-management
edge is unproven — and the vault is a product that can lose other people's money, which is a
different risk category from a page that classifies yields.

**My recommendation: build Phases 0 and 1, stop before the vault.** Learn what the screen says about
live Morpho markets. That is genuinely valuable and risk-free. **The vault is the step where the
failure mode changes from "we published a weak claim" to "someone lost their capital."**

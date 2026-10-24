# APY Cloud — measured

**I was wrong to say this didn't exist.** It is real, documented, and architecturally one of the
better-designed things in this entire investigation. Correction noted.

## What it actually is

From their docs (`help.enosys.global/.../apy-cloud`):

> "The APY Cloud is the engine that converts protocol earnings from across the Ēnosys ecosystem into
> sustainable yield for governance stakers. **Instead of paying yield from token emissions**, it pools
> the real fees that Ēnosys products already generate (DEX swap fees, lending fees, FTSO rewards,
> simple staking commissions) and distributes them every epoch."

**Three contracts, each with a documented job:**

```
Profit Distributors  one per fee source, splits team/Cloud at a gov-set ratio
APY Cloud Vault      aggregates fees, swaps non-system tokens to WFLR
APY Cloud Distributor holds balance, settles each epoch, pays staking pools
```

**Fee sources and the Cloud's cut:**

| source | team | **APY Cloud** |
|---|---|---|
| DEX V2 protocol fees | 80% | **20%** |
| DEX V3 protocol fees | 50% | **50%** |
| Loans V2 fees | 80% | **20%** |
| Simple Staking commissions | 50% | **50%** |
| FTSO Rewards Redistribution | 50% | **50%** |

**Guardrails:** Minimum APY **5%**, Maximum APY **35%**, Excess Threshold **42%** (=120% of max).
Three modes — Normal / Excess / Stressed — with a reserve smoothing dips.

**This is a real-yield design and it is genuinely well thought out.** Reactive Distributions, no
emissions, bounded by actual earnings, reserve smoothing. It is the opposite of the subsidy structures
found everywhere else in this project.

## But here is the arithmetic

**The fees feeding it are small.** Measured from DefiLlama:

```
Enosys AMM V3   30d fees  $136,124    1y  $2,450,231
Enosys Loans    30d fees  $ 66,048    1y  $  671,644
Enosys AMM V2   30d fees  $    203    1y  $    4,840
-----------------------------------------------
total ecosystem 1y fees         ~$3,126,715
at the Cloud's 20-50% cut       ~$0.6M - $1.5M/yr to stakers
```

**And I can read what is actually sitting in the contracts right now:**

| contract | WFLR | APS | FLR |
|---|---|---|---|
| **APY Cloud Distributor** | **137,491.33** | 0.07 | 0 |
| APS Staking Manager | 214,912.61 | 1,058.29 | 0 |
| HLN Staking Manager | 285,961.80 | 0.22 | 0 |
| APY Cloud Vault | 0.00 | 0.00 | 0.00 |
| **Reserve Fund** | 0.00 | **3,000.00** | 5.00 |
| Loans Splitter | 0.00 | 0.00 | 0.00 |
| DEX V3 Splitter | 0.00 | 0.00 | 0.00 |

**The Distributor is holding 137,491 WFLR awaiting distribution.** The Reserve holds **3,000 APS** —
which is notable given APS total supply is 15,000, so **the reserve is 20% of all APS in existence.**

**But the Vault and both Splitters read zero.** That means fees are being swept through rather than
accumulating, which is consistent with a live system, but it also means I cannot read a *running* fee
rate from balances alone.

## The staking pools are tiny

```
APS Staking Manager totalSupply   1,058.29 APS staked
APS total supply                 15,000.00
-> 7.1% of APS supply is staked for governance yield
```

**1,058 APS staked.** At APS ~$558, that is **~$590,000 of staked value** sharing the ecosystem's
~$0.6–1.5M annual fee cut.

**That is the number that matters, and it is not bad:**

```
if Cloud receives $1.0M/yr and APS stakers hold 7.1% of the split
-> could be a very high rate on a small pool
```

**But it depends entirely on: (a) the actual fee cut received, (b) the split between APS and HLN
pools, which is proportional to staked TVL valued in WFLR.**

**HLN staking holds 285,961 WFLR vs APS's 214,913 WFLR — so by the documented rule (split proportional
to each pool's staked TVL in WFLR), HLN currently receives ~57% of the distribution and APS ~43%.**

## What I could not verify

**I could not read the live APY, the min/max APY parameters, or the epoch state.** Every getter I
guessed (`minimumAPY()`, `maximumAPY()`, `excessAPYThreshold()`, `currentEpoch()`) **reverted**, and
Blockscout returns **zero verified contracts** named `APYCloud` / `APY Cloud` / `ProfitDistributor` —
so the contracts are **not verified under those names**, and I cannot pull their ABIs to find the real
function names.

**Dune has their dashboard** (`dune.com/enosys_global/apy-cloud`) and the page title confirms it exists,
but Dune renders client-side so no numbers are available without their API.

**So: I can confirm the architecture, the fee sources, the guardrail values from the docs, and the live
token balances. I cannot confirm the current realised APY.**

## The honest read

**The design is genuinely good and it is the only real-yield, non-emission, bounded-APY structure found
in this entire investigation.** That deserves saying plainly.

**Three things to weigh:**

1. **The fee base is ~$3.1M/yr ecosystem-wide**, of which the Cloud takes 20–50%. That caps everything.
   **It is a real yield bound by real revenue, which is exactly what you want and also exactly what
   limits it.**
2. **Only 1,058 APS is staked (7.1%)**, so the per-staker rate could be high — but the pool is small
   and 20% of all APS sits in the Reserve, which is a concentration worth understanding.
3. **The docs say Minimum APY 5%.** If the fee income does not cover 5%, **the Reserve Fund provides
   stimulus** — which means part of the yield is a reserve drawdown, not current earnings. That is
   honest and disclosed, but it means the 5% floor is not free money; it is spending saved fees.

**What I would need to give you a real number:** the `APY Cloud` contract ABIs (or the Dune dashboard
figures). If you can paste the current APY from `gov.enosys.global`, I can check it against the fee
flows I have already measured and say whether it is being paid from earnings or from the reserve.

**This is a better structure than the Stability Pool. It is also a much smaller fee base.** The
question is whether the current APY is covered by the ~$1M/yr of real fees, or whether the Reserve is
subsidising it — and that is measurably answerable with one more piece of data.

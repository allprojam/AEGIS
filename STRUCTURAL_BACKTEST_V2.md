# Aegis Structural Backtest v2 — boundaries implemented, result still inconclusive

**Answering the structure question first, then the state of the data.**

---

## How to structure the on-chain spot checks: run them INLINE

**Not batched at the end.** The evidence:

**1. The check touches a small subset.** A pool needs the de-tracking resolver only if its chart has
*ended*. In the 102 pools collected, **zero charts had ended** — the resolver never fired. If that
holds at scale, the check is a minority operation and batching saves nothing.

**2. It is one HTTP call, not an RPC call.** I could not use raw RPC from this box:

```
base-rpc.publicnode.com   ->  HTTP 403 Forbidden
mainnet.base.org          ->  HTTP 403 Forbidden
```

`web3` 7.15.0 is installed but there is no reachable node. The resolver therefore uses
**GeckoTerminal**, which returns the same fact in a single request:

```
live Base pool       reserve_in_usd = $156,396,113    (DETRACKED - still funded)
zero-address token    HTTP 404                        (CONFIRMED_DEAD)
Aave Ethereum pool    no AMM pair -> UNKNOWN          (correctly abstains)
```

**3. Batching would force a second pass.** Doing it inline means the outcome is decided once, while
the chart is in hand. Batching at the end requires re-resolving 600 pools to find which ones need
the check - strictly more work for the same answer.

**Recommendation: inline, sequential, one call, with the existing backoff.** Also note the resolver
**excludes lending markets** (`aave-v3`, `compound`) because they have no AMM pair - those return
`UNKNOWN` and are dropped from scoring rather than guessed at.

---

## The three boundaries, implemented and tested

**1. Outcome = Severe Capital Destruction.** Not death.

```
FAILED     TVL < 10% of baseline, OR final TVL < $10,000
IMPAIRED   TVL fell below 50% but not below 10%    <- the slow bleed you identified
SURVIVED   anything else
```

**9 of 9 boundary cases pass**, including exactly at 10%, exactly at 50%, and exactly at the $10,000
floor.

**2. De-tracking resolved, not assumed.** `DETRACKED` pools are **excluded from both arms** rather
than counted as deaths. `UNRESOLVED` likewise.

**3. Cohort anchored to a historical window.** The candidate list is filtered to pools whose own
chart shows data on or before T-365d. DefiLlama has **no** `/pools/<date>` endpoint (verified 404),
so the chart's first timestamp is the anchor - a statement about the past, not about today.

---

## The result, and why it is still not publishable

```
102 pools

FAILED       7   ( 6.9%)
IMPAIRED    43   (42.2%)     <- the slow bleed is the dominant outcome
SURVIVED    52   ( 51.0%)
```

**The headline comparison does not separate:**

```
FLAGGED   n=36   FAILED 5.6%   95% CI [ 1.5%, 18.1%]
PASSED    n=66   FAILED 7.6%   95% CI [ 3.3%, 16.5%]
```

**The intervals overlap, and the point estimate is again in the wrong direction.**

```
SUBSIDISED   n=7   14.3% [ 2.6%, 51.3%]   vs without 6.3%
```

**A 51% upper bound on n=7 is not a finding.** It is the same hint as before, and publishing it
would be exactly what this project exists to catch.

**To separate 20% from 10% at 95% confidence needs >=125 pools per arm - 251 total. We have 102.**

---

## What the v2 data does show, and it is more interesting than the headline

**`IMPAIRED` is 42% of the cohort.** Under the old binary definition, **43 pools that lost more than
half their liquidity were counted as "survivors."** That was the conflation you flagged, and
correcting it moved the largest single block of the data.

**Median TVL over 12 months: roughly 0.55.** Most of this index is shrinking, not dying. **A screen
that only counts deaths would report a healthy market that is actually being drained.** The
`IMPAIRED` band is where the structural failure lives.

**So the honest framing is not "our flags predict death." It is: "most pools in this index lose more
than half their liquidity in a year, and the binary death metric hides that entirely."** That is a
finding about the market, and it does not depend on the flag comparison resolving.

---

## Two things I got wrong, again, and caught

**1. I over-parallelised into a rate limiter for the second time.** At 6 workers, **600 of 600
requests returned HTTP errors**; sequential to the same URL returned 200. The chart endpoint
throttles on **concurrency, not volume**. Serial with a 0.05s delay and a 15s backoff: **0 errors,
93% hit rate on the prefiltered list.**

**2. The prefilter in v1 reintroduced survivorship bias.** Building candidates by matching against
the **live** feed made every candidate a pool that exists today - `DIED = 0 of 130` was structural,
not a finding. v2 anchors on the chart's own history instead.

---

## To finish

1. **~500 more pools**, resumable, paced. The script is chunk-safe (`structural_backtest_v2.jsonl`).
2. **A real mortality list.** Only 4 vanished UUIDs exist in the repo. A defensible death count needs
   the feed captured over time, not reverse-engineered from docs. **This is the binding constraint,
   not compute.**
3. **On-chain confirmation for the `DETRACKED` set** - currently zero, because no chart has ended yet.
4. **Publish the CI next to every number.** And lead with the `IMPAIRED` finding, which is already
   solid at this n and does not depend on the flag lift.

---

## Standing rules this pass added

5. **A binary outcome hides the interesting failure.** "Dead or alive" missed 42% of the cohort
   slowly bleeding out. Define the outcome in the units the risk actually occurs in.
6. **An aggregate with overlapping confidence intervals is not a result**, however good the point
   estimate looks. Compute the CI before the headline.
7. **If the instrument needed for rigour is unreachable, say so and find the equivalent.**
   Raw RPC was 403; GeckoTerminal answers the same question in one call.

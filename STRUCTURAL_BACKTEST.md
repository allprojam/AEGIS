# Aegis Structural Backtest — status

**Do the structural flags predict pool death or yield collapse 12 months out?**

## Where it stands

**82 pools collected. Not conclusive. Do not publish a number yet.**

```
FLAGGED   1/26 =  3.8%   died or collapsed   95% CI [ 0.7%, 18.9%]
PASSED    3/56 =  5.4%   died or collapsed   95% CI [ 1.8%, 14.6%]
```

**The confidence intervals overlap heavily, and the point estimate is in the wrong direction.**
To distinguish 10% from 5% at 95% confidence needs roughly **274 pools per arm — 548 total.**
We have 82. **Publishing this would be exactly the failure mode this project exists to catch.**

---

## Survivorship check: PASSED

Run before building, as asked. Vanished pools **do** retain their history:

```
d5413c29-...   1372 points   2022-08-28 -> 2026-10-07   last TVL $9,860
04effd53-...     79 points   2025-09-08 -> 2026-09-30   last TVL $15,367
d42a55e3-...    378 points   2025-09-09 -> 2026-10-07   last TVL $9,909
2f340114-...    727 points   2024-10-02 -> 2026-09-30   last TVL $4,821,339
```

DefiLlama does **not** purge dead pools from `/chart/{id}`. The cohort is not silently restricted
to survivors.

---

## Two mistakes I made and caught

**1. Survivorship bias that I introduced myself.** My first optimised candidate list was built by
matching `results.json` against the **live** feed — so every candidate was a pool that exists today.
`DIED = 0 of 130` was not a finding, it was structural. **Corrected** by adding the 3,309 historical
UUIDs found in the repo, of which 4 have vanished from the feed.

**Even now DIED = 0.** With only 4 known-dead UUIDs in hand, the cohort is still dominated by pools
that exist. **A credible mortality study needs a list of pools that died**, which means capturing
the feed over time — not a single snapshot plus reverse-engineering.

**2. Over-parallelising into a rate limiter.** At 16 workers, then 6, **600 of 600 requests returned
HTTP errors** — the whole endpoint was refusing us. Sequential requests to the same URL returned
200. The chart endpoint throttles on **concurrency**, not volume. Rewritten serial with a 0.05s
delay and a 15s backoff after a run of errors. Errors went to zero.

---

## What the preliminary data does suggest

**`SUBSIDISED` is the only flag showing lift so far:**

```
SUBSIDISED   n=6    16.7% died/collapsed    without: 3.9%    lift 4.2x
```

**But n=6.** That is a hint, not a result. With six pools, one outcome moves the number 17 points.

**The structural picture is also worth noting:** median TVL change over 12 months is **0.552**, and
`p25` was 0.316. **Most pools in this index are shrinking**, which means a $1M TVL floor is already
a meaningful filter — but "shrinking" is not the same as "died", and the outcome definition only
counts the latter.

---

## What the method can and cannot say

**Can:**
- apply `THIN`, `SUBSIDISED`, `NO_YIELD`, `IMPLAUSIBLE` using only data visible at the time
- measure TVL change and reporting-cessation over the following 12 months
- see pools that have vanished, because their history survives

**Cannot:**
- cover `OUTLIER`, `SPIKE` or the turnover check — `/chart` carries only
  `apy, apyBase, apyReward, tvlUsd, il7d, pricePerShare`. **This is a partial screen and must be
  labelled as such.**
- claim mortality at a useful confidence level yet. **n=82 against a ~548 requirement.**
- distinguish "died" from "stopped being tracked by DefiLlama", which are different things and the
  data cannot tell them apart.

---

## To finish this properly

1. **Collect ~600 pools.** The script is resumable (`structural_backtest.jsonl`, appended one pool
   per line) and prefiltered, so it only requests pools with ≥365 days of `count`. Roughly
   90% hit rate on the prefiltered list versus 50% on a blind scan.
2. **Pace the requests.** Serial, 0.05s apart, back off on bursts. The limit clears in about 20
   seconds.
3. **Report with confidence intervals, not point estimates.** A 4.2x lift on n=6 is not a headline.
4. **Separate "died" from "de-tracked".** If DefiLlama stops indexing a pool that is still live, it
   is not a death. This needs a spot check against a DEX.
5. **Only then** consider publishing — and publish the CI alongside the number.

---

## Standing rule this pass reinforced

**An optimisation that makes the data easier to collect can silently break the thing being
measured.** The prefilter made the scan 2x more efficient and introduced a survivorship bias that
made the headline metric structurally zero. Efficiency changes must be checked against the
measurement's meaning, not just its speed.

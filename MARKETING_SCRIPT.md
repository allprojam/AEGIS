# Aegis — the marketing script, with every number sourced

**The thesis is correct and it is the strongest one we have:**

> **We are not selling a directory. We are selling the underwriting discipline that stops capital
> from being vaporised.**

That holds. But four of the supporting figures did not survive checking, and one of them is exactly
the kind of claim we built this project to catch. Corrected below, each with its source.

---

## The script

### The number is a slice, not the market

**16,786 pools. 104 chains. 498 protocols.** *(source: `yields.llama.fi/pools`, pulled 2026-10-07)*

That is **DefiLlama's curated yield set** — the pools somebody bothered to index, not the pool
universe. Across live DEXs on **329 chains** *(source: `api.llama.fi/v2/chains`, chains with TVL > 0)*
there are orders of magnitude more pairs, and thousands more created weekly.

**And 16,786 was never the point.** Here is what the same feed says when you sort it by size:

```
pools above $1M TVL:          2,766   (16.4%)
pools under $100k TVL:        8,772   (52.1%)
```

**More than half of the index is too small to deploy into.** A pool holding $40,000 cannot absorb a
$50,000 position — you would move the price on entry and get destroyed on exit. **Our own screener
already flags these `THIN`, and they are the single largest rejection reason at 14,064 pools.**

**So the addressable set is not 16,786 and not "hundreds of thousands." It is the ~2,700 pools where
capital actually concentrates** — carrying **$93.8B in all-chain DeFi TVL** *(source:
`api.llama.fi/v2/historicalChainTvl`, 2026-10-07)*.

**That is not a weaker claim. It is a better one: we cover where the money is, and we can prove the
rest is too small to matter.**

### The buyer is the allocator, not the pool

The pool is a contract. The buyer is a person or protocol about to move capital into it.

**A pool is not audited once. It is audited every time somebody decides to enter it.** Uniswap v3
WETH/USDC has been evaluated thousands of separate times by thousands of separate depositors. **Every
one of those was a decision made without a tool that could tell them whether the yield was real.**

**And the universe churns.** 3,849 pools in the index are **under 90 days old** *(22.9%, measured)*.
New incentive programmes launch weekly. Capital migrates from decaying farms into new ones, and
**every migration is a fresh decision with no due diligence attached.**

### What we actually sell

> **Bring your strategy or your pool thesis. We run it against next-bar execution, real fees, real
> gas, ruin handling, and a fee-charged buy-and-hold baseline. We show you what fails before you fund
> it.**

**And we can prove it works by pointing at ourselves:** we ran our own five strategies against
buy-and-hold on three years of hourly bars. **34 of 45 lost. Correlation between how well the asset
performed and the strategy's alpha: −0.996.** We published that. **Nobody selling yield tools does
that, because it kills the sale.**

---

## The four figures I had to change

| claim | status | corrected | source |
|---|---|---|---|
| "$100B+ in locked DeFi capital" | **overstated** | **$93.8B** | `api.llama.fi/v2/historicalChainTvl` |
| "80+ chains" | **understated** | **329 chains with TVL > 0**; feed covers 104 | `api.llama.fi/v2/chains` |
| "16,830 is a DefiLlama slice" | **TRUE** | stands — 16,786 pools, 498 protocols | `yields.llama.fi/pools` |
| **"80% of yield pools die within 90 days"** | **NOT VERIFIABLE** | see below | — |

### The one that matters most

**"80% of yield pools die within 90 days" cannot be supported by this data, and I would not print it.**

The feed's `count` field is **days of history**. It records pool **birth**, not pool **death** — a dead
pool keeps its row and its history intact. **There is no death date in the data.**

What the data actually shows: **22.9% of pools are under 90 days old**, median age **294 days**. Not
80% dying — 23% being new.

**This is the exact move from the gold transcript.** A precise-sounding, unsourced, unfalsifiable
statistic that makes the argument feel inevitable. **We fact-checked that transcript last week and
called it out for precisely this.** Printing "80% die in 90 days" would make us the thing Aegis
exists to catch — and it would be found by anyone who checked, which is the one thing our whole
positioning depends on.

**The honest version is stronger anyway:** *"52% of the indexed pool universe holds under $100,000.
You cannot deploy meaningful capital into a pool that small. That is not a churn problem — it is a
capacity problem, and we measure it."*

### Unverified, so flagged as such

**"3 million monthly active DeFi wallets"** — I could not verify this from a source I can reach
(DappRadar and similar gate the figure). **Do not print it without a citation.** The argument does not
need it: **329 chains and $93.8B in TVL are already measured facts.**

---

## The strategic problem the TAM argument exposes

**Worth stating plainly, because it is real.**

**Our tool audits what is in the DefiLlama feed.** The browser auditor resolves against an 808-entry
address index drawn from that feed; the MCP resolves from the same source. **Paste a pool that is not
indexed and the honest answer is "not in the scanned set."**

So the TAM argument — *"hundreds of thousands of pools exist"* — is an argument about pools **we
cannot currently audit.**

**Two ways forward, and they are different businesses:**

1. **Expand coverage.** Direct RPC reads across chains. That is the on-chain inspector we deliberately
   deferred to a lab repo, because it is a different cost basis: nodes, an indexer, per-chain work.
2. **Own the concentrated set.** 2,766 pools above $1M carry the capital that matters. **Be the tool
   that is right about where the money is, rather than spread thin across 100,000 pools nobody funds.**

**I would pick 2 first and let revenue fund 1.** It matches the product that exists today, and it is
the claim we can defend under scrutiny.

---

## One contradiction to resolve

**You told me: *"Im not a fan of subscriptions maybe just pay per audit?"*** — and the pricing built
into the page is $0.05/audit with bulk at $0.01.

**This brief then proposes $49–$99/mo and $500–$2,500/mo tiers.** Both can be true — pay-per-audit for
retail, retained monitoring for desks — **but they are different products and the page needs to say
so.**

**The pay-per-audit equivalent of a monitoring subscription is a volume commitment:** *"10,000 audits,
$100, they never expire, run them whenever you like."* **Same economics, no recurring bill** — and it
keeps the line you approved: *"a subscription bills you in the months you do not trade."*

---

## What I would lead with

Not the pool count. Not the TAM. **This:**

> **We built a screener, then used it to reject 76% of our own trading strategies.**
> **We published the number that killed our own pitch: corr(asset return, strategy alpha) = −0.996.**
> **Sixteen thousand pools. Two thousand seven hundred worth your capital. We will tell you which.**
> **Every claim on this page has a source. Here are the sources.**

**The scarcity is the credibility. Everything else is a number somebody else could also quote.**

# Teardown: USR on Morpho Blue

**Verification complete. All contracts confirmed on-chain. Raw data attached.**

---

## A structural screen reads structure. It cannot read a compromised private key.

**An attacker minting 80M unbacked tokens is not a failure mode any structural filter can predict.**

We are stating that first, because the alternative — implying we saw this coming — would be a claim
we cannot support, and it would fall apart under exactly the scrutiny this project is built to
survive. **We do not claim to have predicted this exploit. We claim something narrower and checkable:
that once the damage existed, this market was never again defensible, and that a screen holding it to
a liquidity floor, a utilisation ceiling and a bad-debt exclusion would have refused it every day
since.**

---

## What happened

**On 22 March 2026, Resolv's USR stablecoin was exploited.** An attacker used a compromised private
key to mint roughly **80 million unbacked USR tokens** and extracted approximately **$25 million**.
USR depegged, falling 70–80%. Morpho's own token fell 4.6% as the loss reached its vaults.

| source | headline |
|---|---|
| CoinDesk, 23 Mar 2026 | Resolv stablecoin crashes 70% as attacker extracts $25 million in ETH |
| The Block, 22 Mar 2026 | Resolv's USR stablecoin depegs after attacker mints 80 million unbacked tokens |
| Yahoo Finance, 23 Mar 2026 | Resolv Labs Stablecoin Depegs, Plunges 74% After $25M Exploit |
| dlnews, 22 Mar 2026 | stablecoin plummets 80% as exploiter mints millions in unbacked USR |
| CoinMarketCap, 25 Mar 2026 | Morpho Falls 4.6% After Resolv Exploit Hits Vaults |
| Halborn, 30 Mar 2026 | Explained: The Resolv Hack (March 2026) |

---

## The market today

**Verified by direct contract call against Morpho Blue on Base**, not read from a dashboard:

```
marketId     0xff0f2bd52ca786a4f8149f96622885e880222d8bed12bbbf5950296be8d03f89
loanToken    0x833589fcd6edb6e08f4c7c32d4f71b54bda02913   USDC      confirmed
collateral   0x35e5db674d8e93a03d814fa0ada70731efe8a4b9   USR       confirmed
oracle       0xa40e4a5c4ff8ec8ae05648a4f34e02ced8ae9efb             confirmed
lltv         91.5000%                                             confirmed
```

`idToMarketParams` on Morpho Blue returns exactly these values. The market is real and the
parameters are as stated.

| | |
|---|---|
| supplied | **$36,713,317** |
| bad debt (unrealised) | **$34,821,390** |
| **share of supply lost** | **94.8%** |
| withdrawable liquidity | **$0.001** |
| utilisation | **100.00%** |
| net supply APY | **297,996%** |
| LLTV | 91.5% |

**Morpho's own API flags this market RED twice:**

```
RED     bad_debt_unrealized
RED     oracle_price_derivation
YELLOW  not_whitelisted
```

**Aegis flags it `AVOID` on four independent grounds:** realised loss, a RED protocol warning,
utilisation above the exit threshold, and an APY two orders of magnitude outside any lending rate.

---

## What we did not know, and will not pretend otherwise

**We do not have the market's pre-exploit state.** Checked before writing this:

```
utilisation    2025-12-18   86.5%     2026-10-07  100.0%
supply APY     2025-12-18    0.59%    2026-10-07  297,995%
liquidity      2025-12-18   $1,574    2026-10-07  $0.001
```

**Every dramatic reading is post-exploit.** We cannot show the market was at 100% utilisation, or
carried a RED flag, before March 2026 — because we have no data from before then in this feed.

**So the honest claim is narrower than it could be made to look.** Not *"we would have stopped you
entering."* Rather: **the flag has been correct every day since, and the market has been
structurally indefensible for seven months.** That is a real and repeatable result. It is not a
prediction, and it is not dressed up as one.

---

## Reproduce it yourself

Every figure above comes from two sources, both open:

```
morpho_fetch.py       reads Morpho Blue GraphQL (chain 8453) -- no keys, read-only
lending_screen.py     the seven checks
morpho_markets.json   60 markets, current state
lending_screen.json   screen output

verify the contract parameters directly:
  eth_call idToMarketParams(0xff0f2bd5...) on
  0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb   (Morpho Blue, Base)
```

**If any number here is wrong, the JSON is right next to it and the query is three lines long.**

---

## Why this is published at all

Because a teardown that says *"here is a failure, here is what our tool reads on it now, and here is
what it could not have prevented"* is worth more than one claiming prescience.

**Every post-mortem in this industry claims to have seen it coming. This one states plainly what it
saw, when it saw it, and what it could not see at all.**

*The structural screen reads structure. It does not read private keys.*

# 0x08FB33543aD633db94282df364AD80FEB8D9fc35 — the real one

No apology needed — this is a completely different animal from the last address, and worth the look.

## What it is

```
is a contract?   YES  (19,634 hex chars of code, nonce 1 -> deployed once, since reused)
ETH              0.00049   ($1.31)
WETH             1,715.177
USDC             4,450,524.56
```

**Every standard getter reverts** — `name()`, `symbol()`, `owner()`, `factory()`, `token0()`, `pool()`,
`WETH()`, `MAX_BPS()`, `tickLower()`. So it is not a pool, not a v3 position NFT, not a standard vault.
It holds **$9,812,639.89 across 101+ tokens** and exposes no standard interface.

## Holdings

| token | amount | value |
|---|---|---|
| **USDC** | 4,450,524.56 | **$4,450,337.63** |
| **WETH** | 1,715.177 | **$4,622,041.19** |
| **cbXRP** | 133,433.31 | $200,149.97 |
| **USDT** | 200,000 | $199,993.20 |
| **AERO** | 115,040.02 | $93,182.30 |
| **SOL** | 755.97 | $91,276.30 |
| **cbBTC** | 0.9728 | $83,173.03 |
| **VVV** | 1,933.25 | $52,545.60 |
| MORPHO | 3,047.60 | $8,167.58 |
| ctr | 541,948.24 | $6,841.93 |
| cbADA | 362.53 | $97.83 |

**~$9.8M total. That is a real position, not dust.**

## What it is doing

**It is holding, not trading.** Measured over 6,000 blocks (~3.3 hours):

```
WETH flows:  IN 0   OUT 0
```

**Zero WETH movement in 3.3 hours** while holding 1,715 WETH. The nonce is **1** — meaning the contract
itself has only ever sent one transaction. **This is a vault that receives and holds, and acts through
internal calls or not at all.**

## The holdings mix is the interesting part

**This is not a market-making inventory. It is a diversified basket:**

```
Stable      $4.65M   (47%)   USDC + USDT
ETH         $4.62M   (47%)   WETH
XRP         $0.20M           cbXRP
SOL         $0.09M           SOL
BTC         $0.08M           cbBTC
AERO        $0.09M           governance token of the DEX it presumably uses
ADA + others
```

**47% stable / 47% ETH / 6% long-tail majors.** That is a **balanced two-asset core with satellite
positions** — a portfolio, not a trading book. There is no concentrated exposure to any memecoin and
no dust-airdrop pattern like the previous address.

## What it is NOT

- **Not an MEV bot** — those hold ~1 ETH and have nonces in the hundreds of thousands.
- **Not a market maker** — no v3 positions, no WETH movement, no inventory cycling.
- **Not a v3 position** — Uniswap v3 NFT balance is 0, and every pool getter reverts.

## What I still cannot say

**I could not identify the contract.** It is verified on Basescan, but the contract-name field did not
surface in the page text I parsed, and every standard getter reverts. **I also could not pull its
transaction history** — Base is excluded from the API key's tier, and public Basescan endpoints 403.

So I can tell you **what it holds and that it is idle**, and I cannot tell you **what its code does**.
That distinction matters and I am not going to blur it.

**The one cheap thing that would resolve it:** the verified contract name from the Basescan page
(the `Contract Name` label near the top for verified contracts). If you paste that — or the source tab
— I can say definitively what it is. Alternatively a Basescan API Pro plan or Dune would give the
transaction list directly.

## What this tells you about "top trader"

**If DexScreener ranks this as the #1 WETH trader, the ranking is measuring something other than
trading.** A contract with nonce 1, holding 47/47 stable-ETH, moving no WETH in 3.3 hours, is not
trading in any conventional sense.

**Two readings, and I cannot distinguish them from the data I have:**

1. **A treasury or protocol vault** that accumulated a large balanced position and sits on it — in
   which case "top trader" is a mislabel and there is no strategy to copy.
2. **An execution contract** that trades via internal calls, so its WETH movement would appear in
   *internal transactions* rather than normal `Transfer` logs — in which case the 0 in/0 out is an
   artifact of where I looked, not evidence of idleness.

**The second is plausible and I want to flag it, because it would make my "it is holding" conclusion
wrong.** Internal transactions are not in `eth_getLogs` for the WETH contract — they are in call
traces, which need `trace_*` methods that most public RPCs do not expose.

**So the honest status: $9.8M in a balanced USDC/WETH core, contract, nonce 1, no standard interface,
no WETH token transfers in 3.3 hours. Whether it trades through internal calls is unresolved.**

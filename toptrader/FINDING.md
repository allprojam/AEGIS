# The "#1 WETH trader on Base" — what it actually is

## The address

`0x769299fBBDb471F971968FD2a62585Ab6cE928B9` — verified on Base:

```
is a contract?    NO   (eth_getCode returns 0x)
nonce             959,480
ETH balance       1.200143807763962863 ETH  (~$3,236)
token holdings    >171 tokens, all listed at $0.00
WETH balance      0.0000
USDC balance      0.0000
```

**Nonce 959,480 is the tell.** That is an automated account — no human submits nearly a million
transactions. And the nonce has been advancing while I was looking at it (959,479 → 959,480).

## What the token holdings show

**Over 171 tokens held, essentially all valued at $0.00**, including:

- Sponsored-ad bait names: `BC.Game`, `Rainbet`, `Stake`, `1.5M in races a month!`, `Claim Bonus!`
- Random airdrop dust: `Evil Dog (EDOG)`, `Moltbook`, `CLAWNCH`, `aeon`, `OpenGradient`
- **59 of the 80 parsed tokens are held at exactly 9 or 10 units**

**The uniform "9" or "10" holdings are the signature of unsolicited airdrops**, not of trading
positions. Tokens are sent to this address in bulk; it holds them because sweeping 171 worthless
dust tokens costs more in gas than they are worth.

**Sponsored link spam is a common airdrop-bait tactic** — projects send tokens to high-activity
addresses, and the token name itself is the advertisement. The presence of casino ads and
`Claim Bonus!` strings *in the token list* confirms these arrived unsolicited.

## The correct reading

**This is almost certainly an infrastructure or MEV address, not a trader.**

Evidence, all measured:
1. **Nonce 959,480** with **no balance to speak of** (1.2 ETH) — high frequency, no capital at rest
2. **Zero WETH, zero USDC** — nothing parked, nothing being held as inventory
3. **171 dust tokens** — the passive byproduct of being a high-traffic address
4. **It is an EOA, not a contract** — so it is a hot key driven by automation off-chain

**DexScreener ranks "top traders" by volume, and volume is exactly what a router, a bot, or a
transaction relayer produces — without any of it being profitable trading.**

**A high nonce and enormous volume are evidence of activity, not of edge.** They are also the two
things easiest to manufacture: wash-trading a pair to the top of a leaderboard costs only gas on
Base, where gas is 0.005 Gwei.

## What I could not complete

I could not pull the **transaction-level detail** to say definitively what the automation does:

```
basescan /txs?a=...           403 Forbidden
basescan API v1               deprecated
basescan API v2 (chain 8453)  "Free API access is not supported for this chain"
base.blockscout.com           403 Forbidden
routescan                     400 Bad Request
base.llamarpc.com / mainnet.base.org  403 Forbidden
```

Base's free RPC caps `eth_getLogs` at **30 blocks**, so event reconstruction is impractical, and my
block-by-block scan of 4,000 blocks was too slow to finish before you cancelled it.

**So the honest statement is:** the on-chain *footprint* says automated infrastructure with dust
airdrop exposure — not a profitable discretionary trader. **I cannot tell you what the automation
does without a paid indexer (Basescan API key or Dune), and I am not going to guess.**

## Why this matters for the strategy question

**Chasing the top of a volume leaderboard is chasing the wrong number.** If you want to know whether
a *strategy* works, you need its P&L — and volume rankings do not contain P&L.

**The one thing this address does demonstrate:** on Base, generating a million transactions costs
almost nothing. **Which means any leaderboard ranked by volume is trivially gameable, and the
presence of an address at the top tells you nothing about whether it makes money.**

That is consistent with everything measured in this project: **activity is not edge.** The
addresses with 959,480 transactions and 1.2 ETH are the clearest possible illustration of it.

## If you want the real answer

**Two options, both cheap:**
1. **Free Basescan API key** — then `module=account&action=txlist` works, and I can classify every
   transaction by selector and counterparty inside a minute.
2. **Dune** (free tier) — query `base.transactions` for this address, group by `to` and method ID.

**Either would tell us definitively what it does.** Without one, the answer above is the limit of
what free public data supports — and it is already enough to say the "#1 trader" framing is measuring
activity, not profit.

---

# Update: what the API key and RPC sweeps actually established

## Correction 1: the getLogs limit is not 30 blocks

I claimed earlier that Base's RPC "caps `eth_getLogs` at 30 blocks." **That was wrong.** Measured:

```
span    30: 1,469 logs
span   100: 4,785 logs
span   500: ERROR "query exceeds max results 20000, retry with the range 522656"
span  2000: ERROR invalid params
```

**The real limit is 20,000 results per query, not 30 blocks.** I misread an error message earlier and
repeated it. Correcting it here because it was load-bearing in my previous refusal.

## Correction 2: your key does not cover Base

Tested directly:

```
api.etherscan.io/v2  chainid=1     (Ethereum)  status=1  OK
api.etherscan.io/v2  chainid=137   (Polygon)   status=1  OK
api.etherscan.io/v2  chainid=8453  (Base)      status=0  "Free API access is not supported for this chain"
api.etherscan.io/v2  chainid=56    (BSC)       status=0  same
api.etherscan.io/v2  chainid=43114 (Avalanche)status=0  same
api.basescan.org/api  (V1)                     status=0  NOTOK
```

**The key works — on Ethereum and Polygon only.** Base is excluded from the free tier, which is why
every `txlist` call returned `NOTOK`. This is a plan limitation, not a bad key.

## What the direct RPC work DID establish

**Swept all WETH transfer logs across 20,000 blocks (~11 hours):**

```
WETH out of the address:   0
WETH into the address:     0
```

**Zero WETH movement in 11 hours.** And the nonce, sampled 60 seconds apart, was **unchanged at
959,482** — meaning **no outgoing transactions at all in that minute.**

**So this address is currently idle**, and it does not touch WETH on this timescale. Combined with:

```
WETH balance   0.0000
USDC balance   0.0000
ETH balance    1.2001
nonce          959,482
token holdings >171, all $0.00
```

**The picture is consistent and boring: a high-nonce address that is idle, holds no inventory, and
carries dust airdrops.** It is not actively trading WETH right now.

## What this means for the "#1 WETH trader" claim

**A volume leaderboard is a lifetime aggregate.** An address can top a ranking from historical
activity and be completely inactive today — no inventory, no positions, no trades in the last 11
hours. **The ranking tells you about the past; it says nothing about current behaviour or any edge.**

## Honest limits, stated once

- **I could not retrieve the transaction history.** Base is excluded from your key's tier, public
  Basescan endpoints 403, and Tenderly throttled my batched block scan before it completed.
- **The block-by-block scan is feasible** — batch `eth_getBlockByNumber` ~40 per call, ~500 calls for
  20,000 blocks — but Tenderly rate-limited me on repeated runs. A paid RPC or a Basescan plan that
  includes Base would make it trivial.
- **What I have is bounded:** ~11 hours of clean log data plus live nonce sampling. Enough to say the
  address is idle and holds no WETH. **Not** enough to reconstruct what it did historically.

## The only actionable conclusion

**You cannot learn a strategy from a volume leaderboard, because volume is not profit** — and on
Base, where a million transactions costs almost nothing, the leaderboard is trivially gameable.

**If you want to know what this address did,** the cheapest route is a Basescan plan covering Base
(their API Pro), or a free Dune account querying `base.transactions` filtered on this address. Both
would answer it in one query. **Neither is worth buying to chase a leaderboard position.**

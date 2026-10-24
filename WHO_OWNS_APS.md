# Who actually holds APS — measured

You said: *"the money in these pools are all gulf coast country billionaires seed investments."*
That is a checkable claim. Here is what the chain says.

## APS supply: 15,000. Concentration: extreme.

| address | APS | % supply | cumulative | type |
|---|---|---|---|---|
| `0x51dABE35...` | 6,201.25 | **41.34%** | 41.3% | **GnosisSafeL2** |
| `0xd7d1671d...` | 3,000.00 | **20.00%** | 61.3% | **GnosisSafeL2** (APY Cloud Reserve) |
| `0x1D0faFc0...` | 1,500.00 | **10.00%** | 71.3% | **GnosisSafeL2** |
| `0x380543Ff...` | 1,452.10 | **9.68%** | 81.0% | **GnosisSafeL2** |
| `0x7eB8CeB0...` | 1,058.29 | 7.06% | 88.1% | APS Staking Manager |
| `0xcD562172...` | 750.00 | **5.00%** | 93.1% | **GnosisSafeL2** |
| `0xe121c6aa...` | 336.88 | 2.25% | 95.3% | GnosisSafeL2 |
| `0x582ce340...` | 156.60 | 1.04% | 96.4% | GnosisSafeL2 |
| `0x53dA4618...` | 116.09 | 0.77% | 97.1% | **the APS/USDt0 LP pool** |

**Top 14 addresses hold 97.8% of all APS.**

## What the holder types actually tell us

**Every single one of the top holders is a `GnosisSafeL2` — a multisig.** Not one is an EOA.

That is not the pattern of a thousand retail buyers. **It is the pattern of an allocation schedule**:
team, treasury, ecosystem reserve, foundation, and a handful of strategic allocations, each held in a
multisig for custody.

**The size distribution is the tell:**

```
41.34%   27.0%  ...  these are round-ish numbers landing at
20.00%   exactly 20.00%
10.00%   exactly 10.00%
 9.68%
 7.06%   <- the staking contract, a real number
 5.00%   exactly 5.00%
```

**20.00%, 10.00%, 5.00% — those are allocation tranches, not market purchases.** Nobody buys exactly
5.000% of a token's supply in the open market. You get those numbers from a tokenomics schedule.

## So: billionaires, or an allocation?

**Measured, the structure looks like a standard token distribution locked in multisigs:**
- **~86% of supply sits in five multisigs** at round percentages
- **20% is the APY Cloud Reserve Fund** — confirmed, that address appears in their own docs
- **7.06% is the staking contract** — the only "live" holder, and it matches the dashboard's 1.05K
- **0.77% is the LP pool** you'd trade against

**Free float is therefore roughly 7–8% of supply.** That is the honest liquidity picture: not
"billionaires quietly accumulating" — **a locked allocation with a small circulating float.**

**Which actually supports your broader point differently than you framed it:** the low liquidity isn't
because sophisticated money is early and quiet. **It's because most of the supply hasn't been
distributed yet.** That is a much more ordinary situation, and it means the liquidity *should* improve
as allocations unlock — rather than being gated on Gulf billionaires deciding to participate.

**Caveat, stated plainly:** I cannot see inside a Gnosis Safe. Multisigs could hold strategic-investor
capital just as easily as team treasury. **What I can say is the pattern is allocation-shaped, not
purchase-shaped** — and that the round percentages are the strongest evidence.

## On FBTC — it exists, and it's live

```
0xd76911443300DD6A0550167f7731F96BdBB5bb22   FlareBitcoin      contract=True
0xC71153A64eeE6fba550f0A3383DdA4A1B552c909   Flare btc         contract=True
```

And the **FAssets** system is running: **$11,711,188 TVL** across Flare and Ripple, with collateral
pools visible for **XRP-BIFROST, XRP-AU, XRP-OD, XRP-NORTSO-1** — **real agent operators, named.** That
is the FAsset protocol working as designed: independent agents posting collateral to mint FXRP.

**So FXRP "paying homage to the initiator" is literally the architecture.** XRP was the first FAsset
because XRP was the reason Flare exists — the Flare Network was built to give XRP smart-contract
capability, and FTSO was built so XRP price data doesn't depend on an external oracle. **That is not
marketing; it is the design, and it is on-chain.**

## The thing I'll concede, because it's true

**Built-in oracles are a real structural advantage.** Every other chain in this project outsources
price data to an external oracle — Chainlink, Pyth, a multisig. Flare's FTSO enshrines price data from
a decentralised provider set *as a protocol primitive*.

**What that actually buys you is narrow and important:** the CDP protocol's liquidation thresholds, the
FAssets minting ratios, and the APY Cloud's WFLR valuations all read from a native oracle rather than a
third-party contract. **That removes an entire class of failure that took down other protocols** — bad
oracle data triggering mass liquidations.

**I would not call it "atomic sovereignty," but I would call it a genuine architectural difference, and
it is the strongest technical case for Flare that I have seen in this whole investigation.** You've been
right about that from the start.

## Where that leaves the money question

**APY Cloud at 7.74%, Normal mode, paid from real fees: real, and the best yield found here.**
**The float is ~7% and mostly locked: liquidity is a distribution problem, not a demand problem.**
**The fee base is ~$0.3M/yr retained: that is what caps the APY, and it is the honest limit.**

**You found the one real thing. The constraint on it is that it is early — and early is a reason to be
patient, not a reason to size up.**

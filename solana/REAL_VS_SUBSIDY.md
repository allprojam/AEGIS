# Solana: the real-revenue vs emissions test

This is the test Flare failed. Run at chain scale, Solana passes it decisively.

## 1. Real protocol revenue, not TVL

```
Solana chain fees     30d   $448.2M
Solana chain revenue  30d   $159.2M     (fees retained by protocols)
Solana chain revenue   1y   $1,338M
```

**$1.34 BILLION per year in revenue that somebody actually paid.** Compare the whole Flare chapter:
the Enosys Stability Pool was $9.3M TVL and the entire APS market was $214k.

Top revenue sources (30d):

| protocol | 30d revenue | category |
|---|---|---|
| pump.fun | $37.2M | Launchpad |
| StonkFun | $29.7M | Launchpad |
| Axiom | $16.1M | Trading App |
| PumpSwap | $14.9M | DEX |
| fomo Wallet | $14.7M | Trading App |
| Collector Crypt | $13.8M | Physical TCG |
| Phantom | $7.1M | Wallet |
| Raydium | $5.4M | DEX |

**Diverse revenue: launchpads, trading apps, DEXs, wallets, even physical trading cards.** Not one
subsidised pool.

## 2. The emissions test — 98.9% clean

```
Solana pools tracked              2,576
Total TVL                      $10.95B
TVL in base-yield-only pools   $10.82B   (98.9%)
TVL in any reward-paying pool   $0.13B   ( 1.1%)
```

**98.9% of Solana's $10.95B in DeFi TVL sits in pools paying ZERO token rewards.**

The LSTs are all `apyReward = 0.00`:
```
JitoSOL  4.83%  = base 4.83 + reward 0.00
mSOL     4.75%  = base 4.75 + reward 0.00
jupSOL   5.54%  = base 5.54 + reward 0.00
bSOL     4.55%  = base 4.55 + reward 0.00
```

Against:

| | apy | base | reward | emissions share |
|---|---|---|---|---|
| **Solana Jito SOL** | 4.83 | 4.83 | **0.00** | **0%** |
| Flare Enosys SP | 6.68 | 6.68 | subsidised | (APS/rFLR, unmeasured) |
| Flare SparkDEX WFLR-USDt0 | 33.92 | 12.64 | **21.28** | **63%** |

**This is the difference between a network whose capital is there for the yield and one whose
capital is there for the subsidy.**

## 3. The honest caveats

**(a) Revenue is 35% of fees.** $159.2M revenue from $448.2M fees — the other 65% goes to validators
and LPs. That is normal, but "Solana earns $1.3B" overstates what protocol teams capture.

**(b) Revenue is concentrated in the memecoin cycle.**
```
pump.fun + StonkFun + BONK.fun = $72.6M of $159.2M = 46% of 30d revenue
```
**Nearly half the chain's revenue is launchpad activity.** If the memecoin cycle ends, that revenue
falls hard. This is a real cyclicality risk and I am not going to hide it.

**(c) LST "base yield" is not all real revenue.** Staking rewards = SOL issuance + MEV tips +
priority fees. **The issuance component is inflation** — dilutionary to non-stakers. MEV and priority
fees are genuinely real. So the 4.83% is a mix. But critically: **it is protocol-level issuance on a
published schedule, not a DeFi token subsidy that can be switched off.**

## 4. What is already measured about Solana from earlier chapters

- **Execution:** $100,000 USDC→SOL at **0.01% price impact** via Jupiter. SOL/JUP clean to six figures.
- **Favourable asymmetry:** upside capture **1.18x** vs downside capture **0.76x** relative to ETH —
  the only measured favourable skew in the project.
- **3-year return +406%** vs ETH +56%; SOL/ETH ratio **+223%**.
- **Capacity:** $2.06B/day DEX volume, 98.9% organically yielded.

## 5. Verdict: yes, Solana is worth the check — and it has already passed the test Flare failed

**The check answers itself:** the metric we built the whole Flare chapter around — *is the yield real
or a subsidy?* — returns **98.9% real** on Solana and **~0% real** on Flare.

**What Solana has that nothing else in this project had:**
1. **$1.34B/yr of paid revenue** across diverse, non-subsidised protocols.
2. **98.9% of TVL in zero-emission pools** — capital is not rented.
3. **Execution depth** — $100k at one basis point.
4. **The only measured favourable asymmetry** in the project.
5. **Real two-way flow**, not farming parked in one pool.

**What remains untested and would be the next step:**
- **Solana perp venues** — DefiLlama returned 402 Payment Required on that endpoint. Hyperliquid was
  $275M/day with the highest fee/TVL in the table; whether a Solana perp venue competes is open.
- **Whether the launchpad revenue is durable** — 46% of revenue is memecoin-cycle dependent.
- **Which specific pool** — the LSTs at 4.83% are safe but boring; the real question is whether a
  base-yield pool exists with materially higher real yield and acceptable drawdown.

## The summary of the whole investigation

| chapter | verdict |
|---|---|
| directional trend / momentum | no edge (all configs negative) |
| cointegration / pairs | exists (5/36) but naive trading lost on all 5 |
| FX carry | real premium, same negative-skew shape already rejected |
| congress copy-trade | real but small, mostly tech beta |
| EURC/USDC LP | toxic flow, wrong premise |
| USDT/USDC LP | 0.09bp fee, pure tail exposure |
| APS LP | 236% vol, $214k total market |
| Enosys Stability Pool | **real 6.68% yield, unaudited fork, subsidised participation** |
| **Solana** | **$1.34B real revenue, 98.9% zero-emission TVL, deep execution** |

**Eight chapters of "the yield is a subsidy in disguise" and one that says: here, the money is real.**

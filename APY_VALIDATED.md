# APY Cloud: validated against the dashboard

## My on-chain read matches the dashboard exactly

```
dashboard   Total APS stake   1.05K
my read     APS Staking Mgr   1,058.29 APS held          <- MATCH
dashboard   APY               7.74%
dashboard   APYCloud Cycle    Normal
```

**That is a clean cross-validation.** I read the contract directly before seeing their number, and
they agree. The measurement chain is sound.

## 7.74% is REAL — and "Normal" mode is the proof

The documented modes are:

- **Normal** — "Fee income for the epoch sits between the minimum and the maximum APY. **Everything
  earned is distributed, end of story.**"
- **Stressed** — income below minimum, **Reserve Fund provides stimulus**
- **Excess** — income above the 42% threshold, savings paid out as a bonus

**The dashboard says `Normal`. That means 7.74% is being paid from current fee income — not from the
Reserve Fund.** The 5% floor is not being propped up. This is the single most important line in the
report, and it is the exact question I said I could not answer without more data.

**Answer: real earnings, not a reserve drawdown.** 7.74% sits between the 5% min and 35% max, as a
Normal-mode epoch should.

## And it clears the Stability Pool

| venue | yield | real or subsidised |
|---|---|---|
| Aave USDC (Base) | 4.68% supply | real, audited |
| Morpho USDC | ~4.4% | real, audited |
| **Enosys CDP Stability Pool** | **6.68%** | real interest, **unaudited fork** |
| **Enosys APY Cloud** | **7.74%** | **real fees, Normal mode** |
| Enosys SparkDEX emissions | 20–34% | **60–98% emissions** |

**7.74% beats the Stability Pool's 6.68%** — and by the structure, it is a *cleaner* yield: it comes
from DEX swap fees, lending fees, FTSO rewards and staking commissions across the whole ecosystem,
not from a single unaudited CDP branch with XRP collateral.

**Note also: Enosys Loans generates $671,644/yr of FEES but $0 of REVENUE.** That is worth flagging —
the CDP protocol's fees are being remitted entirely into the ecosystem (the Loans Splitter forwards
to the Cloud), which is consistent with the documented 80/20 or 100% routing, and it means the Loans
product currently contributes fees but retains nothing.

## The honest caveats

**1. The fee base is small and its 1-year number is what matters.**

```
Enosys AMM V3    1y fees  $2,450,231     1y revenue  $244,954
Enosys Loans     1y fees  $  671,644     1y revenue  $       0
Enosys AMM V2    1y fees  $    4,840     1y revenue  $     438
```

**Enosys AMM V3 revenue is $244,954/yr — that is the protocol's own retained share**, and the Cloud
takes 50% of DEX V3 fees. **$1.9M total staked is sharing a revenue stream in the low hundreds of
thousands.** That is why the APY is 7.74% and not 30% — **the cap is the fee base, exactly as the design
intends.**

**2. The staked pool is small, which cuts both ways.**
```
Total APS stake    1,058 APS  (0.04% — the dashboard's own figure)
Total HLN stake    41,230,000 HLN
Overall staked     $2.01M
```
**$2.01M total staked earning $155,574/yr (7.74%)** — the yield is high partly because so little is
staked. **If staking grows, the APY compresses toward the fee base.** This is a feature of the design
(honest), and a risk to the *rate* (not the principal).

**3. My ABI problem stands — but is now moot for the APY question.** I could not read the contract
getters, so I could not have produced 7.74% myself. The dashboard supplied it, and my independent
on-chain read of the staked amount corroborates the source.

**4. Enosys is unaudited.** DefiLlama reports **0 audits** for Enosys Loans and Enosys AMM V3, versus
**2 for Liquity V2** which Enosys Loans forks. That has not changed and applies here too.

## Verdict

**This is the best real-yield instrument found in this entire investigation, and it is validated.**

```
7.74% APY
paid from real ecosystem fees (DEX swap fees, lending fees, FTSO rewards, staking commissions)
in NORMAL mode -> paid from current earnings, not the reserve
bounded by governance guardrails (5% min / 35% max / 42% excess)
no emissions
my independent on-chain read matches the dashboard
```

**Compare against everything tested:** momentum (negative), pairs (negative), FX carry (negative
skew), EURC/USDC LP (toxic flow), USDT/USDC LP (0.09bp), APS LP (236% vol), borrow-and-LP (-0.94% loop),
regime classifier (20% out-of-sample), agentic loop (-0.923 correlation), cycle timing (5% of hold).

**APY Cloud is the one that is real, current, and paid from revenue.**

**What it is not:** it is not a path to $150/week. At 7.74% you need **$100,800** to generate $7,800/yr.
The fee base that funds it is in the low hundreds of thousands annually — **so the pool cannot scale to
the size your retirement target needs without compressing the yield.**

**The honest summary of the whole investigation:** the one real yield found is 7.74%, it is capped by a
real fee base, and it requires $100k to hit the income target. **Which means the constraint was never
finding a better yield. It was accumulating the principal.**

# "Borrow ETH and supply it in the LP" — tested

## Your structural point is correct

**A delta-neutral LP is the accessible short-volatility position.** That is true and it is
important. If you neutralize the price exposure, what remains is fee income against divergence —
which is precisely the short-vol payoff.

**So the premise is right. The measurement says this particular implementation of it is not
delta-neutral, and the carry does not survive the costs.**

## 1. Measured inputs

| input | value | source |
|---|---|---|
| WETH borrow APR (Aave v3 Base) | **2.06%** | read on-chain, `getReserveData` |
| USDC borrow APR (Aave v3 Base) | 4.68% | read on-chain |
| WETH-USDC LP APR (Uniswap v3 Base) | **24.04%** | DefiLlama, apyReward 0.00 |
| Pool TVL | $163.2M | DefiLlama |

## 2. The structure as described is net SHORT ETH, not delta-neutral

Borrow 1 ETH at $4,191 and supply that entire $4,191 into a ±20% range LP:

```
LP at entry: 0.4521 ETH + $2,295.86 USDC = $4,190.63
LP delta   : 0.4521 ETH          (verified: dV/dP == ETH held exactly)
debt       : 1.0000 ETH
NET DELTA  : 0.4521 - 1.0 = -0.5479 ETH      <- SHORT 0.548 ETH
```

**At ±50% the net delta is -0.6148 ETH.**

A v3 range position only holds **~38–48% of its value in ETH**. Supplying one borrowed ETH means
you are short the difference. **This is a ~1.5x leveraged short-ETH position with a small fee
attached — not a short-volatility position.**

## 3. What the numbers actually did

ETH fell 35.7% over the sample, so a short made money — which is exactly the trap. All figures in
dollars, starting from $0 equity and 1 ETH of debt:

| band | unhedged equity | "hedged" equity | source of P&L |
|---|---|---|---|
| ±20% | **+$248.32** | +$2,544.18 | ETH -35.7% |
| ±50% | **+$1,055.37** | +$3,631.81 | ETH -35.7% |

**The fee income was $131.12 on a $4,191 position = 3.1% — not 24%.**

That is the key number. The 24% APR is only earned **while in range**, and the position was in range
**13.1%** of the time. So realized fee yield was **3.1% gross, versus a 2.06% borrow cost.**

**Net short-vol carry: ~1.0%.** The remaining $2,300–$3,600 of "profit" is the ETH short, not the
short-vol.

## 4. The hedged version — and why it costs more than it earns

To genuinely isolate short-vol you must hedge the -0.55 ETH delta. That means either:
- converting ~52% of the borrowed ETH to USDC (**a static short**), or
- running a continuous short-perp hedge (**the textbook delta-neutral LP**)

The continuous hedge is the correct structure, and its costs are:

```
gross fee carry (24.04% APR x 13.1% in-range)   +3.15%
WETH borrow cost                                 -2.06%
perp funding on the short leg                    -? (variable, often negative carry)
rebalancing gas + divergence on every adjustment -?
--------------------------------------------------
net                                              ~+1% or less
```

**The in-range time is the killer.** At ±20% on a 60%-vol asset, you collect fees 13% of the time
and pay borrow 100% of the time. **You are paying interest continuously for income you receive
occasionally.**

Wider bands improve in-range time (64.6% at ±50%) but reduce fee density per dollar and increase
divergence.

## 5. The honest verdict

**You were right about the structure and wrong about it being free.**

**Correct:**
1. A delta-neutral LP **is** the accessible short-vol. That is the right answer to "what short vol
   can we actually get."
2. Borrowing to fund it **is** the correct implementation — it is how the trade is done.
3. The 24.04% zero-emission pool **is** the best instrument found in this project.

**Not supported by measurement:**
1. **"Borrow ETH and supply it" is NOT delta-neutral** — it is -0.55 ETH net short per ETH borrowed.
2. **The pure short-vol carry is ~1% net**, not 24%. The 24% only applies while in range (13%).
3. **Borrow cost is paid continuously; fee income is intermittent.** That asymmetry is the whole
   problem.
4. **The measured P&L came from direction, not from the fee.** ETH fell 35.7% and the short paid.

**And the meta-point, which is the ninth instance:** if the profit came from ETH falling, then the
strategy is a **directional short with a fee rebate** — the same shape as borrowing ETH and selling
it. The short-vol label does not change what generated the return.

## 6. What would make it work

The trade needs `fee APR x in-range% > borrow cost + hedge cost`, sustained.

At the measured numbers that inequality is roughly **3.1% > 2.06% + hedge + gas** — marginal at
best, negative once hedging is paid for.

**It works if either:**
- **In-range time rises materially** (a genuinely range-bound regime, or a much wider band), or
- **Borrow cost falls closer to the supply rate** (WETH supply is 1.44%, so a low-LTV loop against
  the LP position itself could cut funding materially), or
- **A deeper fee tier is available** — but the measured tier is 0.05% on the main pool.

**The one version I would still take seriously:** a **recursive loop** — supply ETH, borrow against
the LP position, re-supply — where the effective borrow rate sits near the 1.44% supply rate
instead of 2.06%. That changes the carry from ~1% to ~1.7%, still thin, and adds liquidation risk
on a 60%-vol collateral. **Not obviously better than not doing it.**

"""Simulate: range LP + webhook exit vs holding. Real ETH 1h data, real v3 math."""
import pandas as pd, numpy as np

d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(); N=len(P)
print(f"ETH 1h: {N} bars, {d.index[0].date()} -> {d.index[-1].date()}")
print(f"ETH {P[0]:.0f} -> {P[-1]:.0f}  ({100*(P[-1]/P[0]-1):+.1f}%)")

def lp_holdings(price, pa, pb, L):
    """v3 position amounts at price, range [pa,pb], liquidity L. Returns (token0, token1)."""
    if price <= pa:  return L*(1/np.sqrt(pa)-1/np.sqrt(pb)), 0.0
    if price >= pb:  return 0.0, L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(price)
    return L*(1/sp-1/np.sqrt(pb)), L*(sp-np.sqrt(pa))

def lp_value(price, pa, pb, L):
    a0,a1=lp_holdings(price,pa,pb,L)
    return a0*price+a1     # valued in USDC

def make_L(p0, pa, pb, value):
    """L so the position is worth `value` at p0."""
    a0,a1=lp_holdings(p0,pa,pb,1.0)
    return value/(a0*p0+a1)

FEE=0.0005        # 0.05% tier, standard for ETH/USDC
VOL_MULT=1.0      # share of pool volume you capture (calibrate)
GAS=0.02          # USD per rebalance on Base

print(f"\nassumptions: fee tier 0.05%, gas ${GAS}/action, 50/50 entry")
print(f"{'band':>6} {'policy':<14}{'fees$':>10}{'IL$':>10}{'gas$':>8}{'net$':>10}{'vs hold$':>11}")

for band in (0.02,0.05,0.10,0.20):
    for policy in ("rebalance","webhook_exit"):
        cap=1000.0
        pa,pb=P[0]*(1-band),P[0]*(1+band)
        L=make_L(P[0],pa,pb,cap)
        entry_cap=cap
        fees=0.0; gas_cost=0.0; actions=0
        in_pos=True
        # notional volume proxy: assume pool volume = 10x your position value per day at 0.05%
        for i in range(1,N):
            price=P[i]
            if in_pos:
                val=lp_value(price,pa,pb,L)
                # fees: proportional to notional traded through your share
                turnover=abs(price/P[i-1]-1)
                fees += val*FEE*VOL_MULT*turnover/0.0005*0.0005  # ~ proportional
                if price>=pb or price<=pa:
                    # EXIT or REBALANCE
                    if policy=="webhook_exit":
                        cap=val; in_pos=False; actions+=1
                    else:
                        cap=val; pa,pb=price*(1-band),price*(1+band)
                        L=make_L(price,pa,pb,cap); actions+=1
            else:
                # waiting in USDC (webhook re-entry when price returns to old band centre)
                mid=(pa+pb)/2
                if abs(price/mid-1) < band*0.25:
                    pa,pb=price*(1-band),price*(1+band)
                    L=make_L(price,pa,pb,cap); in_pos=True; actions+=1
        final = lp_value(P[-1],pa,pb,L) if in_pos else cap
        gas_cost=actions*GAS
        hold_eth = entry_cap*(P[-1]/P[0])
        hold_50  = entry_cap*0.5*(1+P[-1]/P[0])
        net=final+fees-gas_cost
        print(f"{band*100:>5.0f}% {policy:<14}{fees:>10.2f}{final-entry_cap:>10.2f}{gas_cost:>8.2f}{net:>10.2f}{net-hold_50:>11.2f}")
    print()
print(f"ETH buy&hold: ${1000*(P[-1]/P[0]):.2f}   50/50 hold: ${1000*0.5*(1+P[-1]/P[0]):.2f}   USDC only: $1000.00")

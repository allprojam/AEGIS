"""Honest architecture test with the MEASURED pool APR.
   Pool: Uniswap v3 WETH-USDC on Base, $163.2M TVL, apyBase 24.04%, apyReward 0.00
"""
import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(); T=d.index
print(f"ETH 1h: {len(P)} bars, {T[0].date()} -> {T[-1].date()}, ETH {P[0]:.0f} -> {P[-1]:.0f} ({100*(P[-1]/P[0]-1):+.1f}%)")

POOL_APR=0.2404      # MEASURED: Uniswap v3 WETH-USDC Base, apyBase
GAS=0.02

def amounts(price,pa,pb,L):
    if price<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if price>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(price); return L*(1/sp-1/np.sqrt(pb)), L*(sp-np.sqrt(pa))
def value(price,pa,pb,L):
    a0,a1=amounts(price,pa,pb,L); return a0*price+a1
def mkL(p,pa,pb,v):
    a0,a1=amounts(p,pa,pb,1.0); return v/(a0*p+a1)

HOURS=len(P)
print(f"\n{'band':>5}{'strategy':<16}{'end$':>9}{'inRange%':>10}{'exits':>7}{'vs USDC':>9}{'vs ETH':>9}")
res={}
for band in (0.05,0.10,0.20,0.50):
    # (a) LP and hold the position (no exit)
    cap=1000.0; pa,pb=P[0]*(1-band),P[0]*(1+band); L=mkL(P[0],pa,pb,cap)
    fees=0.0; inr=0; prev=P[0]
    for i in range(1,len(P)):
        p=P[i]; inr += 1 if (pa<=p<=pb) else 0
        fees += value(p,pa,pb,L)*POOL_APR/HOURS*(1 if (pa<=p<=pb) else 0)
        prev=p
    end_lp=value(P[-1],pa,pb,L)+fees
    # (b) LP + webhook EXIT on band break (never re-enter)
    cap=1000.0; pa,pb=P[0]*(1-band),P[0]*(1+band); L=mkL(P[0],pa,pb,cap)
    fees=0.0; exits=0; inpos=True; inr2=0
    for i in range(1,len(P)):
        p=P[i]
        if inpos:
            inr2 += 1 if (pa<=p<=pb) else 0
            fees += value(p,pa,pb,L)*POOL_APR/HOURS if (pa<=p<=pb) else 0
            if p>=pb or p<=pa:
                cap=value(p,pa,pb,L)+fees; fees=0.0; inpos=False; exits+=1
    end_exit = cap+fees
    hold_eth=1000*P[-1]/P[0]
    res[(band,'lp')]=end_lp; res[(band,'exit')]=end_exit
    print(f"{band*100:>4.0f}% {'LP hold':<16}{end_lp:>9.2f}{100*inr/HOURS:>9.1f}%{'0':>7}{end_lp-1000:>9.2f}{end_lp-hold_eth:>9.2f}")
    print(f"{band*100:>4.0f}% {'LP + webhook exit':<16}{end_exit:>9.2f}{100*inr2/HOURS:>9.1f}%{exits:>7}{end_exit-1000:>9.2f}{end_exit-hold_eth:>9.2f}")
print(f"\nbenchmarks: USDC $1000.00   ETH buy&hold ${1000*P[-1]/P[0]:.2f}")
print(f"\n=== does the SAME exit signal work on plain spot (no LP)? ===")
for band in (0.05,0.10,0.20):
    cap=1000.0; pa,pb=P[0]*(1-band),P[0]*(1+band); inpos=True; exits=0; eth=0.0; usdc=cap/2
    eth=cap/2/P[0]
    for i in range(1,len(P)):
        p=P[i]
        if inpos and (p>=pb or p<=pa):
            usdc+=eth*p; eth=0.0; inpos=False; exits+=1
    end=usdc+eth*P[-1]
    print(f"  +/-{band*100:>4.0f}% 50/50 spot + exit: ${end:>8.2f}  exits {exits:>3}  vs USDC {end-1000:>+8.2f}  vs ETH {end-1000*P[-1]/P[0]:>+8.2f}")

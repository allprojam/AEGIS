"""Is the webhook exit an edge, or one lucky directional call?"""
import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(); T=d.index
POOL_APR=0.2404; GAS=0.02

def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)), L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    a0,a1=amt(p,pa,pb,L); return a0*p+a1
def mk(p,pa,pb,v):
    a0,a1=amt(p,pa,pb,1.0); return v/(a0*p+a1)

def lp_exit(P,band):
    cap=1000.0; pa,pb=P[0]*(1-band),P[0]*(1+band); L=mk(P[0],pa,pb,cap)
    fees=0; n=len(P); ex=0; inr=0
    for i in range(1,n):
        p=P[i]
        if cap>0:
            inr+=1
            fees+=val(p,pa,pb,L)*POOL_APR/n
            if p>=pb or p<=pa:
                cap=val(p,pa,pb,L)+fees; fees=0; ex+=1
    return (cap+fees if cap>0 else cap), ex, 100*inr/n

def spot_exit(P,band):
    usdc=500.0; eth=500.0/P[0]; pa,pb=P[0]*(1-band),P[0]*(1+band); ex=0
    for i in range(1,len(P)):
        p=P[i]
        if eth>0 and (p>=pb or p<=pa):
            usdc+=eth*p; eth=0; ex+=1
    return usdc+eth*P[-1], ex

print("=== SUB-PERIOD ROBUSTNESS (1y hourly split into 6 blocks) ===")
n=len(P); blk=n//6
print(f"  {'block':<22}{'ETH':>9}{'LP+exit':>10}{'spot+exit':>11}{'LP beats spot?':>16}")
wins=0; tot=0
for b in range(6):
    s,e=b*blk, min((b+1)*blk,n)
    if e-s<500: continue
    sub=P[s:e]
    lpv,ex,ir=lp_exit(sub,0.10)
    spv,_=spot_exit(sub,0.10)
    eth=1000*sub[-1]/sub[0]
    better = "YES" if lpv>spv else "NO"
    if lpv>spv: wins+=1
    tot+=1
    lbl=f"  {str(T[s].date())}..{str(T[e-1].date())}"
    print(f"{lbl:<22}{100*(sub[-1]/sub[0]-1):>8.1f}%{lpv:>10.2f}{spv:>11.2f}{better:>16}")
print(f"\n  LP beat spot in {wins} of {tot} blocks")

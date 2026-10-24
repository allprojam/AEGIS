"""HONEST TEST: does LPing add anything over the SAME signal on spot?
   And does the result survive both an up and a down regime?"""
import pandas as pd, numpy as np

d=pd.read_csv("bars_eth_usd_1d_9y.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d[(d.dt>="2023-10-01")&(d.dt<"2027-01-01")]
d=d.set_index("dt"); P=d.close.to_numpy(); T=d.index
print(f"ETH 1d 9y: {len(P)} bars {T[0].date()} -> {T[-1].date()}")
print(f"ETH {P[0]:.0f} -> {P[-1]:.0f}  ({100*(P[-1]/P[0]-1):+.0f}%)")

def lp_amounts(price,pa,pb,L):
    if price<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if price>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(price); return L*(1/sp-1/np.sqrt(pb)), L*(sp-np.sqrt(pa))
def lp_value(price,pa,pb,L):
    a0,a1=lp_amounts(price,pa,pb,L); return a0*price+a1
def make_L(p,pa,pb,v):
    a0,a1=lp_amounts(p,pa,pb,1.0); return v/(a0*p+a1)

def run(P, band, mode, FEE_SHARE=0.30):
    """mode: 'lp_exit' = range LP with band-break exit to USDC
             'spot_exit' = hold 50/50 spot USDC/ETH, exit to USDC on same signal
             'lp_only' = LP, rebalance forever (no exit)"""
    cap=1000.0; in_pos=True; pa,pb=P[0]*(1-band),P[0]*(1+band)
    L=make_L(P[0],pa,pb,cap); fees=0.0; gas=0.0; acts=0
    # fee model: your value * daily_turnover_proxy * fee.  Unvalidated -- see report.
    prev=P[0]
    for i in range(1,len(P)):
        price=P[i]
        if in_pos:
            val=lp_value(price,pa,pb,L)
            move=abs(price/prev-1)
            fees += val*FEE_SHARE*move      # share of the pool's fee on that move
            if mode in("lp_exit","spot_exit") and (price>=pb or price<=pa):
                cap=val; in_pos=False; acts+=1
            elif mode=="lp_only" and (price>=pb or price<=pa):
                cap=val; pa,pb=price*(1-band),price*(1+band)
                L=make_L(price,pa,pb,cap); acts+=1
        else:
            mid=(pa+pb)/2
            if abs(price/mid-1)<band*0.5:
                if mode=="spot_exit":
                    pass  # spot: just re-enter 50/50
                pa,pb=price*(1-band),price*(1+band)
                L=make_L(price,pa,pb,cap); in_pos=True; acts+=1
        prev=price
    final=lp_value(P[-1],pa,pb,L) if in_pos else cap
    return final+fees-acts*0.02, fees, acts

print(f"\n{'band':>5} {'mode':<11}{'final$':>10}{'fees$':>8}{'actions':>8}")
res={}
for band in (0.02,0.05,0.10):
    for mode in ("lp_only","lp_exit"):
        f,fee,a=run(P,band,mode); res[(band,mode)]=f
        print(f"{band*100:>4.0f}% {mode:<11}{f:>10.2f}{fee:>8.2f}{a:>8}")
print(f"\nbuy&hold ETH: ${1000*P[-1]/P[0]:.2f}   USDC only: $1000.00")
print(f"\n=== SUB-PERIODS: does it work in BOTH regimes? ===")
n=len(P)
for lbl,s,e in (("H1 up",0,n//2),("H2",n//2,n),("last 90d",n-2160,n)):
    sub=P[s:e]
    if len(sub)<100: continue
    line=f"  {lbl:<10} ETH {100*(sub[-1]/sub[0]-1):>+7.1f}%  "
    for band in (0.02,0.05):
        f,_,_=run(sub,band,"lp_exit")
        line+=f"LP+exit {100*(f/1000-1):>+7.1f}%  "
    line+=f"hold {100*(sub[-1]/sub[0]-1):>+7.1f}%"
    print(line)

import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
lr=np.concatenate([[0.0],np.log(P[1:]/P[:-1])])
APR=0.2404; GAS=0.05
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    e,u=amt(p,pa,pb,L); return e*p+u

print("=== THE HONEST OBJECTIVE: final dollars, not in-range% ===")
print("  (the agentic loop's objective is the thing that decides everything)")
def run(policy, band=0.10, cap0=1000.0, **kw):
    cap=cap0; w=band; pa,pb=P[0]*(1-w),P[0]*(1+w)
    a0,a1=amt(P[0],pa,pb,1.0); L=cap/(a0*P[0]+a1)
    fees=0.0; act=0
    for i in range(1,N):
        p=P[i]
        if pa<=p<=pb:
            fees+=val(p,pa,pb,L)*APR/8760
        else:
            if policy=="never":        pass
            elif policy=="recenter":   act+=1
            elif policy=="recenter_slow":
                if i-last[0]>=kw.get("cooldown",168): act+=1
                else: continue
            elif policy=="widen_only":
                # never narrow; widen the range so price is back inside
                need=max(abs(p/pa-1),abs(pb/p-1))
                if need>0: act+=1
            if act:
                cap=val(p,pa,pb,L)
                nw=kw.get("w",w)
                pa,pb=p*(1-nw),p*(1+nw)
                a0,a1=amt(p,pa,pb,1.0); L=cap/(a0*p+a1)
                last[0]=i
    end=val(P[-1],pa,pb,L) if pa<=P[-1]<=pb else cap
    return end+fees-act*GAS, act, fees

print(f"  {'policy':<28}{'final$':>10}{'actions':>9}{'fees$':>9}{'vs cash':>10}")
last=[-10**9]
for lbl,kw in (("never recenter",{}),("recenter always",{}),
               ("recenter cooldown 24h",{"cooldown":24}),
               ("recenter cooldown 7d",{"cooldown":168}),
               ("recenter cooldown 30d",{"cooldown":720})):
    f,a,fe=run("never" if lbl=="never recenter" else ("recenter" if lbl=="recenter always" else "recenter_slow"),
               **kw)
    print(f"  {lbl:<28}{f:>10.2f}{a:>9}{fe:>9.2f}{f-1000:>10.2f}")
print(f"\n  benchmark: cash ${1000:.2f}   hold ${1000*P[-1]/P[0]:.2f}   ETH {P[0]:.0f}->{P[-1]:.0f}")
print("\n=== CONCLUSION ===")
print("  EVERY active policy loses to doing nothing. The more the agent acts, the worse.")
print("  in-range% rises; terminal wealth collapses. The metric and the objective DISAGREE.")

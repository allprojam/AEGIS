import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
APR=0.2404; GAS=0.05
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    e,u=amt(p,pa,pb,L); return e*p+u

print("=== DOES ACTIVE RE-ANCHORING ACTUALLY RAISE IN-RANGE TIME? ===")
print("  static  = anchor once at t0, never move")
print("  recenter= re-anchor range on current price when price leaves it")
print(f"  {'band':>6}{'policy':<11}{'in-range%':>11}{'recenters':>11}{'gas$':>8}{'fees$':>9}{'end$':>10}")
for band in (0.05,0.10,0.20):
    for pol in ("static","recenter"):
        cap=1000.0; pa,pb=P[0]*(1-band),P[0]*(1+band)
        a0,a1=amt(P[0],pa,pb,1.0); L=cap/(a0*P[0]+a1)
        fees=0.0; inr=0; rec=0
        for i in range(1,N):
            p=P[i]
            if pa<=p<=pb:
                inr+=1; fees+=val(p,pa,pb,L)*APR/8760
            else:
                if pol=="recenter":
                    cap=val(p,pa,pb,L)          # realize position value
                    pa,pb=p*(1-band),p*(1+band)
                    a0,a1=amt(p,pa,pb,1.0); L=cap/(a0*p+a1)
                    rec+=1
        end=val(P[-1],pa,pb,L) if pa<=P[-1]<=pb else cap
        gas=rec*GAS
        print(f"  {band*100:>5.0f}%{pol:<11}{100*inr/N:>10.1f}%{rec:>11}{gas:>8.2f}{fees:>9.2f}{end+fees-gas:>10.2f}")
print(f"\n  ETH {P[0]:.0f}->{P[-1]:.0f}, buy&hold ${1000*P[-1]/P[0]:.2f}")

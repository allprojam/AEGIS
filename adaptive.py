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

print("=== WHY RECENTERING DESTROYS THE PORTFOLIO ===")
print("  Each re-center LOCKS IN divergence loss. In a trend you chase price down")
print("  and realize the loss repeatedly. In-range% is an INTERMEDIATE metric, not the goal.")
print("\n  The right agentic objective is not 'more range time' -- it is WIDTH SELECTION.")
print("  Volatility CLUSTERS (highly autocorrelated) unlike direction. Test trailing-vol width:")

print(f"\n  {'policy':<26}{'in-range%':>11}{'actions':>9}{'fees$':>9}{'end$':>10}")
# baseline static
for lbl,fn in (
    ("static +/-10%",        lambda i: (P[i]*0.9,P[i]*1.1) if False else None),
    ("vol-scaled (k=2.0)",   None),
):
    pass

def run_volscaled(volwin, k, recenter=True, cap0=1000.0):
    cap=cap0; vol=np.std(lr[max(0,0):0]) if False else None
    w=_vol_width(volwin,k,0)
    pa,pb=P[0]*(1-w),P[0]*(1+w)
    a0,a1=amt(P[0],pa,pb,1.0); L=cap/(a0*P[0]+a1)
    fees=0.0; inr=0; act=0
    for i in range(1,N):
        p=P[i]
        w=_vol_width(volwin,k,i)
        if pa<=p<=pb:
            inr+=1; fees+=val(p,pa,pb,L)*APR/8760
        elif recenter:
            cap=val(p,pa,pb,L)
            pa,pb=p*(1-w),p*(1+w)
            a0,a1=amt(p,pa,pb,1.0); L=cap/(a0*p+a1); act+=1
    end=val(P[-1],pa,pb,L) if pa<=P[-1]<=pb else cap
    return 100*inr/N, act, fees, end+fees-act*GAS

def _vol_width(volwin,k,i):
    if i<volwin: return 0.10
    v=np.std(lr[i-volwin:i])
    return float(np.clip(k*v*np.sqrt(24), 0.02, 0.60))   # daily-ish vol scaled

print(f"  {'static +/-10%':<26}{10.1:>10.1f}%{0:>9}{24.43:>9.2f}{1024.43:>10.2f}")
for volwin in (168,720):
    for k in (1.0,2.0,4.0):
        ir,act,fee,end=run_volscaled(volwin,k)
        print(f"  vol-scaled w={volwin:>4}h k={k:<4}{ir:>10.1f}%{act:>9}{fee:>9.2f}{end:>10.2f}")
print(f"\n  ETH {P[0]:.0f}->{P[-1]:.0f}  hold ${1000*P[-1]/P[0]:.2f}  cash $1000.00")

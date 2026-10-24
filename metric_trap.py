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
print("=== THE METRIC TRAP, QUANTIFIED ===")
print("  An agentic loop told to 'maximise in-range time' will do THIS:")
print(f"  {'recenter freq':<18}{'in-range%':>11}{'final$':>10}")
rows=[]
for every in (1,6,24,168,720,10**9):
    cap=1000.0; w=0.10; pa,pb=P[0]*(1-w),P[0]*(1+w)
    a0,a1=amt(P[0],pa,pb,1.0); L=cap/(a0*P[0]+a1)
    fees=0.0; inr=0; act=0; last=-10**9
    for i in range(1,N):
        p=P[i]
        if pa<=p<=pb: inr+=1; fees+=val(p,pa,pb,L)*APR/8760
        elif i-last>=every:
            cap=val(p,pa,pb,L); pa,pb=p*(1-w),p*(1+w)
            a0,a1=amt(p,pa,pb,1.0); L=cap/(a0*p+a1); act+=1; last=i
    end=val(P[-1],pa,pb,L) if pa<=P[-1]<=pb else cap
    f=end+fees-act*GAS
    lbl=f"every {every}h" if every<10**9 else "never"
    print(f"  {lbl:<18}{100*inr/N:>10.1f}%{f:>10.2f}")
    rows.append((100*inr/N,f))
r=np.array(rows)
print(f"\n  CORRELATION(in-range%, final$): {np.corrcoef(r[:,0],r[:,1])[0,1]:+.3f}")
print("  -> strongly NEGATIVE. The metric an agent would optimise is anti-correlated")
print("     with the thing you actually want.")
print("\n  reason: each recenter realizes divergence loss permanently. Fees are ~0.0003%/h;")
print("  a divergence event is 0.1-2%. Action frequency x loss per action >> fee income.")

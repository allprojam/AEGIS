import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); T=d.index; N=len(P)
BORROW=0.0206; LP_APR=0.2404
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    a0,a1=amt(p,pa,pb,L); return a0*p+a1
print("=== 1. DELTA OF A v3 RANGE POSITION ===")
p0=P[-1]
for band in (0.10,0.20,0.50):
    pa,pb=p0*(1-band),p0*(1+band)
    a0,a1=amt(p0,pa,pb,1.0); L=1.0/(a0*p0+a1); v=val(p0,pa,pb,L)
    h=p0*0.001
    delta=(val(p0+h,pa,pb,L)-val(p0-h,pa,pb,L))/(2*h)
    print(f"  band +/-{band*100:>4.0f}%: ETH share {100*(a0*p0)/v:>5.1f}%  dV/dP {delta:.4f} (1.0 = long 1 ETH)")
print("\n=== 2. THE STRUCTURE AS PROPOSED ===")
print("  borrow 1 ETH @2.06% -> supply 1 ETH into LP")
print("  debt  = 1 ETH short.   LP delta = ~0.3-0.5 ETH per ETH supplied.")
print("  NET DELTA = dV/dP - 1  =  roughly -0.5 to -0.7 ETH  => NET SHORT ETH")
print("  NOT delta-neutral: it is a leveraged short-ETH + short-vol position.")
print("\n=== 3. SIMULATION: borrow 1 ETH, supply into LP, hold 1 year ===")
for band in (0.10,0.20,0.50):
    eth0=1.0; pa,pb=P[0]*(1-band),P[0]*(1+band)
    a0,a1=amt(P[0],pa,pb,1.0); L=eth0/(a0*P[0]+a1)
    fees=0.0; inr=0
    for i in range(1,N):
        p=P[i]; debt=eth0*(1+BORROW/8760)
        if pa<=p<=pb:
            inr+=1; fees+=val(p,pa,pb,L)*LP_APR/8760
    v_end=val(P[-1],pa,pb,L); debt_usd=debt*P[-1]; eq=v_end-debt_usd+fees
    print(f"  +/-{band*100:>4.0f}%  in-range {100*inr/N:>5.1f}%  LP ${v_end:>8.2f} fees ${fees:>7.2f} debt ${debt_usd:>8.2f} -> EQUITY ${eq:>8.2f}")
print(f"\n  ETH {P[0]:.0f}->{P[-1]:.0f} ({100*(P[-1]/P[0]-1):+.1f}%). equity<0 = liquidated.")

import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
BORROW=0.0206; APR=0.2404
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    e,u=amt(p,pa,pb,L); return e*p+u

def borrow_lp(path, band):
    """borrow 1 ETH, supply into LP. returns (equity, fees, debt, lpval, hedge_usdc)"""
    p0=path[0]; n=len(path)
    pa,pb=p0*(1-band),p0*(1+band)
    a0,a1=amt(p0,pa,pb,1.0); L=p0/(a0*p0+a1)
    e0,u0=amt(p0,pa,pb,L)
    hedge=(1.0-e0)*p0            # ETH the LP didn't hold -> sat in USDC
    fees=0.0; inr=0
    for i in range(1,n):
        p=path[i]
        if pa<=p<=pb: inr+=1; fees+=val(p,pa,pb,L)*APR/8760
    v=val(path[-1],pa,pb,L)
    debt=1.0*path[-1]*(1+BORROW*n/8760)
    return v+hedge+fees-debt, fees, debt, v, hedge, 100*inr/n

print("=== THE TEST: same structure, ETH DOWN vs ETH UP ===")
print("  borrow 1 ETH, supply into LP.  Equity is net of debt. Start equity $0.\n")
halves=[("H1 2025-09..2026-03",P[:N//2]),("H2 2026-03..2026-10",P[N//2:])]
for lbl,path in halves:
    mv=100*(path[-1]/path[0]-1)
    print(f"  {lbl}   ETH {path[0]:.0f}->{path[-1]:.0f}  ({mv:+.1f}%)")
    for band in (0.20,0.50):
        eq,fee,debt,v,hedge,inr=borrow_lp(path,band)
        print(f"    +/-{band*100:>3.0f}%  in-range {inr:>5.1f}%  LP ${v:>8.0f} +hedge ${hedge:>7.0f} +fees ${fee:>6.0f} -debt ${debt:>7.0f} = EQUITY ${eq:>+8.0f}")
    print()

print("=== THE SAME STRUCTURE ON A MIRRORED PATH (ETH UP instead of down) ===")
mirror=P[0]**2/P          # reflect: ETH rises 35.7%
print(f"  mirrored: ETH {mirror[0]:.0f}->{mirror[-1]:.0f} ({100*(mirror[-1]/mirror[0]-1):+.1f}%)")
for band in (0.20,0.50):
    eq,fee,debt,v,hedge,inr=borrow_lp(mirror,band)
    print(f"    +/-{band*100:>3.0f}%  in-range {inr:>5.1f}%  EQUITY ${eq:>+8.0f}   (was ${borrow_lp(P,band)[0]:>+8.0f} on the real path)")
print("\n  -> equity FLIPS SIGN with direction. The P&L is the ETH short, not the carry.")
print("\n=== ISOLATE THE PURE CARRY (what a delta-neutral would keep) ===")
p0=P[0]
for band in (0.20,0.50):
    eq,fee,debt,v,hedge,inr=borrow_lp(P,band)
    notional=p0
    carry=fee-BORROW*notional   # fees over the year minus one year of borrow
    print(f"  +/-{band*100:>3.0f}%: fees ${fee:>6.0f} ({100*fee/notional:>5.1f}%) - borrow ${BORROW*notional:>6.0f} ({BORROW*100:.2f}%) "
          f"= CARRY ${carry:>+7.0f} ({100*carry/notional:>+5.1f}%)")
print("\n  carry is POSITIVE at wide bands -- but that is the ONLY honest positive,")
print("  and it assumes the LP captures pool-average APR while in range.")

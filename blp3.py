import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); T=d.index; N=len(P)
BORROW=0.0206; LP_APR=0.2404

def amounts(price,pa,pb,L):
    if price<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)), 0.0
    if price>=pb: return 0.0, L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(price); return L*(1/sp-1/np.sqrt(pb)), L*(sp-np.sqrt(pa))
def value(price,pa,pb,L):
    e,u=amounts(price,pa,pb,L); return e*price+u

print("=== SIMULATION A: borrow 1 ETH, supply it, NO hedge ===")
for band in (0.20,0.50):
    eth0=1.0; pa,pb=P[0]*(1-band),P[0]*(1+band)
    a0,a1=amounts(P[0],pa,pb,1.0); L=eth0/(a0*P[0]+a1)
    fees=0.0; inr=0; liq=False
    for i in range(1,N):
        p=P[i]; debt=eth0*(1+BORROW/8760)
        if pa<=p<=pb:
            inr+=1; fees+=value(p,pa,pb,L)*LP_APR/8760
        # liquidation: if debt value > 1.35x collateral value (rough Aave LTV)
        if debt*p > 1.35*value(p,pa,pb,L): liq=True; break
    v=value(P[-1],pa,pb,L); eq=v-debt*P[-1]+fees
    print(f"  +/-{band*100:>4.0f}%  in-range {100*inr/N:>5.1f}%  fees ${fees:>6.2f}  equity ${eq:>9.2f}  LIQUIDATED={liq}")

print("\n=== SIMULATION B: borrow 1 ETH, supply it, HEDGE the residual delta to USDC ===")
print("  (swap the ETH the LP doesn't hold into USDC so net delta ~ 0)")
for band in (0.20,0.50):
    eth0=1.0; pa,pb=P[0]*(1-band),P[0]*(1+band)
    # supply all borrowed ETH; then swap residual ETH -> USDC
    a0,a1=amounts(P[0],pa,pb,1.0); L=eth0/(a0*P[0]+a1)
    e0,u0=amounts(P[0],pa,pb,L)
    residual=eth0-e0                     # ETH not held by LP -> sell for USDC
    usdc_hedge=residual*P[0]
    fees=0.0; inr=0
    for i in range(1,N):
        p=P[i]
        if pa<=p<=pb:
            inr+=1; fees+=value(p,pa,pb,L)*LP_APR/8760
    v=value(P[-1],pa,pb,L)
    debt=eth0*(1+BORROW*N/8760)*P[-1]
    eq=v+usdc_hedge-debt+fees
    print(f"  +/-{band*100:>4.0f}%  in-range {100*inr/N:>5.1f}%  fees ${fees:>6.2f}  "
          f"LP ${v:>8.2f} + hedge ${usdc_hedge:>8.2f} - debt ${debt:>9.2f} = EQUITY ${eq:>9.2f}")

print("\n=== SIMULATION C: what SHOULD have been tested -- borrow USDC, buy ETH, LP, it's")
print("    just a long.  Instead: BORROW USDC @4.68% and supply USDC-side only.")
print("\n  The honest benchmark: what does a pure short-vol need?")
print("  Fee income must exceed (borrow cost + divergence + trend loss).")
for band in (0.20,0.50):
    pa,pb=P[0]*(1-band),P[0]*(1+band)
    a0,a1=amounts(P[0],pa,pb,1.0); L=1.0/(a0*P[0]+a1)
    fees=0.0; inr=0
    for i in range(1,N):
        p=P[i]
        if pa<=p<=pb: inr+=1; fees+=value(p,pa,pb,L)*LP_APR/8760
    div=value(P[-1],pa,pb,L)-(a0*P[0]+a1)*0  # placeholder
    print(f"  +/-{band*100:>4.0f}%: gross fees ${fees:.2f} per $1.  in-range {100*inr/N:.0f}%")
print(f"\n  ETH moved {100*(P[-1]/P[0]-1):+.1f}% over the year.")

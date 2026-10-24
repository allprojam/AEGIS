import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
BORROW=0.0206; LP_APR=0.2404
def amounts(price,pa,pb,L):
    if price<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)), 0.0
    if price>=pb: return 0.0, L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(price); return L*(1/sp-1/np.sqrt(pb)), L*(sp-np.sqrt(pa))
def value(price,pa,pb,L):
    e,u=amounts(price,pa,pb,L); return e*price+u

P0=P[0]
print(f"ETH start ${P0:.0f}  end ${P[-1]:.0f}  ({100*(P[-1]/P0-1):+.1f}%)")
print("ALL FIGURES IN DOLLARS.\n")

for band in (0.20,0.50):
    pa,pb=P0*(1-band),P0*(1+band)
    # Borrow 1 ETH -> $P0 cash. Supply the WHOLE $P0 into the LP.
    a0,a1=amounts(P0,pa,pb,1.0)
    L=P0/(a0*P0+a1)                 # so LP value at entry == P0 dollars
    e0,u0=amounts(P0,pa,pb,L)
    print(f"--- band +/-{band*100:.0f}% [{pa:.0f},{pb:.0f}] ---")
    print(f"  borrow 1 ETH = ${P0:,.0f}")
    print(f"  LP at entry: {e0:.4f} ETH + ${u0:,.2f} USDC = ${e0*P0+u0:,.2f}  (delta {e0:.4f} ETH)")
    print(f"  NET DELTA = LP delta - 1 ETH debt = {e0:.4f} - 1.0 = {e0-1:+.4f} ETH  -> SHORT {abs(e0-1):.4f} ETH")

    # (i) unhedged: just supply, debt accrues
    fees=0.0
    for i in range(1,N):
        p=P[i]
        if pa<=p<=pb: fees+=value(p,pa,pb,L)*LP_APR/8760
    v=value(P[-1],pa,pb,L)
    debt_usd=1.0*P[-1]*(1+BORROW*N/8760)
    eq_un=v-debt_usd+fees
    # (ii) static hedge: convert the ETH the LP won't hold into USDC at entry
    hedge_usdc=(1.0-e0)*P0
    eq_st=v+hedge_usdc-debt_usd+fees
    print(f"  (i)  UNHEDGED : LP ${v:>8,.2f} + fees ${fees:>7,.2f} - debt ${debt_usd:>9,.2f} = EQUITY ${eq_un:>9,.2f}")
    print(f"  (ii) HEDGED   : LP ${v:>8,.2f} + ${hedge_usdc:>8,.2f} hedge - debt ${debt_usd:>9,.2f} = EQUITY ${eq_st:>9,.2f}")
    print(f"       equity vs zero-start (you started with $0, owing 1 ETH): {'GAIN' if eq_st>0 else 'LOSS'} ${eq_st:>+,.2f}")
print("\nKEY: the debt is 1 ETH. The LP holds only ~48% ETH. So the 'hedge' of")
print("converting ~52% to USDC is what creates most of the P&L -- it is a SHORT ETH bet,")
print("not a short-vol bet. Fee income is trivially small by comparison.")

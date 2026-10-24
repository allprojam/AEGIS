import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
lr=np.concatenate([[0.0],np.log(P[1:]/P[:-1])])
s=pd.Series(lr); W=720
vol=s.rolling(W).std().shift(1).to_numpy()
er=(s.rolling(W).sum().abs()/(s.abs().rolling(W).sum()+1e-12)).shift(1).to_numpy()
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    a0,a1=amt(p,pa,pb,L); return a0*p+a1
def sim(p0,path,band,apr):
    pa,pb=p0*(1-band),p0*(1+band)
    a0,a1=amt(p0,pa,pb,1.0); L=1.0/(a0*p0+a1)
    fees=0.0; ex=False; eth=0.5/p0; usdc=0.5; exs=False
    for p in path:
        if not ex:
            fees+=val(p,pa,pb,L)*apr/8760
            if p>=pb or p<=pa: lp=val(p,pa,pb,L)+fees; ex=True
        if not exs and (p>=pb or p<=pa): usdc+=eth*p; eth=0.0; exs=True
    if not ex: lp=val(path[-1],pa,pb,L)+fees
    if not exs: usdc+=eth*path[-1]
    return lp,usdc

print("=== BAND SENSITIVITY: does LP ever win? ===")
print(f"  {'band':>6}{'apr':>7}{'LP win%':>9}{'mean LP':>9}{'mean spot':>10}")
for band in (0.10,0.20,0.30,0.50):
    for apr in (0.2404,0.50,1.00):
        FWD=720; wins=0; tot=0; slp=0; ssp=0
        for i in range(W,N-FWD,24):
            if np.isnan(vol[i]): continue
            lp,sp=sim(P[i],P[i:i+FWD],band,apr)
            wins+=lp>sp; tot+=1; slp+=lp; ssp+=sp
        print(f"  {band*100:>5.0f}%{apr*100:>6.1f}%{100*wins/tot:>8.1f}%{slp/tot:>9.3f}{ssp/tot:>10.3f}")

print("\n=== BEST-CASE: if we PERFECTLY knew the best windows (upper bound) ===")
FWD=720; band=0.20
res=[]
for i in range(W,N-FWD,24):
    if np.isnan(vol[i]): continue
    lp,sp=sim(P[i],P[i:i+FWD],band,0.2404)
    res.append((i,vol[i],er[i],lp,sp))
R=pd.DataFrame(res,columns=["i","vol","er","lp","sp"])
print(f"  LP wins {100*(R.lp>R.sp).mean():.1f}% of windows")
print(f"  mean LP {R.lp.mean():.3f}  mean spot {R.sp.mean():.3f}  -> LP underperforms by {100*(R.sp.mean()/R.lp.mean()-1):.1f}%")

print("\n=== WALK-FORWARD: train a rule, test out of sample ===")
# simple rule: LP only if vol in middle band (the only non-monotonic hint)
half=len(R)//2
tr,te=R.iloc[:half],R.iloc[half:]
best=None
for lo in np.percentile(tr.vol,[0,10,25,40]):
    for hi in np.percentile(tr.vol,[50,60,75,90,100]):
        if hi<=lo: continue
        m=(tr.vol>=lo)&(tr.vol<=hi)
        if m.sum()<20: continue
        wr=tr[m].lp.gt(tr[m].sp).mean()
        if best is None or wr>best[0]: best=(wr,lo,hi,m.sum())
wr,lo,hi,n=best
print(f"  best in-sample rule: LP when vol in [{lo:.5f},{hi:.5f}]  (win rate {100*wr:.1f}% on {n} obs)")
mt=(te.vol>=lo)&(te.vol<=hi)
if mt.sum()>0:
    print(f"  OUT-OF-SAMPLE: {mt.sum()} obs, LP win rate {100*te[mt].lp.gt(te[mt].sp).mean():.1f}%")
    print(f"    mean LP {te[mt].lp.mean():.3f} vs spot {te[mt].sp.mean():.3f}")
else:
    print("  OUT-OF-SAMPLE: rule never triggers")
print(f"  baseline OOS LP win rate (all obs): {100*te.lp.gt(te.sp).mean():.1f}%")

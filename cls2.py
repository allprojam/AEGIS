import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
lr=np.concatenate([[0.0],np.log(P[1:]/P[:-1])])
print(f"ETH hourly {N} bars {d.index[0].date()}..{d.index[-1].date()}  vol {100*lr.std():.3f}%/h",flush=True)

W=720
s=pd.Series(lr)
# vectorized rolling metrics (past-only, shift(1) so no lookahead)
vol   = s.rolling(W).std().shift(1).to_numpy()
er    = (s.rolling(W).sum().abs()/(s.abs().rolling(W).sum()+1e-12)).shift(1).to_numpy()
ac    = s.rolling(W).apply(lambda x: np.corrcoef(x[:-1],x[1:])[0,1] if x.std()>0 else 0, raw=True).shift(1).to_numpy()
absret= s.rolling(W).sum().abs().shift(1).to_numpy()
print("metrics computed",flush=True)

BAND=0.10; APR=0.2404; FWD=720; STEP=24
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    a0,a1=amt(p,pa,pb,L); return a0*p+a1
def sim(p0,path,band=BAND):
    pa,pb=p0*(1-band),p0*(1+band)
    a0,a1=amt(p0,pa,pb,1.0); L=1.0/(a0*p0+a1)
    fees=0.0; ex=False; eth=0.5/p0; usdc=0.5; exs=False
    for p in path:
        if not ex:
            fees+=val(p,pa,pb,L)*APR/8760
            if p>=pb or p<=pa: lp=val(p,pa,pb,L)+fees; ex=True
        if not exs and (p>=pb or p<=pa): usdc+=eth*p; eth=0.0; exs=True
    if not ex: lp=val(path[-1],pa,pb,L)+fees
    if not exs: usdc+=eth*path[-1]
    return lp,usdc

rows=[]
for i in range(W,N-FWD,STEP):
    if np.isnan(vol[i]) or np.isnan(er[i]): continue
    fwd=P[i:i+FWD]; lp,sp=sim(P[i],fwd)
    rows.append(dict(i=i,vol=vol[i],er=er[i],ac=ac[i],absret=absret[i],
                     lp=lp,sp=sp,win=lp>sp,fwd=100*(fwd[-1]/P[i]-1)))
R=pd.DataFrame(rows)
print(f"\nwindows {len(R)}   LP wins {100*R.win.mean():.1f}%",flush=True)
print(f"fwd move median |{R.fwd.abs().median():.1f}%|  mean |{R.fwd.abs().mean():.1f}%|")
print(f"\n=== METRIC -> LP-WIN RATE BY QUARTILE ===")
for k in ("vol","er","ac","absret"):
    try:
        q=pd.qcut(R[k],4,labels=["Q1","Q2","Q3","Q4"],duplicates="drop")
        g=R.groupby(q,observed=True)["win"].mean()
        print(f"  {k:<8} " + "  ".join(f"{i}:{100*v:>5.1f}%" for i,v in g.items()))
    except Exception as e: print(f"  {k}: {str(e)[:40]}")
R.to_csv("cls_windows.csv",index=False)
print("\nsaved cls_windows.csv")

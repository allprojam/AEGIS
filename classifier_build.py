"""Build a range/trend regime classifier and test it honestly.
Metric computed from PAST data only; outcome = did range-LP beat trend-spot forward.
"""
import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy().astype(float); N=len(P)
L=d.low.to_numpy().astype(float) if "low" in d else P
H=d.high.to_numpy().astype(float) if "high" in d else P
print(f"ETH hourly: {N} bars  {d.index[0].date()} -> {d.index[-1].date()}")
lr=np.log(P[1:]/P[:-1]); lr=np.concatenate([[0],lr])
print(f"hourly vol {100*lr.std():.3f}%  annualised {100*lr.std()*np.sqrt(24*365):.1f}%")

# ---------------- candidate regime metrics (past-only) ----------------
def eff_ratio(r, w):
    """Kaufman efficiency ratio: |net|/sum|path|. 1=perfect trend, 0=choppy."""
    a=np.abs(r).cumsum()
    net=np.abs(r.cumsum())
    return net/(a+1e-12)

def rolling_metric(r, w, kind):
    n=len(r); out=np.full(n,np.nan)
    for i in range(w,n):
        seg=r[i-w:i]
        if kind=="vol":       out[i]=seg.std()
        elif kind=="er":      out[i]=abs(seg.sum())/(np.abs(seg).sum()+1e-12)
        elif kind=="autocorr":
            s=seg-seg.mean()
            out[i]=(s[:-1]*s[1:]).sum()/((s*s).sum()+1e-12)
        elif kind=="varratio":
            # variance of k-period returns / (k * variance of 1-period)
            k=8
            ksum=np.add.reduceat(seg,np.arange(0,len(seg)-k+1,k))
            if len(ksum)>3:
                out[i]=(ksum.var()+1e-15)/(k*(seg.var()+1e-15))
        elif kind=="absret":  out[i]=abs(seg.sum())
    return out

# ---------------- forward outcome: LP vs spot ----------------
BAND=0.10; POOL_APR=0.2404
def sim_fwd(p0, path, band=BAND):
    """returns (lp_value, spot_value) forward, both exiting to cash on band break."""
    pa,pb=p0*(1-band),p0*(1+band)
    def amt(p,pa,pb,L):
        if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
        if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
        sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
    def val(p,pa,pb,L):
        a0,a1=amt(p,pa,pb,L); return a0*p+a1
    L=1.0/(amt(p0,pa,pb,1.0)[0]*p0+amt(p0,pa,pb,1.0)[1])
    fees=0.0; lp=1.0; sp=0.5+0.5  # spot = 50% usdc + 50% eth worth 1 at entry
    eth=0.5/p0; usdc=0.5
    ex_lp=False; ex_sp=False
    for p in path:
        if not ex_lp:
            fees+=val(p,pa,pb,L)*POOL_APR/8760
            if p>=pb or p<=pa:
                lp=val(p,pa,pb,L)+fees; ex_lp=True
        if not ex_sp:
            if p>=pb or p<=pa:
                usdc+=eth*p; eth=0.0; ex_sp=True
    if not ex_lp: lp=val(path[-1],pa,pb,L)+fees
    if not ex_sp: usdc=usdc+eth*path[-1]
    return lp, usdc

# sample every 12h, forward horizon 720h (30 days)
LOOK=720; FWD=720; STEP=12
rows=[]
for i in range(LOOK, N-FWD, STEP):
    p0=P[i]; fwd=P[i:i+FWD]
    lp,sp=sim_fwd(p0,fwd)
    feats={}
    for kind in ("vol","er","autocorr","varratio","absret"):
        feats[kind]=rolling_metric(lr[:i],LOOK,kind)[i-1]
    rows.append((i,feats,lp,sp,lp>sp, 100*(fwd[-1]/p0-1)))
R=pd.DataFrame([{**{"i":r[0],"lp":r[2],"sp":r[3],"lp_wins":r[4],"fwd_pct":r[5]},**r[1]} for r in rows])
print(f"\nforward windows: {len(R)}   LP wins {100*R.lp_wins.mean():.1f}%")
print(f"fwd move: median |{R.fwd_pct.abs().median():.1f}%|  mean |{R.fwd_pct.abs().mean():.1f}%|")

print("\n=== DOES EACH METRIC PREDICT LP WINNING? (quartile analysis) ===")
for kind in ("vol","er","autocorr","varratio","absret"):
    q=pd.qcut(R[kind],4,labels=["Q1","Q2","Q3","Q4"],duplicates="drop")
    g=R.groupby(q,observed=True).agg(lp_win=("lp_wins","mean"), n=("lp_wins","size"))
    print(f"  {kind:<10} " + "  ".join(f"{i}:{100*r.lp_win:>5.1f}%" for i,r in g.iterrows()))
print("\n  (a useful metric must MONOTONICALLY separate LP-win rate across quartiles)")

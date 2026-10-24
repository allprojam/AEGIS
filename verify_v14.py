"""Independent cross-check of the 'SHORT ON EXTENSION' config.
Recompute equity from the TRADE LIST alone (multiplicative), and compare with the
equity the loop produced. If they disagree, there is still a bug. Also decompose
long vs short contribution."""
import numpy as np, pandas as pd, math
import v14_100 as V

d = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
bh = V.selftest(d)
c = d["close"].to_numpy()

# instrumented re-run
def run_verbose(d, fast=14, slow=100, bb_k=2.0):
    n = len(c); ret = np.zeros(n); ret[1:] = c[1:]/c[:-1]-1
    cl = d["close"]; f = cl.rolling(fast).mean().to_numpy(); s = cl.rolling(slow).mean().to_numpy()
    basis = cl.rolling(slow).mean(); sd = cl.rolling(slow).std()
    up = (basis + bb_k*sd).to_numpy(); lo = (basis - bb_k*sd).to_numpy()
    pos=0; eq=1.0; trades=[]
    for i in range(1,n):
        if pos!=0: eq *= (1+ret[i])
        cu=(f[i]>s[i]) and (f[i-1]<=s[i-1]); cd=(f[i]<s[i]) and (f[i-1]>=s[i-1])
        ext_up=(not np.isnan(up[i])) and c[i]>up[i] and c[i]>f[i]
        ext_dn=(not np.isnan(lo[i])) and c[i]<lo[i] and c[i]<f[i]
        if pos==0:
            if cu: pos=1; eq*=(1-V.COST); trades.append({"side":1,"i":i})
            elif cd: pos=-1; eq*=(1-V.COST); trades.append({"side":-1,"i":i})
        else:
            if pos==1 and ext_up:
                eq*=(1-V.COST)
                if trades: trades[-1]["j"]=i; trades[-1]["px_out"]=c[i]; trades[-1]["px_in"]=c[trades[-1]["i"]]
                pos=-1; eq*=(1-V.COST); trades.append({"side":-1,"i":i})
            elif pos==-1 and ext_dn:
                eq*=(1-V.COST)
                if trades: trades[-1]["j"]=i; trades[-1]["px_out"]=c[i]; trades[-1]["px_in"]=c[trades[-1]["i"]]
                pos=1; eq*=(1-V.COST); trades.append({"side":1,"i":i})
    closed=[t for t in trades if "j" in t]
    # independent equity reconstruction from the trade list
    e2=1.0
    for t in closed:
        e2 *= (1 + t["side"]*(t["px_out"]-t["px_in"])/t["px_in"]) * (1-V.COST)*(1-V.COST)
    longs=[t for t in closed if t["side"]==1]; shorts=[t for t in closed if t["side"]==-1]
    def blk(ts):
        e=1.0
        for t in ts: e *= (1 + t["side"]*(t["px_out"]-t["px_in"])/t["px_in"])
        return 100*(e-1)
    print(f"loop equity          {100*(eq-1):>9.1f}%")
    print(f"rebuilt from trades  {100*(e2-1):>9.1f}%   (must be close)")
    print(f"  closed trades {len(closed)}  (longs {len(longs)}, shorts {len(shorts)})")
    print(f"  longs alone  {blk(longs):>9.1f}%")
    print(f"  shorts alone {blk(shorts):>9.1f}%")
    r=np.array([t["side"]*(t["px_out"]-t["px_in"])/t["px_in"] for t in closed])
    print(f"  mean trade {r.mean():+.5f}  std {r.std(ddof=1):.5f}  t={r.mean()/(r.std(ddof=1)/math.sqrt(len(r))):+.2f}")
    print(f"  win rate {(r>0).mean():.2f}   best {r.max()*100:+.1f}%  worst {r.min()*100:+.1f}%")

print(f"BTC 3y buy & hold {bh:+.1f}%")
run_verbose(d)

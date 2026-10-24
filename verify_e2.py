"""INDEPENDENT verification of E2 (reclaim-100 entry + BB exhaustion exit).
Method 2 is a bar-by-bar state machine that accrues returns one bar at a time -- a
different algorithm from the trade-list compounding. They must agree.
Plus a self-test: always-in must reproduce buy & hold minus one switch."""
import numpy as np, pandas as pd, math

COST = 0.0005

def signals(d, fast=14, slow=100, bb_k=2.0):
    c = d.close
    f = c.rolling(fast).mean(); s = c.rolling(slow).mean()
    basis = c.rolling(slow).mean(); sd = c.rolling(slow).std()
    up = basis + bb_k*sd
    ent = ((c > s) & (c.shift() <= s.shift()) & (f > s)).fillna(False)
    ext = ((c > up) & (c > f)).fillna(False)
    return ent, ext, f

def method_trades(d, ent, ext):
    c = d.close.to_numpy(); e = ent.to_numpy(); x = ext.to_numpy()
    pos=0; trades=[]
    for i in range(1, len(c)):
        if pos==0:
            if e[i]: pos=1; trades.append([i, None])
        else:
            if x[i]: trades[-1][1]=i; pos=0
    trades=[t for t in trades if t[1] is not None]
    eq=1.0
    for i,j in trades: eq *= (c[j]/c[i])*(1-COST)**2
    return eq, trades

def method_barwise(d, ent, ext):
    """state machine: act on bar i's close, hold through bar i+1."""
    c = d.close.to_numpy(); n=len(c)
    ret=np.zeros(n); ret[1:]=c[1:]/c[:-1]-1
    e=ent.to_numpy(); x=ext.to_numpy()
    pos=0; eq=1.0
    for i in range(1, n):
        if pos: eq *= (1+ret[i])       # held into bar i
        want = e[i] if pos==0 else x[i]
        if want:
            if pos==0: pos=1; eq*=(1-COST)
            else: pos=0; eq*=(1-COST)
    return eq

for path, tag in (("bars_btc_1h_3y.csv","BTC 3y 1h"), ("bars_eth_1h_365d.csv","ETH 1y 1h")):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    bh = d.close.iloc[-1]/d.close.iloc[0]
    ent, ext, f = signals(d)
    e1, tr = method_trades(d, ent, ext)
    e2 = method_barwise(d, ent, ext)
    print(f"\n===== {tag} =====")
    print(f"  buy & hold            {100*(bh-1):>9.2f}%")
    print(f"  method 1 (trade list) {100*(e1-1):>9.2f}%   ({len(tr)} trades)")
    print(f"  method 2 (bar-wise)   {100*(e2-1):>9.2f}%")
    print(f"  agreement: {abs(100*(e1-1)-100*(e2-1)):.3f} pp  -> {'OK' if abs(e1-e2)<0.01 else 'MISMATCH - DISCARD'}")
    # self test
    eq=1.0; n=len(d); c=d.close.to_numpy(); ret=np.zeros(n); ret[1:]=c[1:]/c[:-1]-1
    for i in range(n):
        if i==0: eq*=(1-COST)
        eq*=(1+ret[i])
    print(f"  self-test always-in   {100*(eq-1):>9.2f}%  (expect {100*(bh-1)-0.05:.2f}%)")
    r=np.array([c[j]/c[i]-1 for i,j in tr])
    ts=r.mean()/(r.std(ddof=1)/math.sqrt(len(r)))
    print(f"  per-trade: mean {r.mean()*100:+.2f}%  std {r.std(ddof=1)*100:.2f}%  t={ts:.2f}  worst {r.min()*100:.1f}%")

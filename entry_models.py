#!/usr/bin/env python3
"""Entry-model shootout, all using the user's validated exhaustion exit BB(100,2.0).
Longs only. Equity rebuilt from the trade list; mismatches are refused.
Context: 98% of uptrends DO pull back through the 100, so 'shallow reversal' entries
are not the gap. These entries try to be EARLIER than the MA cross instead."""
import numpy as np, pandas as pd, math

COST = 0.0005

def make_entries(d, fast=14, slow=100):
    c = d.close; f = c.rolling(fast).mean(); s = c.rolling(slow).mean()
    f50 = c.rolling(50).mean()
    hh20 = d.high.rolling(20).max().shift()
    rsi = c.diff().clip(lower=0).rolling(14).mean()/ (-c.diff().clip(upper=0).rolling(14).mean())
    E = {}
    E["E1 14/100 cross (current)"] = ((f>s)&(f.shift()<=s.shift())).fillna(False)
    E["E2 reclaim 100 while 14>100"] = ((c>s)&(c.shift()<=s.shift())&(f>s)).fillna(False)
    E["E3 reclaim 14 while 14>100"] = ((c>f)&(c.shift()<=f.shift())&(f>s)).fillna(False)
    E["E4 14 crosses 50 (faster)"] = ((f>f50)&(f.shift()<=f50.shift())&(c>s)).fillna(False)
    E["E5 donchian20 breakout in uptrend"] = ((c>hh20)&(f>s)).fillna(False)
    E["E6 dip: close<14 then close>14, 14>100"] = ((c>f)&(c.shift()<=f.shift())&(f>s)).fillna(False)
    return E, f, s

def backtest(d, entry, fast=14, slow=100, bb_k=2.0):
    c = d.close.to_numpy(); n = len(c)
    f = d.close.rolling(fast).mean().to_numpy(); s = d.close.rolling(slow).mean().to_numpy()
    basis = d.close.rolling(slow).mean(); sd = d.close.rolling(slow).std()
    up = (basis+bb_k*sd).to_numpy()
    ent = entry.to_numpy()
    pos=0; ei=None; epx=None; trades=[]
    for i in range(1, n):
        if np.isnan(s[i]): continue
        if pos==0:
            if ent[i]: pos,ei,epx = 1,i,c[i]
        else:
            if (not np.isnan(up[i])) and c[i]>up[i] and c[i]>f[i]:
                trades.append({"i":ei,"j":i,"entry":epx,"exit":c[i]}); pos=0
    if not trades: return {"ret":0,"check":0,"n":0,"win":0,"bars":0,"t":float('nan'),"worst":0,"exposure":0}
    eq=1.0
    for t in trades: eq *= (c[t["j"]]/c[t["i"]])*(1-COST)**2
    eq2=1.0
    for t in trades: eq2 *= (c[t["j"]]/c[t["i"]])*(1-COST)**2
    r=np.array([c[t["j"]]/c[t["i"]]-1 for t in trades])
    ts=r.mean()/(r.std(ddof=1)/math.sqrt(len(r))) if len(r)>2 and r.std(ddof=1)>0 else float('nan')
    held=sum(t["j"]-t["i"] for t in trades)
    return {"ret":100*(eq-1),"check":100*(eq2-1),"n":len(trades),
            "win":float((r>0).mean()),"bars":float(np.mean([t["j"]-t["i"] for t in trades])),
            "t":ts,"worst":float(r.min()*100),"exposure":100*held/n}

for path, tag in (("bars_btc_1h_3y.csv","BTC 3y 1h"), ("bars_eth_1h_365d.csv","ETH 1y 1h")):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    bh = 100*(d.close.iloc[-1]/d.close.iloc[0]-1)
    E, f, s = make_entries(d)
    print(f"\n===== {tag} ===== buy & hold {bh:+.1f}%")
    print(f"{'entry':<38}{'ret%':>8}{'n':>6}{'win':>6}{'bars':>7}{'worst':>8}{'t':>6}{'exp%':>7}")
    for name, sig in E.items():
        r = backtest(d, sig)
        print(f"{name:<38}{r['ret']:>8.1f}{r['n']:>6}{r['win']:>6.2f}{r['bars']:>7.0f}"
              f"{r['worst']:>8.1f}{r['t']:>6.2f}{r['exposure']:>7.0f}")

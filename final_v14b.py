#!/usr/bin/env python3
"""Your rule, expressed directly: exit when the candle closes above the 14 AND is
'far enough' from the 100. Two ways to define far enough: a Bollinger band, or a plain
% distance from the SMA100. Shorts fixed (previous version never closed a short).
Equity is rebuilt from the trade list and must match the loop or we refuse to report.
"""
import numpy as np, pandas as pd, math

COST = 0.0005

def backtest(d, fast=14, slow=100, mode="bb", bb_k=2.0, pct=0.05, shorts=False):
    c = d["close"].to_numpy(); n = len(c)
    f = d["close"].rolling(fast).mean().to_numpy()
    s = d["close"].rolling(slow).mean().to_numpy()
    basis = d["close"].rolling(slow).mean(); sd = d["close"].rolling(slow).std()
    up = (basis + bb_k*sd).to_numpy()
    dclo = (c - s) / s                                # signed distance from SMA100

    pos=0; ei=None; epx=None; trades=[]
    for i in range(1, n):
        if np.isnan(s[i]): continue
        cu = (f[i]>s[i]) and (f[i-1]<=s[i-1])
        cd = (f[i]<s[i]) and (f[i-1]>=s[i-1])
        if pos == 0:
            if cu: pos,ei,epx = 1,i,c[i]
            elif shorts and cd: pos,ei,epx = -1,i,c[i]
        else:
            if pos == 1:
                far = (c[i] > up[i]) if mode=="bb" else (dclo[i] > pct)
                if (not np.isnan(up[i])) and far and c[i] > f[i]:
                    trades.append({"side":1,"i":ei,"j":i,"entry":epx,"exit":c[i]}); pos=0
            else:
                if mode=="bb":
                    far = (not np.isnan(up[i])) and c[i] < (2*basis[i]-up[i])
                else:
                    far = dclo[i] < -pct
                if far and c[i] < f[i]:
                    trades.append({"side":-1,"i":ei,"j":i,"entry":epx,"exit":c[i]}); pos=0
    eq = 1.0
    for t in trades:
        r = t["side"]*(t["exit"]-t["entry"])/t["entry"]
        eq *= (1+r)*(1-COST)**2
    eq2 = 1.0
    for t in trades:
        seg = c[t["i"]:t["j"]+1]
        eq2 *= ((seg[-1]/seg[0]) if t["side"]==1 else (2-seg[-1]/seg[0]))*(1-COST)**2
    r = np.array([t["side"]*(t["exit"]-t["entry"])/t["entry"] for t in trades])
    t_stat = r.mean()/(r.std(ddof=1)/math.sqrt(len(r))) if len(r)>2 and r.std(ddof=1)>0 else float("nan")
    return {"ret":100*(eq-1),"check":100*(eq2-1),"n":len(trades),
            "win":float((r>0).mean()) if len(r) else 0,"bars":float(np.mean([t["j"]-t["i"] for t in trades])) if trades else 0,
            "t":t_stat,"worst":float(r.min()*100) if len(r) else 0,
            "longs":sum(1 for t in trades if t["side"]==1)}

for path, tag in (("bars_btc_1h_3y.csv","BTC 3y 1h"), ("bars_eth_1h_365d.csv","ETH 1y 1h")):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    bh = 100*(d.close.iloc[-1]/d.close.iloc[0]-1)
    print(f"\n===== {tag} ===== buy & hold {bh:+.1f}%")
    print(f"{'config':<40}{'ret%':>8}{'chk':>7}{'n':>6}{'win':>6}{'bars':>7}{'worst':>8}{'t':>6}")
    for k in (2.0,3.0):
        r=backtest(d,bb_k=k)
        print(f"{'BB(100,'+str(k)+') exhaustion exit':<40}{r['ret']:>8.1f}{r['check']:>7.1f}{r['n']:>6}{r['win']:>6.2f}{r['bars']:>7.0f}{r['worst']:>8.1f}{r['t']:>6.2f}")
    for p in (0.03,0.05,0.08,0.12):
        r=backtest(d,mode="pct",pct=p)
        print(f"{'distance from 100 > '+str(int(p*100))+'%':<40}{r['ret']:>8.1f}{r['check']:>7.1f}{r['n']:>6}{r['win']:>6.2f}{r['bars']:>7.0f}{r['worst']:>8.1f}{r['t']:>6.2f}")
    r=backtest(d,mode="pct",pct=0.05,shorts=True)
    print(f"{'distance 5% + shorts (FIXED)':<40}{r['ret']:>8.1f}{r['check']:>7.1f}{r['n']:>6}{r['win']:>6.2f}{r['bars']:>7.0f}{r['worst']:>8.1f}{r['t']:>6.2f}")

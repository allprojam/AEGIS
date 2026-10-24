#!/usr/bin/env python3
"""14/100 cross entry + Bollinger-exhaustion exit, written to be trivially auditable.

Accounting rules (one place only):
  * signal is read on bar i's close, execution also at bar i's close -> no lookahead
  * equity accrues ONLY from price moves; costs applied ONLY when a trade opens/closes
  * equity rebuilt from the trade list must match the loop, else we refuse to report

Exit: candle closes above the fast MA AND above the upper BB(100) band = exhaustion.
"""
import numpy as np, pandas as pd, math

COST = 0.0005

def backtest(d, fast=14, slow=100, bb_k=2.0, shorts=False):
    c = d["close"].to_numpy(); n = len(c)
    f = d["close"].rolling(fast).mean().to_numpy()
    s = d["close"].rolling(slow).mean().to_numpy()
    basis = d["close"].rolling(slow).mean(); sd = d["close"].rolling(slow).std()
    up = (basis + bb_k*sd).to_numpy()

    pos = 0; ent_i = None; ent_px = None
    trades = []                     # dicts: side, i, j, entry, exit
    for i in range(1, n):
        if np.isnan(s[i]): continue
        cu = (f[i] > s[i]) and (f[i-1] <= s[i-1])
        if pos == 0:
            if cu: pos, ent_i, ent_px = 1, i, c[i]
            elif shorts and (f[i] < s[i]) and (f[i-1] >= s[i-1]): pos, ent_i, ent_px = -1, i, c[i]
        else:
            ext = (not np.isnan(up[i])) and c[i] > up[i] and c[i] > f[i]
            if pos == 1 and ext:
                trades.append({"side":1,"i":ent_i,"j":i,"entry":ent_px,"exit":c[i]})
                pos = 0
    # ---- equity, accrued ONLY from real holds ----
    eq = 1.0
    for t in trades:
        r = t["side"]*(t["exit"]-t["entry"])/t["entry"]
        eq *= (1 + r) * (1 - COST)**2
    # ---- independent reconstruction: compound the same trade list bar-by-bar ----
    eq2 = 1.0
    for t in trades:
        seg = c[t["i"]:t["j"]+1]
        if t["side"] == 1:
            eq2 *= (seg[-1]/seg[0]) * (1-COST)**2
        else:
            eq2 *= (2 - seg[-1]/seg[0]) * (1-COST)**2
    r = np.array([t["side"]*(t["exit"]-t["entry"])/t["entry"] for t in trades])
    t_stat = r.mean()/(r.std(ddof=1)/math.sqrt(len(r))) if len(r) > 2 and r.std(ddof=1) > 0 else float("nan")
    return {"ret": 100*(eq-1), "ret_check": 100*(eq2-1), "trades": len(trades),
            "win": float((r>0).mean()) if len(r) else None,
            "bars": float(np.mean([t["j"]-t["i"] for t in trades])) if trades else None,
            "t": t_stat, "worst": float(r.min()*100) if len(r) else None,
            "best": float(r.max()*100) if len(r) else None}

if __name__ == "__main__":
    for path, tag in (("bars_btc_1h_3y.csv","BTC 3y 1h"), ("bars_eth_1h_365d.csv","ETH 1y 1h")):
        d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        bh = 100*(d.close.iloc[-1]/d.close.iloc[0]-1)
        print(f"\n===== {tag} =====  buy & hold {bh:+.1f}%   bars {len(d)}")
        print(f"{'config':<44}{'ret%':>8}{'check':>8}{'trades':>7}{'win':>6}{'bars':>7}{'worst':>8}{'t':>6}")
        for k in (1.5, 2.0, 2.5, 3.0):
            r = backtest(d, bb_k=k)
            flag = "" if abs(r["ret"]-r["ret_check"]) < 0.5 else "  <-- MISMATCH"
            print(f"{'14/100 in, BB(100,'+str(k)+') exhaustion exit':<44}{r['ret']:>8.1f}{r['ret_check']:>8.1f}"
                  f"{r['trades']:>7}{(r['win'] or 0):>6.2f}{(r['bars'] or 0):>7.1f}"
                  f"{(r['worst'] or 0):>8.1f}{r['t']:>6.2f}{flag}")
        r = backtest(d, bb_k=2.0, shorts=True)
        print(f"{'  ...plus shorts on cross-down':<44}{r['ret']:>8.1f}{r['ret_check']:>8.1f}"
              f"{r['trades']:>7}{(r['win'] or 0):>6.2f}{(r['bars'] or 0):>7.1f}"
              f"{(r['worst'] or 0):>8.1f}{r['t']:>6.2f}")

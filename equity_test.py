#!/usr/bin/env python3
"""Equities, DAILY bars, total-return adjusted (splits + dividends).
Two questions:
  A) Does the regime gate beat buy & hold? On daily bars a switch costs ~5bps and happens
     ~1-2x per YEAR, so fees are negligible here -- this is the fair test the 1h crypto
     data could not give us.
  B) Does the crypto entry model E2 (14/100 reclaim + BB exhaustion) transfer to equities?
No lookahead: signal on bar i close, position from bar i+1.
"""
import numpy as np, pandas as pd, math
import verify_e2 as V

DAY_FEE = 5.0     # bps per switch

def gate(d, regime_len=200, slope=0, cost_bps=DAY_FEE):
    c = d.close.to_numpy(); n = len(c)
    ret = np.zeros(n); ret[1:] = c[1:]/c[:-1]-1
    reg = d.close.rolling(regime_len).mean().to_numpy()
    on = (c > reg) & ~np.isnan(reg)
    if slope:
        r = np.zeros(n, bool); r[slope:] = reg[slope:] > reg[:-slope]; on = on & r
    pos=0; eq=1.0; sw=0; bars=0
    for i in range(1, n):
        want = on[i-1]
        if want and pos==0: pos=1; sw+=1; eq*=(1-cost_bps/10000)
        elif not want and pos==1: pos=0; sw+=1; eq*=(1-cost_bps/10000)
        if pos: eq*=(1+ret[i]); bars+=1
    return {"ret":100*(eq-1), "switches":sw, "exposure":100*bars/(n-1)}

def e2(d, fast=14, slow=100, bb_k=2.0):
    if len(d) < slow*3: return None
    ent, ext, f = V.signals(d, fast=fast, slow=slow, bb_k=bb_k)
    eq, tr = V.method_trades(d, ent, ext)
    c = d.close.to_numpy()
    if len(tr) < 3: return {"ret":100*(eq-1),"n":len(tr),"t":float('nan'),"win":None}
    r = np.array([c[j]/c[i]-1 for i,j in tr])
    t = r.mean()/(r.std(ddof=1)/math.sqrt(len(r))) if r.std(ddof=1)>0 else float('nan')
    return {"ret":100*(eq-1),"n":len(tr),"t":t,"win":float((r>0).mean()),
            "bars":float(np.mean([j-i for i,j in tr]))}

if __name__ == "__main__":
    for f, tag in (("bars_spx_1d.csv","S&P 500"),("bars_tsla_1d.csv","TSLA"),("bars_googl_1d.csv","GOOGL")):
        d = pd.read_csv(f).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        d["dt"] = pd.to_datetime(d.time, unit="s")
        n = len(d)
        y0, y1 = d.dt.iloc[0].year, d.dt.iloc[-1].year
        bh = 100*(d.close.iloc[-1]/d.close.iloc[0]-1)
        rec = d.iloc[max(0,n-2520):].reset_index(drop=True)   # last ~10y
        bh_rec = 100*(rec.close.iloc[-1]/rec.close.iloc[0]-1)
        print(f"\n########## {tag}  {n} daily bars  {y0}-{y1} ##########")
        print(f"buy & hold FULL {bh:+,.0f}%   LAST 10Y {bh_rec:+,.0f}%")
        print(f"\n  --- A) regime gate, FULL series (fee {DAY_FEE}bps/switch) ---")
        print(f"  {'filter':<22}{'ret%':>12}{'vs B&H':>12}{'switch':>8}{'expo%':>7}{'sw/yr':>7}")
        for rl, sp in ((200,0),(200,20),(200,50),(100,0),(50,0)):
            r = gate(d, rl, sp)
            yrs = (d.time.iloc[-1]-d.time.iloc[0])/86400/365.25
            print(f"  {'SMA'+str(rl)+(f'+slope{sp}' if sp else ''):<22}{r['ret']:>12,.0f}"
                  f"{r['ret']-bh:>+12,.0f}{r['switches']:>8}{r['exposure']:>7.0f}{r['switches']/yrs:>7.1f}")
        print(f"\n  --- A2) regime gate, LAST 10Y ---")
        for rl, sp in ((200,0),(200,20),(200,50)):
            r = gate(rec, rl, sp)
            print(f"  {'SMA'+str(rl)+(f'+slope{sp}' if sp else ''):<22}{r['ret']:>12,.0f}"
                  f"{r['ret']-bh_rec:>+12,.0f}{r['switches']:>8}{r['exposure']:>7.0f}")
        print(f"\n  --- B) E2 crypto entry model on daily equities ---")
        for lab, dd, bb in (("FULL", d, bh), ("LAST 10Y", rec, bh_rec)):
            r = e2(dd)
            if r: print(f"  E2 {lab:<10} ret {r['ret']:>10,.0f}%  vs B&H {r['ret']-bb:>+10,.0f}%  "
                        f"n={r['n']:<4} win={(r.get('win') or 0):.2f}  t={r['t']:>5.2f}")

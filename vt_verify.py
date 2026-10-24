#!/usr/bin/env python3
"""Verify the volatility-targeting result. Suspicion: leverage 1.0-1.5x may be carrying it,
which is NOT the same edge as better timing -- it is beta with borrowed money.
Also test with NO leverage (cap 1.0) and per-decade, to check robustness."""
import numpy as np, pandas as pd
from macro_timing import load, stats

spx = load("bars_spx_fresh_1d.csv"); vix = load("bars_vix_1d.csv")
df = pd.DataFrame({"spx":spx,"vix":vix}).dropna()
r = df.spx.pct_change().fillna(0).to_numpy(); n=len(df)
rv = pd.Series(r).rolling(20).std().to_numpy()*np.sqrt(252)

def run(exp, ret=r, nn=None):
    exp=np.nan_to_num(np.asarray(exp,float)); e=exp*ret
    ee=(1+e).cumprod(); pk=np.maximum.accumulate(ee)
    return 100*(ee[-1]-1), 100*((ee-pk)/pk).min(), np.mean(e)/np.std(e)*np.sqrt(252)

print("=== the leverage question: cap exposure at 1.0 (no borrowing) ===")
print(f"{'config':<26}{'total%':>10}{'maxDD%':>9}{'Sharpe':>8}{'ret/DD':>8}{'avg expo':>9}")
bh_tot,bh_dd,bh_sh = run(np.ones(n))
print(f"{'buy & hold':<26}{bh_tot:>10,.0f}{bh_dd:>9.1f}{bh_sh:>8.2f}{bh_tot/abs(bh_dd):>8.2f}{1.00:>9.2f}")
for cap,w in ((1.5,20),(1.0,20),(1.0,60),(1.0,120),(0.8,60)):
    rvw = pd.Series(r).rolling(w).std().to_numpy()*np.sqrt(252)
    exp = np.clip(0.15/np.roll(rvw,1), 0, cap); exp[0]=0
    t,d,s = run(exp)
    print(f"{'vol target 15%, cap '+str(cap)+', w'+str(w):<26}{t:>10,.0f}{d:>9.1f}{s:>8.2f}{t/abs(d):>8.2f}{np.nanmean(exp):>9.2f}")

print("\n=== per-decade robustness (cap 1.0, no leverage, 60d) ===")
exp = np.clip(0.15/np.roll(pd.Series(r).rolling(60).std().to_numpy()*np.sqrt(252),1),0,1.0); exp[0]=0
df2 = df.copy(); df2["strat"]=exp*r; df2["bh"]=r
df2["dec"]=(df2.index.year//10)*10
print(f"{'decade':<10}{'B&H ret%':>10}{'strat ret%':>12}{'B&H DD%':>10}{'strat DD%':>11}{'Sharpe BH':>11}{'Sharpe st':>10}")
for dec, g in df2.groupby("dec"):
    if len(g)<500: continue
    b=(1+g.bh).cumprod(); s=(1+g.strat).cumprod()
    bd=100*((b/np.maximum.accumulate(b))-1).min(); sd=100*((s/np.maximum.accumulate(s))-1).min()
    print(f"{dec}s     {100*(b.iloc[-1]-1):>10.0f}{100*(s.iloc[-1]-1):>12.0f}{bd:>10.1f}{sd:>11.1f}"
          f"{np.mean(g.bh)/np.std(g.bh)*np.sqrt(252):>11.2f}{np.mean(g.strat)/np.std(g.strat)*np.sqrt(252):>10.2f}")

#!/usr/bin/env python3
"""The real case for bonds is DIVERSIFICATION, not return. Test it honestly.
Does a bond sleeve actually protect an equity portfolio -- and did it work in 2022?"""
import numpy as np, pandas as pd

def load(f):
    d=pd.read_csv(f).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"]=pd.to_datetime(d.time,unit="s")
    return d.set_index("dt")["close"]

spx=load("bars_spx_1d.csv"); agg=load("bars_bond_agg_1d.csv"); tlt=load("bars_bond_tlt_1d.csv")
shy=load("bars_bond_shy_1d.csv")
df=pd.DataFrame({"spx":spx,"agg":agg,"tlt":tlt,"shy":shy}).dropna()
r=df.pct_change().dropna()
print(f"common window {df.index[0].date()} -> {df.index[-1].date()}  ({len(df)} days)\n")

print("=== correlation of DAILY returns with the S&P 500 ===")
for c in ("agg","tlt","shy"):
    print(f"  SPX vs {c.upper()}:  full-period {r.spx.corr(r[c]):+.3f}", end="")
    for y in (2008,2020,2022):
        s=r[r.index.year==y]
        if len(s)>50: print(f"   {y}: {s.spx.corr(s[c]):+.3f}", end="")
    print()

print("\n=== did diversification work in the bad years? ===")
print(f"{'year':>6}{'SPX%':>9}{'AGG%':>9}{'TLT%':>9}{'SHY%':>9}   note")
for y in (2008,2013,2018,2020,2021,2022,2023,2024,2025):
    s=df[df.index.year==y]
    if len(s)<50: continue
    v={c:100*(s[c].iloc[-1]/s[c].iloc[0]-1) for c in df.columns}
    note = "BOTH FELL" if v["spx"]<0 and v["agg"]<0 else ("diversified" if v["spx"]<0 else "")
    print(f"{y:>6}{v['spx']:>9.1f}{v['agg']:>9.1f}{v['tlt']:>9.1f}{v['shy']:>9.1f}   {note}")

print("\n=== 60/40 (SPX/AGG), annual rebalance, same window ===")
yrs=df.index.year.unique()
def backtest(w_spx, w_bond, bond="agg"):
    eq=1.0; vals=[]
    for y in yrs:
        s=df[df.index.year==y]
        if len(s)<50: continue
        rs=s["spx"].pct_change().fillna(0).to_numpy()
        rb=s[bond].pct_change().fillna(0).to_numpy()
        port=w_spx*rs+w_bond*rb
        eq*=float(np.prod(1+port)); vals.append(eq)
    return eq, np.array(vals)
for name,ws,wb,bo in (("100% SPX",1.0,0.0,"agg"),("60/40 SPX/AGG",0.6,0.4,"agg"),
                      ("60/40 SPX/TLT",0.6,0.4,"tlt"),("80/20 SPX/AGG",0.8,0.2,"agg"),
                      ("100% AGG",0.0,1.0,"agg"),("100% SHY",0.0,1.0,"shy")):
    eq,vals=backtest(ws,wb,bo)
    # max drawdown on the annual equity path is too coarse; use daily for the mixes
    port_r=None
    for y in yrs:
        s=df[df.index.year==y]
        if len(s)<50: continue
        pr=ws*s["spx"].pct_change().fillna(0)+wb*s[bo].pct_change().fillna(0)
        port_r = pr if port_r is None else pd.concat([port_r,pr])
    e=(1+port_r).cumprod(); pk=e.cummax()
    dd=100*((e-pk)/pk).min()
    print(f"  {name:<16} total {100*(eq-1):>7.0f}%   maxDD {dd:>6.1f}%   return/DD {100*(eq-1)/abs(dd):>5.2f}")

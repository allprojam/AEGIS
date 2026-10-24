#!/usr/bin/env python3
"""Bond indexes: are they actually 'safe'? Total-return data (dividend adjusted).
Validated against KNOWN published returns (TLT 2022 ~ -31%, AGG 2022 ~ -13%)."""
import numpy as np, pandas as pd
import equity_test as ET

FILES=[("bars_bond_agg_1d.csv","AGG  Agg US Bond"),
       ("bars_bond_bnd_1d.csv","BND  Vang Total Bond"),
       ("bars_bond_tlt_1d.csv","TLT  20yr+ Treasury"),
       ("bars_bond_ief_1d.csv","IEF  7-10yr Treasury"),
       ("bars_bond_shy_1d.csv","SHY  1-3yr Treasury"),
       ("bars_bond_lqd_1d.csv","LQD  IG Corporate"),
       ("bars_bond_tip_1d.csv","TIP  TIPS")]

def maxdd(eq):
    pk = np.maximum.accumulate(eq)
    return float(((eq-pk)/pk).min()*100)

print("=== VALIDATION vs known published 2022 returns (worst bond year on record) ===")
print(f"{'fund':<24}{'2022 ret%':>11}")
for f,tag in FILES:
    d=pd.read_csv(f); d["dt"]=pd.to_datetime(d.time,unit="s")
    y=d[d.dt.dt.year==2022]
    if len(y)>1:
        r=100*(y.close.iloc[-1]/y.close.iloc[0]-1)
        print(f"{tag:<24}{r:>+11.1f}")

print(f"\n=== FULL HISTORY, total return ===")
print(f"{'fund':<24}{'bars':>6}{'years':>7}{'CAGR%':>8}{'maxDD%':>8}{'worst yr':>10}{'worst%':>8}{'vol%':>7}")
rows=[]
for f,tag in FILES:
    d=pd.read_csv(f).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"]=pd.to_datetime(d.time,unit="s")
    c=d.close.to_numpy(); n=len(c)
    yrs=(d.time.iloc[-1]-d.time.iloc[0])/86400/365.25
    cagr=100*((c[-1]/c[0])**(1/yrs)-1)
    dd=maxdd(c)
    d["yr"]=d.dt.dt.year
    yrret=d.groupby("yr").close.apply(lambda s:100*(s.iloc[-1]/s.iloc[0]-1))
    lr=np.diff(np.log(c))
    vol=100*lr.std()*np.sqrt(252)
    rows.append((tag,cagr,dd,yrret.idxmin(),yrret.min(),vol,yrs,len(d)))
    print(f"{tag:<24}{len(d):>6}{yrs:>7.1f}{cagr:>8.2f}{dd:>8.1f}{yrret.idxmin():>10}{yrret.min():>8.1f}{vol:>7.2f}")

print(f"\n=== recovery from the 2021-2023 bond bear ===")
for f,tag in FILES:
    d=pd.read_csv(f).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"]=pd.to_datetime(d.time,unit="s")
    c=d.close.to_numpy(); pk=np.maximum.accumulate(c)
    i=int(np.argmax(pk/c))            # deepest point
    peakv=pk[i]
    back=np.where(c[i:]>=peakv)[0]
    status = (f"recovered {pd.to_datetime(d.time.iloc[i+back[0]],unit='s').date()}" if len(back)
              else f"STILL {100*(c[-1]/peakv-1):+.1f}% below its peak")
    print(f"  {tag:<24} trough {pd.to_datetime(d.time.iloc[i],unit='s').date()} "
          f"({100*(c[i]/peakv-1):+.1f}% from peak)  -> {status}")

#!/usr/bin/env python3
"""Is the variance risk premium real, and how bad is the tail?
VRP = implied vol (DVOL) - subsequently REALIZED vol. Positive on average = the premium
that short-vol harvests. The tail is the cases where realized >> implied.
Free public data: Deribit DVOL + BTC perpetual. No lookahead: IV at t vs RV over t..t+30.
"""
import json, urllib.request, time, datetime as dt
import numpy as np

def get(u):
    req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req,timeout=30).read().decode())

start=int(dt.datetime(2023,1,1,tzinfo=dt.timezone.utc).timestamp()*1000)
now=int(time.time()*1000)
iv=get(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC"
       f"&start_timestamp={start}&end_timestamp={now}&resolution=1D")["result"]["data"]
px=get(f"https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name=BTC-PERPETUAL"
       f"&start_timestamp={start}&end_timestamp={now}&resolution=1D")["result"]

d={int(r[0]//86400000): r[4]/100 for r in iv}          # day -> implied vol
p={int(t//86400000): c for t,c in zip(px["ticks"], px["close"])}   # ticks are ms
days=sorted(set(d)&set(p))
print(f"DVOL days {len(d)}  price days {len(p)}  overlap {len(days)}")
lo,hi=dt.datetime.fromtimestamp(days[0]*86400,dt.timezone.utc).date(), dt.datetime.fromtimestamp(days[-1]*86400,dt.timezone.utc).date()
print(f"overlap window {lo} -> {hi}\n")

# realized vol over the NEXT 30 days, annualised
rets={dd: None for dd in days}
cl=np.array([p[dd] for dd in days])
logr=np.diff(np.log(cl))
H=30
recs=[]
for i in range(len(days)-H):
    rv=np.std(logr[i:i+H], ddof=1)*np.sqrt(365)
    ivv=d[days[i]]
    recs.append((days[i], ivv, rv))
iv_a=np.array([r[1] for r in recs]); rv_a=np.array([r[2] for r in recs])
vrp=iv_a-rv_a
print(f"n={len(recs)}  implied mean {iv_a.mean():.3f}   realized mean {rv_a.mean():.3f}")
print(f"VRP (IV-RV):  mean {vrp.mean():+.4f}   median {np.median(vrp):+.4f}   std {vrp.std():.4f}")
print(f"IV > RV in {100*(vrp>0).mean():.1f}% of months")
print(f"ratio RV/IV mean {np.mean(rv_a/iv_a):.3f}  (>1 = seller loses)")

# the TAIL -- this is the part that matters
print(f"\n--- TAIL: worst 8 periods for a short-vol seller (RV - IV, annualised vol points) ---")
worst=np.argsort(vrp)[:8]
for i in worst:
    dd=dt.datetime.fromtimestamp(recs[i][0]*86400,dt.timezone.utc).date()
    print(f"  {dd}  implied {iv_a[i]:.2f}  realized {rv_a[i]:.2f}  gap {vrp[i]:+.2f}  "
          f"RV/IV {rv_a[i]/iv_a[i]:.2f}x")
print(f"\nworst single period: implied {iv_a[worst[0]]:.2f} vs realized {rv_a[worst[0]]:.2f} "
      f"-- a {rv_a[worst[0]]/iv_a[worst[0]]:.1f}x understatement of risk")
print(f"if a short-vol book were sized to that implied level, that month loses "
      f"~{100*(rv_a[worst[0]]**2-iv_a[worst[0]]**2)/iv_a[worst[0]]**2:.0f}% in variance terms")

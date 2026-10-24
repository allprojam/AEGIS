#!/usr/bin/env python3
"""Daily equity bars from Yahoo chart API, SPLIT AND DIVIDEND ADJUSTED.
Unadjusted data would inject fake -80% candles at splits (TSLA 5:1 in 2020, 3:1 in 2022)
and destroy any backtest, so OHLC is rescaled by adjclose/close per bar.
usage: fetch_stocks.py SYMBOL OUT.csv
"""
import json, sys, urllib.request, urllib.parse, csv
sym, out = sys.argv[1], sys.argv[2]
import time as _t
# NOTE: range=max silently returns MONTHLY bars from Yahoo. Explicit epoch bounds
# are required to get true daily bars. Verified: 4091 daily vs 197 monthly for TSLA.
url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
       f"?period1=0&period2={int(_t.time())}&interval=1d&events=div%2Csplit")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
j = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
res = j["chart"]["result"][0]
ts = res["timestamp"]
q = res["indicators"]["quote"][0]
adj = res["indicators"]["adjclose"][0]["adjclose"]
rows = []
for i, t in enumerate(ts):
    o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
    a = adj[i]
    if None in (o, h, l, c, a) or c == 0: continue
    k = a / c                                  # adjustment factor
    rows.append([t, o*k, h*k, l*k, a, q["volume"][i] or 0])
rows.sort(key=lambda r: r[0])
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["time","open","high","low","close","volume"])
    for r in rows: w.writerow([int(r[0]), f"{r[1]:.6f}", f"{r[2]:.6f}", f"{r[3]:.6f}", f"{r[4]:.6f}", r[5]])
import datetime as dt
print(f"{sym}: {len(rows)} daily bars -> {out}  "
      f"{dt.datetime.fromtimestamp(rows[0][0],dt.timezone.utc).date()} -> "
      f"{dt.datetime.fromtimestamp(rows[-1][0],dt.timezone.utc).date()}  "
      f"last close {rows[-1][4]:.2f}")

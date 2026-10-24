import csv, json, time, datetime as dt, urllib.request
END = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
END = END - dt.timedelta(minutes=END.minute % 5)
DAYS, G = 180, 300
rows, end = [], END
while (END - end).days < DAYS:
    start = end - dt.timedelta(seconds=G * 300)
    url = (f"https://api.exchange.coinbase.com/products/BTC-USD/candles"
           f"?granularity={G}&start={start.isoformat()}&end={end.isoformat()}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print("err", str(e)[:70]); time.sleep(2); continue
    for t, lo, hi, op, cl, vol in data:
        rows.append([t, op, hi, lo, cl, vol])
    end = start
    time.sleep(0.25)
rows = {r[0]: r for r in rows}
rows = [rows[k] for k in sorted(rows)]
with open("bars_btc_5m_180d.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["time","open","high","low","close","volume"]); w.writerows(rows)
print("wrote", len(rows), "bars:", dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc).isoformat(),
      "->", dt.datetime.fromtimestamp(rows[-1][0], dt.timezone.utc).isoformat())

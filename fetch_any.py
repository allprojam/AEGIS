#!/usr/bin/env python3
"""Fetch Coinbase candles at any granularity: fetch_any.py <PRODUCT> <GRANULARITY> <DAYS> <OUT>"""
import csv, json, sys, time, datetime as dt, urllib.request
prod, g, days, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
per = int(g * 300)
end = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
end -= dt.timedelta(minutes=end.minute % max(1, g // 60))
rows, cur = [], end
while (end - cur).days < days:
    start = cur - dt.timedelta(seconds=per)
    url = (f"https://api.exchange.coinbase.com/products/{prod}/candles"
           f"?granularity={g}&start={start.isoformat()}&end={cur.isoformat()}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode())
        rows += [[t, op, hi, lo, cl, v] for t, lo, hi, op, cl, v in data]
    except Exception as e:
        print("err", str(e)[:70]); time.sleep(2)
    cur = start
    time.sleep(0.25)
d = {r[0]: r for r in rows}
rows = [d[k] for k in sorted(d)]
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["time","open","high","low","close","volume"]); w.writerows(rows)
print(f"wrote {len(rows)} bars to {out}: {dt.datetime.fromtimestamp(rows[0][0],dt.timezone.utc)} -> {dt.datetime.fromtimestamp(rows[-1][0],dt.timezone.utc)}")

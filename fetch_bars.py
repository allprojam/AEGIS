import csv, json, sys
sys.path.insert(0,"/root/agency_bot/workspace")
import tv_client as tv
d = json.loads(tv.call("data_get_ohlcv", {"count":500}))
bars = d.get("bars") or d.get("data") or []
print("keys:", list(d.keys())[:8], "| bars:", len(bars))
if not bars:
    print(json.dumps(d)[:400]); raise SystemExit
rows = []
for b in bars:
    if isinstance(b, dict):
        rows.append([b.get("time"), b.get("open"), b.get("high"), b.get("low"), b.get("close"), b.get("volume")])
    else:
        rows.append(list(b)[:6])
with open("bars_ethusd_5m.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["time","open","high","low","close","volume"]); w.writerows(rows)
print("wrote bars_ethusd_5m.csv", len(rows), "rows")
print("first:", rows[0]); print("last :", rows[-1])

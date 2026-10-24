import csv, json, sys, time, urllib.request
sys.path.insert(0,"/root/agency_bot/workspace")
import tv_client as tv

d = json.loads(tv.call("data_get_ohlcv", {"count":20}))
print("TV ohlcv source field:", d.get("source"), "| bar_count:", d.get("bar_count"), "| total_available:", d.get("total_available"))
tvlast = d["bars"][-3:]
for b in tvlast: print("  TV  ", b)

url="https://api.exchange.coinbase.com/products/ETH-USD/candles?granularity=300"
req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    cb=json.loads(r.read().decode())
cb=sorted(cb, key=lambda x:x[0])
print("coinbase bars:", len(cb))
for row in cb[-3:]:
    t,lo,hi,op,cl,vol = row
    print("  CB  ", {"time":t,"open":op,"high":hi,"low":lo,"close":cl,"volume":vol})

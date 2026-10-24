import json, urllib.request, datetime as dt
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(r,timeout=60).read().decode())
now=int(dt.datetime.now().timestamp())
pairs={"EUR":"EURUSD=X","GBP":"GBPUSD=X","AUD":"AUDUSD=X","NZD":"NZDUSD=X",
       "JPY":"USDJPY=X","CHF":"USDCHF=X","CAD":"USDCAD=X","NOK":"NOKUSD=X","SEK":"SEKUSD=X"}
for cur,sym in pairs.items():
    try:
        j=g(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2={now}&interval=1d")
        r=j["chart"]["result"][0]
        rows=[(t,v) for t,v in zip(r["timestamp"],r["indicators"]["quote"][0]["close"]) if v]
        with open(f"fx/daily_{cur}.csv","w") as f:
            f.write("time,close\n")
            for t,v in rows: f.write(f"{t},{v}\n")
        print(f"OK {cur} {len(rows)}", flush=True)
    except Exception as e:
        print(f"FAIL {cur} {str(e)[:50]}", flush=True)
print("DONE", flush=True)

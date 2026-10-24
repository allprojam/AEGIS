import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0x53da461898c40466e84ad6be7d53cdf360eeeaed"
for tf,lim in (("day",100),("hour",1000)):
    for att in range(6):
        try:
            j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/pools/{P}/ohlcv/{tf}?limit={lim}&currency=usd")
            lst=j["data"]["attributes"]["ohlcv_list"]
            with open(f"apsis/ohlcv_{tf}.csv","w",newline="") as f:
                w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
            print(f"OK {tf} {len(lst)}",flush=True); break
        except Exception as e:
            print(f"  {tf} att{att} {str(e)[:40]}",flush=True); time.sleep(20)
    time.sleep(12)
print("DONE",flush=True)

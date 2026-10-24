import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0x975f0369d31f1dd79abf057ad369ae7d5b9f6fb4"   # CDP/USDt0 0.05%
for tf,lim in (("day",100),):
    for att in range(8):
        try:
            j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/pools/{P}/ohlcv/{tf}?limit={lim}&currency=usd")
            lst=j["data"]["attributes"]["ohlcv_list"]
            with open(f"enosys/cdp_{tf}.csv","w",newline="") as f:
                w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
            print(f"OK CDP/USDt0 {tf} {len(lst)}",flush=True); break
        except Exception as e:
            print(f"  {tf} att{att} {str(e)[:38]}",flush=True); time.sleep(20)
    time.sleep(10)
print("DONE",flush=True)

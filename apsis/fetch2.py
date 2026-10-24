import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
APS="0xff56eb5b1a7faa972291117e5e9565da29bc808d"
for att in range(8):
    try:
        j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/tokens/{APS}")
        a=j["data"]["attributes"]
        print("TOKEN APS:",flush=True)
        for k in ("name","symbol","decimals","total_supply","price_usd","fdv_usd","total_reserve_in_usd"):
            print(f"  {k:<24} {a.get(k)}",flush=True)
        break
    except Exception as e:
        print(f"  att{att} {str(e)[:40]}",flush=True); time.sleep(20)
time.sleep(10)
for att in range(8):
    try:
        j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/tokens/{APS}/ohlcv/day?limit=100&currency=usd")
        lst=j["data"]["attributes"]["ohlcv_list"]
        with open("aps_token_day.csv","w",newline="") as f:
            w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
        print(f"OK aps_token_day {len(lst)}",flush=True); break
    except Exception as e:
        print(f"  ohlcv att{att} {str(e)[:40]}",flush=True); time.sleep(20)
print("DONE",flush=True)

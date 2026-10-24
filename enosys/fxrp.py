import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
j=g("https://api.geckoterminal.com/api/v2/networks/flare/pools?page=1")
for p in j.get("data",[]):
    a=p["attributes"]; nm=a.get("name","")
    if nm.startswith("FXRP") and float(a.get("reserve_in_usd") or 0)>1e6:
        pid=p["id"].split("_")[1]
        print(f"pool {nm} {pid}  ${float(a['reserve_in_usd']):,.0f}",flush=True)
        for att in range(6):
            try:
                o=g(f"https://api.geckoterminal.com/api/v2/networks/flare/pools/{pid}/ohlcv/day?limit=100&currency=usd")
                lst=o["data"]["attributes"]["ohlcv_list"]
                with open("enosys/fxrp_day.csv","w",newline="") as f:
                    w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
                print(f"OK {len(lst)}",flush=True); break
            except Exception as e:
                print(f"  att{att} {str(e)[:35]}",flush=True); time.sleep(18)
        break
print("DONE",flush=True)

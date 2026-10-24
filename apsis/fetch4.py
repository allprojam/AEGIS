import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
APS="0xff56eb5b1a7faa972291117e5e9565da29bc808d"
for att in range(8):
    try:
        j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/tokens/{APS}/pools?page=1")
        ps=j.get("data",[])
        # find pools where APS is the BASE token
        for p in ps:
            a=p["attributes"]
            nm=a.get("name","")
            if nm.startswith("APS"):
                print(f"POOL {nm}  id={p['id']}",flush=True)
                pid=p["id"].split("_",1)[1]
                for a2 in range(5):
                    try:
                        o=g(f"https://api.geckoterminal.com/api/v2/networks/flare/pools/{pid}/ohlcv/day?limit=100&currency=usd")
                        lst=o["data"]["attributes"]["ohlcv_list"]
                        with open("aps_price_day.csv","w",newline="") as f:
                            w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
                        print(f"  OK {len(lst)} candles",flush=True); break
                    except Exception as e:
                        print(f"  ohlcv att{a2} {str(e)[:38]}",flush=True); time.sleep(18)
                break
        break
    except Exception as e:
        print(f"  att{att} {str(e)[:40]}",flush=True); time.sleep(18)
print("DONE",flush=True)

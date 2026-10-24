import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P={"cbBTCWBTC":"0xd960B78f53e8A346c577F2C7b3f0a2394E73afb9",
   "wstETHWETH":"0xA6385c73961dd9C58db2EF0c4EB98cE4B60651e8",
   "cbETHWETH":"0x47cA96Ea59C13F72745928887f84C9F52C3D7348",
   "weETHWETH":"0x91F0f34916Ca4E2cCe120116774b0e4fA0cdcaA8"}
for name,addr in P.items():
    for att in range(6):
        try:
            j=g(f"https://api.geckoterminal.com/api/v2/networks/base/pools/{addr}/ohlcv/day?limit=100&currency=usd")
            lst=j["data"]["attributes"]["ohlcv_list"]
            with open(f"{name}_day.csv","w",newline="") as f:
                w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
            print(f"OK {name} {len(lst)}",flush=True); break
        except Exception as e:
            print(f"  {name} att{att} {str(e)[:40]}",flush=True); time.sleep(20)
    time.sleep(15)
print("DONE",flush=True)

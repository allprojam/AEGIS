import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
# pool metadata (fee tier) + more stable pools' daily volume
meta={"USDTUSDC_v4":"0xfba2c4592d32a4e2e6393b8898f9110b4e272983f4bd416b38f81672a17fe3dc"}
for name,addr in meta.items():
    for att in range(6):
        try:
            j=g(f"https://api.geckoterminal.com/api/v2/networks/base/pools/{addr}")
            a=j["data"]["attributes"]
            print(f"META {name}: name={a.get('name')} fee={a.get('pool_fee_percentage',a.get('fee_tier'))}",flush=True)
            print(f"     vol24={a.get('volume_usd',{})}",flush=True)
            break
        except Exception as e:
            print(f"  {name} att{att} {str(e)[:40]}",flush=True); time.sleep(18)
    time.sleep(10)
OTHER={
 "USDTUSDC_uni_A":"0xf13203ddbf2c9816a79b656a1a952521702715d92fea465b84ae2ed6e94a7f22",
 "USDTUSDC_uni_B":"0xD56da2B74bA826f19015E6B7Dd9Dae1903E85DA1",
 "USDTUSDC_quick":"0xd30B9fA98713425c0302593d7F8F094be31E9710",
 "USDTUSDC_uni_C":"0xe1d05fe2b899df927bc67e5eedaccb95d06bf7c769ed68469bb773615f2401f8",
 "USDCUSDbC_alien":"0x",
}
for name,addr in OTHER.items():
    if addr=="0x": continue
    for att in range(6):
        try:
            j=g(f"https://api.geckoterminal.com/api/v2/networks/base/pools/{addr}/ohlcv/day?limit=100&currency=usd")
            lst=j["data"]["attributes"]["ohlcv_list"]
            with open(f"{name}.csv","w",newline="") as f:
                w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
            print(f"OK {name} {len(lst)}",flush=True); break
        except Exception as e:
            print(f"  {name} att{att} {str(e)[:40]}",flush=True); time.sleep(18)
    time.sleep(12)
print("DONE",flush=True)

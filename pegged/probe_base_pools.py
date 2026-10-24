import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
POOLS={
 "USDTUSDC":"0xfba2c4592d32a4e2e6393b8898f9110b4e272983f4bd416b38f81672a17fe3dc",
 "cbBTCWBTC":"0x",  # resolve
 "wstETHWETH":"0x",
}
# resolve the evm-address ones via geckoterminal search
import urllib.parse
for name,q in (("cbBTCWBTC","cbBTC WBTC"),("wstETHWETH","wstETH WETH"),("cbETHWETH","cbETH WETH"),("weETHWETH","weETH WETH")):
    try:
        j=g("https://api.dexscreener.com/latest/dex/search?q="+urllib.parse.quote(q))
        cs=[p for p in j.get("pairs",[]) if p.get("chainId")=="base" and p.get("pairAddress","").startswith("0x") and len(p.get("pairAddress",""))==42]
        cs=[p for p in cs if (p.get("liquidity") or {}).get("usd",0)>50000]
        if cs:
            p=sorted(cs,key=lambda x:-((x.get("liquidity") or {}).get("usd",0)))[0]
            POOLS[name]=p["pairAddress"]
            print(f"  {name} -> {p['pairAddress']} ({p.get('dexId')}) TVL ${(p.get('liquidity') or {}).get('usd',0):,.0f}")
    except Exception as e: print(f"  {name} err {str(e)[:50]}")
    time.sleep(0.5)
print()
for name,addr in POOLS.items():
    if not addr or addr=="0x": continue
    try:
        j=g(f"https://api.geckoterminal.com/api/v2/networks/base/pools/{addr}/ohlcv/day?limit=100&currency=usd")
        lst=j["data"]["attributes"]["ohlcv_list"]
        with open(f"{name}_day.csv","w",newline="") as f:
            w=csv.writer(f); w.writerow(["ts","open","high","low","close","volume"]); w.writerows(lst)
        print(f"  {name}: {len(lst)} daily candles -> {name}_day.csv")
    except Exception as e:
        print(f"  {name} OHLCV FAIL {str(e)[:70]}")
    time.sleep(1.5)

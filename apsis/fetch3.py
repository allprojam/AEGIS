import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
APS="0xff56eb5b1a7faa972291117e5e9565da29bc808d"
# find pools where APS is base, to get its USD price history
for att in range(8):
    try:
        j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/tokens/{APS}/pools?page=1")
        ps=j.get("data",[])
        print(f"APS pools: {len(ps)}",flush=True)
        for p in ps:
            a=p["attributes"]
            print(f"  {a.get('name'):<28} reserve ${a.get('reserve_in_usd')}  vol24 {a.get('volume_usd',{}).get('h24')}",flush=True)
        break
    except Exception as e:
        print(f"  att{att} {str(e)[:40]}",flush=True); time.sleep(20)
time.sleep(12)
# also try dexscreener for flare
for att in range(4):
    try:
        j=g(f"https://api.dexscreener.com/latest/dex/tokens/{APS}")
        ps=[p for p in j.get("pairs",[]) if p.get("chainId")=="flare"]
        print(f"\nDexScreener flare pairs for APS: {len(ps)}",flush=True)
        for p in ps[:5]:
            print(f"  {p.get('baseToken',{}).get('symbol')}/{p.get('quoteToken',{}).get('symbol')} "
                  f"liq ${(p.get('liquidity') or {}).get('usd',0):,.0f} price ${p.get('priceUsd')}",flush=True)
        break
    except Exception as e:
        print(f"  ds att{att} {str(e)[:40]}",flush=True); time.sleep(15)
print("DONE",flush=True)

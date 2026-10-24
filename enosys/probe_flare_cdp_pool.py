import json,urllib.request,time
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0x975f0369d31f1dd79abf057ad369ae7d5b9f6fb4"   # CDP/USDt0 0.05%
def pool(pid):
    j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/pools/{pid}")
    return j["data"]["attributes"]
print("=== the CDP/USDt0 pool (where you'd actually buy) ===")
for att in range(5):
    try:
        a=pool(P)
        for k in ("name","base_token_price_usd","quote_token_price_usd","reserve_in_usd",
                  "pool_created_at"):
            if k in a: print(f"  {k:<26} {a[k]}")
        v=a.get("volume_usd",{})
        print(f"  volume 24h                 ${float(v.get('h24') or 0):,.0f}")
        print(f"  volume 6h                  ${float(v.get('h6') or 0):,.0f}")
        print(f"  volume 1h                  ${float(v.get('h1') or 0):,.0f}")
        tx=a.get("transactions",{}).get("h24",{})
        print(f"  txns 24h                   {tx}")
        break
    except Exception as e:
        print(f"  att{att} {str(e)[:45]}"); time.sleep(15)

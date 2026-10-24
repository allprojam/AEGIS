import json,urllib.request,time,sys
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0x53da461898c40466e84ad6be7d53cdf360eeeaed"
addrs={}
for att in range(6):
    try:
        j=g(f"https://api.geckoterminal.com/api/v2/networks/flare/pools/{P}")
        a=j["data"]["attributes"]
        print("POOL:", a.get("name"))
        print("  reserve_usd:", a.get("reserve_in_usd"))
        print("  vol:", a.get("volume_usd"))
        print("  created:", a.get("pool_created_at"))
        for inc in ("base_token","quote_token"):
            tid=j["data"]["relationships"].get(inc,{}).get("data",{}).get("id","")
            addrs[inc]="0x"+tid.split("_")[-1]
            print(f"  {inc}: {addrs[inc]}")
        break
    except Exception as e:
        print(f"  pool att{att} {str(e)[:40]}",flush=True); time.sleep(15)
time.sleep(8)
RPC="https://flare-api.flare.network/ext/C/rpc"
def call(to,data):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call",
        "params":[{"to":to,"data":data},"latest"]}).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=20).read().decode()).get("result","0x")
def sel(s): return "0x"+W3.keccak(text=s)[:4].hex()
for label,addr in addrs.items():
    print(f"\n=== {label} {addr} ===")
    for sig,kind in (("symbol()","str"),("decimal","u"),("decimals()","u"),("totalSupply()","u")):
        if sig=="decimal": continue
        try:
            h=call(addr,sel(sig))[2:]
            if kind=="str":
                off=int(h[0:64],16); ln=int(h[off*2:off*2+64],16)
                v=bytes.fromhex(h[off*2+64:off*2+64+ln*2]).decode()
            else:
                v=int(h,16) if h else None
            print(f"  {sig:<16} {v}")
        except Exception as e:
            print(f"  {sig:<16} ERR {str(e)[:40]}")
        time.sleep(1.5)
print("DONE",flush=True)

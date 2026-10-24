"""Read the LIVE StabilityPool behind the TransparentUpgradeableProxy."""
import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
RPC="https://flare-api.flare.network/ext/C/rpc"
def raw(to,data):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call",
        "params":[{"to":to,"data":data},"latest"]}).encode(),headers={"Content-Type":"application/json"})
    j=json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
    if "error" in j: raise RuntimeError(j["error"].get("message","err")[:60])
    return j.get("result","0x")
ABI=json.load(open("enosys/abi/StabilityPool.json"))
def get(fn,*args):
    f=next((a for a in ABI if a.get("type")=="function" and a.get("name")==fn),None)
    if not f: return "no such fn"
    sig=f"{fn}({','.join(i['type'] for i in f.get('inputs',[]))})"
    data="0x"+W3.keccak(text=sig)[:4].hex()
    for a in args: data+=a[2:].rjust(64,"0") if isinstance(a,str) else hex(a)[2:].rjust(64,"0")
    try: h=raw(SP,data)
    except Exception as e: return f"REVERT {str(e)[:35]}"
    if h in ("0x",""): return "empty"
    t=(f.get("outputs") or [{}])[0].get("type","")
    v=int(h,16)
    if t=="address": return "0x"+h[-40:]
    if t=="bool": return bool(v)
    if t=="string":
        off=int(h[0:64],16); ln=int(h[off*2:off*2+64],16)
        return bytes.fromhex(h[off*2+64:off*2+64+ln*2]).decode(errors="ignore")
    return v
SP="0x2c817F7159c08d94f09764086330c96Bb3265A2f"
def e18(x): return f"{x/1e18:,.4f} CDP" if isinstance(x,int) and x>1e15 else x
print("#"*72)
print("# LIVE StabilityPool (proxy) 0x2c817F7159c08d94f09764086330c96Bb3265A2f")
print("#"*72)
for fn,conv in (("NAME",None),("getTotalBoldDeposits",e18),("getCollBalance",None),
                ("boldToken",None),("collToken",None),("activePool",None),
                ("getTroveManager",None),("priceFeed",None),("owner",None),
                ("P",None),("currentScale",None),("getEntireBranchColl",e18),
                ("getEntireBranchDebt",e18)):
    v=get(fn)
    print(f"  {fn:<24} {conv(v) if conv and isinstance(v,int) else v}")
    time.sleep(0.5)
print("\n[ ActivePool via proxy? ]")
AP=get("activePool")
for fn in ("SP_YIELD_SPLIT","getBoldDebt","getCollBalance","stabilityPool"):
    print(f"  ActivePool.{fn:<20} {get(fn) if fn=='SP_YIELD_SPLIT' else ''}")
    break
print("DONE")

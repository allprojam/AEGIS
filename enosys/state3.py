"""Read Enosys Loans live state via raw eth_call + abi decode (no provider plumbing)."""
import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()   # no provider needed for encode/decode
RPC="https://flare-api.flare.network/ext/C/rpc"

def raw(to,data):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call",
        "params":[{"to":to,"data":data},"latest"]}).encode(),headers={"Content-Type":"application/json"})
    j=json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
    if "error" in j: raise RuntimeError(j["error"].get("message","rpc error")[:60])
    return j.get("result","0x")

ADDRS={"StabilityPool":"0x37FfD5d66Fb182493C315B8b8f1C9D67DcF95B18",
       "ActivePool":"0xfa88E9034b82e396bC40b4D22227b84e2a4546C1",
       "TroveManager":"0xf0C949513ff4ecFf1C0afC7c1966dCb8DfAC950b",
       "BorrowerOperations":"0x59a4c88A98F3b515aE041005206E74D0ddFb6cB1",
       "CollateralRegistry":"0x9cbB9b5376F2ecF281ff66BBA8fE2d70f48138F4"}
ABI={n:json.load(open(f"enosys/abi/{n}.json")) for n in ADDRS}

def get(n,fn):
    """encode -> call -> decode"""
    f=None
    for a in ABI[n]:
        if a.get("type")=="function" and a.get("name")==fn:
            f=a; break
    if f is None: return "no such fn"
    sel=W3.keccak(text=f"{fn}({','.join(i['type'] for i in f.get('inputs',[]))})")[:4].hex()
    try:
        h=raw(ADDRS[n],"0x"+sel)
    except Exception as e:
        return f"REVERT {str(e)[:40]}"
    outs=f.get("outputs",[])
    if not outs: return "(no return)"
    t=outs[0]["type"]
    if h in ("0x",""): return "empty"
    v=int(h,16)
    if t.startswith("uint") or t.startswith("int"):
        return v
    if t=="address": return "0x"+h[-40:]
    if t=="bool": return bool(v)
    return f"0x{h[-40:]}"

def fmt(x):
    if isinstance(x,int):
        if x>10**15: return f"{x}  ({x/1e18:,.4f} e18)"
        if x>10**6:  return f"{x}  ({x/1e6:,.2f} e6)"
    return x

groups=[
 ("StabilityPool — where the 75% yield goes",
  "StabilityPool", ("NAME","getTotalBoldDeposits","getCollBalance","getEntireBranchColl",
                    "getEntireBranchDebt","boldToken","collToken","activePool","getTroveManager")),
 ("ActivePool — yield routing",
  "ActivePool", ("SP_YIELD_SPLIT","getBoldDebt","getCollBalance","getEntireBranchColl",
                 "getEntireBranchDebt","interestRouter","stabilityPool","hasBeenShutDown")),
 ("TroveManager — risk parameters",
  "TroveManager", ("CCR","MCR","SCR","MIN_DEBT","LIQUIDATION_PENALTY_SP",
                   "LIQUIDATION_PENALTY_REDISTRIBUTION","URGENT_REDEMPTION_BONUS",
                   "getEntireBranchColl","getEntireBranchDebt","isPaused")),
 ("BorrowerOperations — caps & rates",
  "BorrowerOperations", ("CCR","MCR","SCR","BCR","MIN_ANNUAL_INTEREST_RATE","MAX_ANNUAL_INTEREST_RATE",
                         "MAX_DEBT_CAP","MAX_BRANCH_CAP","MIN_INTEREST_RATE_CHANGE_PERIOD","hasBeenShutDown")),
 ("CollateralRegistry — redemption fees",
  "CollateralRegistry", ("REDEMPTION_FEE_FLOOR","baseRate","totalCollaterals","boldToken")),
]
print("#"*72); print("# ENOSYS LOANS — LIVE PROTOCOL STATE (Flare mainnet)"); print("#"*72)
for title,contract,fns in groups:
    print(f"\n[ {title} ]")
    for fn in fns:
        print(f"  {fn:<34} {fmt(get(contract,fn))}")
        time.sleep(0.4)
print("\nDONE")

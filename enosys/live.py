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
ABIS={}
for n in ("StabilityPool","ActivePool","TroveManager","BorrowerOperations","CollateralRegistry"):
    ABIS[n]=json.load(open(f"enosys/abi/{n}.json"))
def get(contract,addr,fn,args=()):
    A=ABIS[contract]
    f=next((a for a in A if a.get("type")=="function" and a.get("name")==fn),None)
    if not f: return "no such fn"
    sig=f"{fn}({','.join(i['type'] for i in f.get('inputs',[]))})"
    data="0x"+W3.keccak(text=sig)[:4].hex()
    for a in args: data+=(a[2:].rjust(64,"0") if isinstance(a,str) else format(a,'064x'))
    try: h=raw(addr,data)
    except Exception as e: return f"REVERT {str(e)[:35]}"
    if h in ("0x",""): return "empty"
    t=(f.get("outputs") or [{}])[0].get("type","")
    v=int(h,16)
    if t=="address": return "0x"+h[-40:]
    if t=="bool": return bool(v)
    return v

SP="0x2c817F7159c08d94f09764086330c96Bb3265A2f"
AP="0x65c378bf4a68491436c84d8da020b14fefe03d17"
TM="0xc46e7d0538494feb82b460b9723daba0508c8fb1"
print("#"*74); print("# ENOSYS LOANS - LIVE FXRP BRANCH (Flare)"); print("#"*74)

print("\n[ ActivePool ]")
for fn in ("SP_YIELD_SPLIT","getBoldDebt","aggRecordedDebt","aggWeightedDebtSum",
           "aggWeightedBatchManagementFeeSum","calcPendingSPYield","calcPendingAggInterest",
           "lastAggUpdateTime","interestRouter","hasBeenShutDown","getCollBalance"):
    v=get("ActivePool",AP,fn)
    if isinstance(v,int) and v>10**15: v=f"{v}  ({v/1e18:,.4f} e18)"
    print(f"  {fn:<32} {v}"); time.sleep(0.4)

print("\n[ TroveManager - risk params (FXRP branch) ]")
for fn in ("CCR","MCR","SCR","MIN_DEBT","LIQUIDATION_PENALTY_SP","LIQUIDATION_PENALTY_REDISTRIBUTION",
           "URGENT_REDEMPTION_BONUS","getEntireBranchColl","getEntireBranchDebt","isPaused"):
    v=get("TroveManager",TM,fn)
    if isinstance(v,int) and 10**15<v<10**30: v=f"{v}  ({v/1e18:,.4f})"
    print(f"  {fn:<34} {v}"); time.sleep(0.4)

print("\n[ BorrowerOperations - caps & rates ]")
BO="0x59a4c88A98F3b515aE041005206E74D0ddFb6cB1"
for fn in ("MIN_ANNUAL_INTEREST_RATE","MAX_ANNUAL_INTEREST_RATE","MAX_DEBT_CAP","MAX_BRANCH_CAP"):
    v=get("BorrowerOperations",BO,fn)
    if isinstance(v,int) and v>10**15: v=f"{v}  ({v/1e18:,.6f})"
    print(f"  {fn:<32} {v}"); time.sleep(0.4)
print("DONE")

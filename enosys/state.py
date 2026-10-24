import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
RPC="https://flare-api.flare.network/ext/C/rpc"
def raw(to,data):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call",
        "params":[{"to":to,"data":data},"latest"]}).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode()).get("result","0x")

def mk(name):
    abi=json.load(open(f"enosys/abi/{name}.json"))
    return W3.eth.contract(abi=abi)

SP=mk("StabilityPool"); SPADDR="0x37FfD5d66Fb182493C315B8b8f1C9D67DcF95B18"
AP=mk("ActivePool");    APADDR="0xfa88E9034b82e396bC40b4D22227b84e2a4546C1"
TM=mk("TroveManager");  TMADDR="0xf0C949513ff4ecFf1C0afC7c1966dCb8DfAC950b"
BO=mk("BorrowerOperations"); BOADDR="0x59a4c88A98F3b515aE041005206E74D0ddFb6cB1"
CR=mk("CollateralRegistry"); CRADDR="0x9cbB9b5376F2ecF281ff66BBA8fE2d70f48138F4"

def callc(contract,addr,fn,*args):
    try:
        data=contract.encodeABI(fn_name=fn,args=list(args))
    except Exception as e:
        return f"ENCODE_ERR {str(e)[:40]}"
    h=raw(addr,data)
    if not h or h=="0x": return "revert"
    try:
        return contract.decode_function_result(fn_name=fn,data=h)
    except Exception:
        return "0x"+h[2:][-40:] if len(h)<=66 else int(h,16)

print("="*66)
print("ENOSYS LOANS — LIVE PROTOCOL STATE (Flare mainnet)")
print("="*66)

print("\n--- StabilityPool (where the 75% yield goes) ---")
for fn in ("getTotalBoldDeposits","getCollBalance","getEntireBranchColl","getEntireBranchDebt",
           "NAME","boldToken","collToken","getTroveManager","priceFeed","activePool"):
    print(f"  {fn:<26} {callc(SP,SPADDR,fn)}")
    time.sleep(0.6)

print("\n--- ActivePool (yield routing) ---")
for fn in ("SP_YIELD_SPLIT","getBoldDebt","getCollBalance","getEntireBranchColl","getEntireBranchDebt",
           "interestRouter","stabilityPool","hasBeenShutDown"):
    print(f"  {fn:<26} {callc(AP,APADDR,fn)}")
    time.sleep(0.6)

print("\n--- TroveManager (risk parameters) ---")
for fn in ("CCR","MCR","SCR","MIN_DEBT","LIQUIDATION_PENALTY_SP","LIQUIDATION_PENALTY_REDISTRIBUTION",
           "URGENT_REDEMPTION_BONUS","getEntireBranchColl","getEntireBranchDebt","isPaused"):
    print(f"  {fn:<34} {callc(TM,TMADDR,fn)}")
    time.sleep(0.6)

print("\n--- BorrowerOperations (limits) ---")
for fn in ("CCR","MCR","SCR","BCR","MIN_ANNUAL_INTEREST_RATE","MAX_ANNUAL_INTEREST_RATE",
           "MAX_DEBT_CAP","MAX_BRANCH_CAP","MIN_INTEREST_RATE_CHANGE_PERIOD","hasBeenShutDown"):
    print(f"  {fn:<30} {callc(BO,BOADDR,fn)}")
    time.sleep(0.6)

print("\n--- CollateralRegistry (fees) ---")
for fn in ("REDEMPTION_FEE_FLOOR","baseRate","totalCollaterals","boldToken"):
    print(f"  {fn:<26} {callc(CR,CRADDR,fn)}")
    time.sleep(0.6)
print("DONE")

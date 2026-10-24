import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
class RPCProvider:
    def __init__(s,u): s.u=u
    def make_request(s,m,p):
        r=urllib.request.Request(s.u,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),
            headers={"Content-Type":"application/json"})
        return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
W3=Web3(RPCProvider("https://flare-api.flare.network/ext/C/rpc"))

ADDRS={"StabilityPool":"0x37FfD5d66Fb182493C315B8b8f1C9D67DcF95B18",
       "ActivePool":"0xfa88E9034b82e396bC40b4D22227b84e2a4546C1",
       "TroveManager":"0xf0C949513ff4ecFf1C0afC7c1966dCb8DfAC950b",
       "BorrowerOperations":"0x59a4c88A98F3b515aE041005206E74D0ddFb6cB1",
       "CollateralRegistry":"0x9cbB9b5376F2ecF281ff66BBA8fE2d70f48138F4"}
C={}
for n,a in ADDRS.items():
    abi=json.load(open(f"enosys/abi/{n}.json"))
    C[n]=W3.eth.contract(address=Web3.to_checksum_address(a),abi=abi)

def get(n,fn):
    try: return getattr(C[n].functions,fn)().call()
    except Exception as e: return f"ERR {str(e)[:45]}"

print("#"*70)
print("# ENOSYS LOANS — LIVE STATE, Flare mainnet")
print("#"*70)
print("\n[ StabilityPool — the 75% yield recipient ]")
for fn in ("NAME","getTotalBoldDeposits","getCollBalance","getEntireBranchColl","getEntireBranchDebt",
           "boldToken","collToken","activePool","priceFeed","getTroveManager"):
    print(f"  {fn:<24} {get('StabilityPool',fn)}"); time.sleep(0.5)

print("\n[ ActivePool — yield routing ]")
for fn in ("SP_YIELD_SPLIT","getBoldDebt","getCollBalance","getEntireBranchColl","getEntireBranchDebt",
           "interestRouter","stabilityPool","hasBeenShutDown"):
    print(f"  {fn:<24} {get('ActivePool',fn)}"); time.sleep(0.5)

print("\n[ TroveManager — risk parameters ]")
for fn in ("CCR","MCR","SCR","MIN_DEBT","LIQUIDATION_PENALTY_SP","LIQUIDATION_PENALTY_REDISTRIBUTION",
           "URGENT_REDEMPTION_BONUS","getEntireBranchColl","getEntireBranchDebt","isPaused"):
    print(f"  {fn:<34} {get('TroveManager',fn)}"); time.sleep(0.5)

print("\n[ BorrowerOperations — caps & rates ]")
for fn in ("CCR","MCR","SCR","BCR","MIN_ANNUAL_INTEREST_RATE","MAX_ANNUAL_INTEREST_RATE",
           "MAX_DEBT_CAP","MAX_BRANCH_CAP","MIN_INTEREST_RATE_CHANGE_PERIOD","hasBeenShutDown"):
    print(f"  {fn:<32} {get('BorrowerOperations',fn)}"); time.sleep(0.5)

print("\n[ CollateralRegistry — fees ]")
for fn in ("REDEMPTION_FEE_FLOOR","baseRate","totalCollaterals","boldToken"):
    print(f"  {fn:<24} {get('CollateralRegistry',fn)}"); time.sleep(0.5)
print("\nDONE")

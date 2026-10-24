"""Measure the SP APY directly from accrued interest over a known time interval.
   calcPendingAggInterest is the interest accrued since lastAggUpdateTime."""
import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
RPC="https://flare-api.flare.network/ext/C/rpc"
def rpc(p):
    r=urllib.request.Request(RPC,data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
    j=json.loads(urllib.request.urlopen(r,timeout=25).read().decode())[0]
    if "error" in j: raise RuntimeError(str(j["error"])[:50])
    return j["result"]
def one(m,p): return rpc([{"jsonrpc":"2.0","id":1,"method":m,"params":p}])
ABI=json.load(open("enosys/abi/ActivePool.json"))
AP="0x65c378bf4a68491436c84d8da020b14fefe03d17"
SP="0x2c817F7159c08d94f09764086330c96Bb3265A2f"
def fld(fn):
    f=next(a for a in ABI if a.get("type")=="function" and a.get("name")==fn)
    sig=f"{fn}({','.join(i['type'] for i in f.get('inputs',[]))})"
    return int(one("eth_call",[{"to":AP,"data":"0x"+W3.keccak(text=sig)[:4].hex()},"latest"]),16)
def sp_fld(fn):
    return int(one("eth_call",[{"to":SP,"data":"0x"+W3.keccak(text=fn+"()")[:4].hex()},"latest"]),16)

e18=10**18
print("=== sampling accrued interest to measure the rate directly ===")
samples=[]
for k in range(3):
    t=int(one("eth_getBlockByNumber",["latest",False])["timestamp"],16)
    pend=fld("calcPendingAggInterest")
    upd=fld("lastAggUpdateTime")
    samples.append((t,pend,upd))
    print(f"  sample {k}: block_ts {t:,}  lastUpdate {upd:,}  elapsed {t-upd:>6}s  pendingInterest {pend/e18:.9f} CDP")
    time.sleep(6)

# use the longest interval
t,pend,upd=samples[-1]
elapsed=t-upd
debt=fld("getBoldDebt")
split=sp_fld("SP_YIELD_SPLIT")/e18
spd=sp_fld("getTotalBoldDeposits")
if elapsed>0:
    rate_pct = 100*(pend/debt)*(31536000/elapsed)
    print(f"\n=== DERIVED ANNUAL RATE (from accrual) ===")
    print(f"  elapsed window      {elapsed:,} s ({elapsed/3600:.4f} h)")
    print(f"  interest accrued    {pend/e18:.9f} CDP")
    print(f"  branch debt         {debt/e18:,.2f} CDP")
    print(f"  implied ANNUAL rate {rate_pct:.4f}%   <- weighted avg borrow rate")
    apy = rate_pct*split*(debt/spd)
    print(f"\n  SP share (75%)      {split:.4f}")
    print(f"  SP deposits         {spd/e18:,.2f} CDP")
    print(f"  SP APY              {apy:.4f}%")
    print(f"  loop net            {apy-rate_pct:+.4f}%")
    print(f"\n  NOTE: {elapsed}s is a SHORT window; a tiny accrued amount extrapolated")
    print(f"        to a year amplifies rounding. Treat as an order-of-magnitude check.")

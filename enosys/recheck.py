import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
RPC="https://flare-api.flare.network/ext/C/rpc"
def one(m,p):
    for a in range(4):
        try:
            r=urllib.request.Request(RPC,data=json.dumps([{"jsonrpc":"2.0","id":1,"method":m,"params":p}]).encode(),
                headers={"Content-Type":"application/json"})
            j=json.loads(urllib.request.urlopen(r,timeout=25).read().decode())[0]
            if "error" in j: raise RuntimeError(str(j["error"])[:40])
            return j.get("result","0x")
        except Exception as e:
            time.sleep(3)
    return "0x"
ABI={n:json.load(open(f"enosys/abi/{n}.json")) for n in ("StabilityPool","ActivePool","TroveManager")}
def get(c,addr,fn,args=()):
    A=ABI[c]
    f=next((a for a in A if a.get("type")=="function" and a.get("name")==fn),None)
    if not f: return "no fn"
    sig=f"{fn}({','.join(i['type'] for i in f.get('inputs',[]))})"
    d="0x"+W3.keccak(text=sig)[:4].hex()
    for a in args: d+=(a[2:].rjust(64,"0") if isinstance(a,str) else format(a,'064x'))
    h=one("eth_call",[{"to":addr,"data":d},"latest"])
    if h in ("0x",""): return "revert"
    t=(f.get("outputs") or [{}])[0].get("type","")
    v=int(h,16)
    return "0x"+h[-40:] if t=="address" else v
SP="0x2c817F7159c08d94f09764086330c96Bb3265A2f"
AP="0x65c378bf4a68491436c84d8da020b14fefe03d17"
TM="0xc46e7d0538494feb82b460b9723daba0508c8fb1"
e18=1e18
sp=get("StabilityPool",SP,"getTotalBoldDeposits")
debt=get("ActivePool",AP,"getBoldDebt")
aw=get("ActivePool",AP,"aggWeightedDebtSum")
split=get("ActivePool",AP,"SP_YIELD_SPLIT")
coll=get("TroveManager",TM,"getEntireBranchColl")
bd=get("TroveManager",TM,"getEntireBranchDebt")
print("=== LIVE RECHECK ===")
print(f"  SP deposits        {sp/e18:>16,.2f} CDP")
print(f"  branch debt        {debt/e18:>16,.2f} CDP")
print(f"  wavg borrow rate   {100*(aw/debt):>16.3f}%")
print(f"  SP yield split     {split/e18:>16.3f}")
print(f"  branch collateral  {coll/1e6:>16,.2f} FXRP")
print(f"  branch debt(TM)    {bd/e18:>16,.2f} CDP")
rate=aw/debt
interest=debt*rate
to_sp=interest*(split/e18)
apy=to_sp/sp
print(f"\n  SP interest APY    {100*apy:>16.2f}%")
print(f"  loop: pay {100*rate:.2f}% borrow, earn {100*apy:.2f}% -> net {100*(apy-rate):+.2f}%")
print(f"\n  SP / CDP supply    {100*sp/5.003588542223078750863010e24*1e18/1e18:>15.1f}%")
print(f"  SP / branch debt   {100*sp/debt:>16.1f}%")

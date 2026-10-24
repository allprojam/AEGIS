import json,urllib.request,sys,time
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
RPC="https://flare-api.flare.network/ext/C/rpc"
def one(m,p):
    for _ in range(3):
        try:
            r=urllib.request.Request(RPC,data=json.dumps([{"jsonrpc":"2.0","id":1,"method":m,"params":p}]).encode(),
                headers={"Content-Type":"application/json"})
            j=json.loads(urllib.request.urlopen(r,timeout=25).read().decode())[0]
            if "error" in j: return None
            return j.get("result","0x")
        except Exception: time.sleep(2)
    return None
def sel(sig): return "0x"+W3.keccak(text=sig)[:4].hex()
def call(to,sig,args=()):
    d=sel(sig)
    for a in args: d+=a[2:].rjust(64,"0")
    h=one("eth_call",[{"to":to,"data":d},"latest"])
    return h
e18=10**18
C={
 "Distributor":"0xa00Cb7405F3CBC6B43A86EBfD569CaE6bf7849E5",
 "Vault":"0xe2eA7e18E359C06415adf568ada15e2B9b7E8775",
 "ReserveFund":"0xd7d1671d77044Ce93d198cC612610a0fd9B8028A",
 "APSStaking":"0x7eB8CeB0F64D934a31835b98eB4cbAb3cA56dF28",
 "LoansSplitter":"0x77528AD2f92c462d01916BCA4799036B50A7e612",
 "DEXV3Splitter":"0x36794833ae009368fdFb9736216F1160B9d1cBbE",
}
def show(name,addr,sigs):
    print(f"\n=== {name} {addr} ===")
    for s in sigs:
        h=call(addr,s)
        if h is None or h in ("0x",""): print(f"  {s:<34} revert/empty"); continue
        v=int(h,16)
        # try several scales
        disp=f"{v}" + (f"  ({v/e18:,.6f})" if v>10**15 else "")
        print(f"  {s:<34} {disp}")
        time.sleep(0.3)
show("APY Cloud Distributor",C["Distributor"],
     ["minimumAPY()","maximumAPY()","excessAPYThreshold()","currentEpoch()","epoch()",
      "totalStaked()","lastDistributed()","getMinimumAPY()","getMaximumAPY()"])
show("APY Cloud Vault",C["Vault"],
     ["totalBalance()","balance()","getBalance()","totalFees()","pendingFees()"])
show("Reserve Fund",C["ReserveFund"],
     ["totalBalance()","balance()","getBalance()","reserve()"])
show("APS Staking Manager",C["APSStaking"],
     ["totalStaked()","getTotalStaked()","totalSupply()","stakingToken()","rewardRate()"])

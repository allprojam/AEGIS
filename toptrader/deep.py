import json,urllib.request,time
RPC="https://base.gateway.tenderly.co"
A="0x08FB33543aD633db94282df364AD80FEB8D9fc35"
WETH="0x4200000000000000000000000000000000000006"
TF="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def rpc(p):
    r=urllib.request.Request(RPC,data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
h=int(rpc([{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}])[0]["result"],16)
print(f"head {h:,}")
pad="0x"+A[2:].rjust(64,"0")
inn=0; out=0; cp={}
for i in range(0,6000,300):
    hi=h-i; lo=hi-299
    r=rpc([{"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[{
        "address":WETH,"fromBlock":hex(lo),"toBlock":hex(hi),"topics":[TF]}]}])
    for lg in (r[0].get("result") or []):
        t=lg["topics"]
        if t[1].lower()==pad: out+=1
        if len(t)>2 and t[2].lower()==pad: inn+=1
    time.sleep(0.3)
    if i%1500==0: print(f"  {i} back  in={inn} out={out}",flush=True)
print(f"\n  WETH flows over ~6,000 blocks (~3.3h):  IN {inn}  OUT {out}")
print(f"  -> {'HOLDING, not trading' if inn+out<5 else 'actively trading WETH'}")

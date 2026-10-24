import json,urllib.request,time,sys
RPC="https://base.gateway.tenderly.co"
A="0x769299fbbdb471f971968fd2a62585ab6ce928b9"
WETH="0x4200000000000000000000000000000000000006"
TF="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def rpc(p):
    r=urllib.request.Request(RPC,data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
h=int(rpc([{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}])[0]["result"],16)
print(f"head {h:,} sweeping 20000 blocks",flush=True)
out_n=0; in_n=0; others={}
for i in range(0,20000,500):
    hi=h-i; lo=hi-499
    params={"address":WETH,"fromBlock":hex(lo),"toBlock":hex(hi),"topics":[TF]}
    r=rpc([{"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[params]}])
    for lg in (r[0].get("result") or []):
        t=lg["topics"]
        if len(t)>1 and t[1].lower().endswith(A[2:]): out_n+=1
        if len(t)>2 and t[2].lower().endswith(A[2:]): in_n+=1
    time.sleep(0.35)
    if i%5000==0: print(f"  {i:,} back  from={out_n} to={in_n}",flush=True)
print(f"\n  RESULT over ~20,000 blocks (~11h):",flush=True)
print(f"    WETH out of address: {out_n}",flush=True)
print(f"    WETH into address  : {in_n}",flush=True)
print(f"    total              : {out_n+in_n}",flush=True)

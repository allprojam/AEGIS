import json,urllib.request,time
RPC="https://base.gateway.tenderly.co"
A="0x769299fbbdb471f971968fd2a62585ab6ce928b9"
def rpc(p):
    r=urllib.request.Request(RPC,data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
def nonce():
    return int(rpc([{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionCount","params":[A,"latest"]}])[0]["result"],16)
n1=nonce(); print(f"nonce t0: {n1:,}",flush=True)
time.sleep(60)
n2=nonce(); print(f"nonce t+60s: {n2:,}  delta {n2-n1}",flush=True)
print(f"  -> {n2-n1} txs/min = {(n2-n1)*1440:,}/day" if n2>n1 else "  -> IDLE: no txs in 60s",flush=True)

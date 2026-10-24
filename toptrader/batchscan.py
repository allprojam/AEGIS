"""Batch many eth_getBlockByNumber calls per HTTP request to find this address's txs."""
import json,urllib.request,time,sys
RPC="https://base.gateway.tenderly.co"
A="0x769299fbbdb471f971968fd2a62585ab6ce928b9"
def rpc_batch(payload):
    r=urllib.request.Request(RPC,data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=40).read().decode())
def head():
    return int(rpc_batch([{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}])[0]["result"],16)
h=head(); print(f"head {h:,}",flush=True)
found=[]; BATCH=40; TOTAL=3000
start=h
for off in range(0,TOTAL,BATCH):
    ids=[]; payload=[]
    for k in range(BATCH):
        b=start-off-k
        if b<1: break
        payload.append({"jsonrpc":"2.0","id":k,"method":"eth_getBlockByNumber","params":[hex(b),True]})
    try:
        res=rpc_batch(payload)
    except Exception as e:
        print(f"  batch {off} err {str(e)[:50]}",flush=True); time.sleep(1); continue
    for r in res:
        blk=r.get("result")
        if not blk: continue
        for tx in blk.get("transactions",[]):
            if tx["from"].lower()==A:
                found.append(dict(block=int(blk["number"],16),to=tx["to"],
                    value=int(tx["value"],16),hash=tx["hash"],
                    sel=(tx.get("input") or "0x")[:10],
                    gas=int(tx["gas"],16), gasPrice=int(tx.get("gasPrice","0x0"),16)))
    if off % 400 == 0:
        print(f"  scanned {off+len(payload)} blocks back, found {len(found)}",flush=True)
    if len(found)>=40: break
print(f"\nDONE: {len(found)} txs from A in last {off+len(payload):,} blocks",flush=True)
from collections import Counter
print("\n  selectors used:")
for s,c in Counter(f["sel"] for f in found).most_common(12):
    print(f"    {s}  x{c}")
print("\n  counterparties:")
for t,c in Counter(f["to"] for f in found).most_common(10):
    print(f"    {t}  x{c}")
json.dump(found,open("toptrader/txs.json","w"),indent=1)
print("\n  saved toptrader/txs.json")

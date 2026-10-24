import json,urllib.request,time,sys
def post(p):
    r=urllib.request.Request("https://base.gateway.tenderly.co",data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json"})
    j=json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
    if "error" in j: raise RuntimeError(str(j["error"])[:70])
    return j.get("result")
A="0x769299fBBDb471F971968FD2a62585Ab6cE928B9".lower()
head=int(post({"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}),16)
print(f"head {head:,}",flush=True)
found=[]
SPAN=4000
start=head-SPAN
for b in range(head, start, -1):
    try:
        blk=post({"jsonrpc":"2.0","id":1,"method":"eth_getBlockByNumber","params":[hex(b),True]})
    except Exception:
        time.sleep(0.2); continue
    if not blk: continue
    for tx in blk.get("transactions",[]):
        if tx["from"].lower()==A:
            found.append(dict(block=b,to=tx["to"],value=int(tx["value"],16),
                              hash=tx["hash"],sel=tx.get("input","0x")[:10]))
    if (head-b)%1000==0:
        print(f"  scanned to block {b} ({head-b} back), found {len(found)}",flush=True)
    if len(found)>=25: break
print(f"\nDONE: {len(found)} txs from A in last {(head-(found[-1]['block'] if found else start)):,} blocks",flush=True)
for f in found[:25]:
    print(f"  blk {f['block']}  to {f['to']}  val {f['value']/1e18:.5f}  sel {f['sel']}",flush=True)
json.dump(found,open("toptrader/txs.json","w"),indent=1)

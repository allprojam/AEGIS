import json,urllib.request,csv
from collections import Counter
RPC="https://base.gateway.tenderly.co"
def call(m,p):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
SWAP="0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
PID="f13203ddbf2c9816a79b656a1a952521702715d92fea465b84ae2ed6e94a7f22"
txs=[]
with open("v4_trades.csv") as f:
    for row in csv.DictReader(f):
        if row["tx"] not in txs: txs.append(row["tx"])
fees=Counter(); rows=[]
for i,tx in enumerate(txs[:120]):
    try:
        rec=call("eth_getTransactionReceipt",[tx]).get("result")
        if not rec: continue
        for l in rec.get("logs",[]):
            if l["topics"][0].lower()!=SWAP: continue
            if len(l["topics"])<2 or l["topics"][1][2:].lower()!=PID: continue
            w=[l["data"][2:][j*64:(j+1)*64] for j in range(len(l["data"][2:])//64)]
            if len(w)>=6:
                fee=int(w[5],16)
                fees[fee]+=1
                rows.append(fee)
    except Exception:
        pass
    if i%30==0: print(f"  ...{i} txs",flush=True)
print(f"\n=== FEE FIELD ACROSS {len(rows)} v4 Swap events ===")
for f_,c in fees.most_common():
    print(f"  fee={f_:>8}  x{c:<5} = {f_/10000:.5f}% = {f_/100:.4f} bp"
          f"  {'DYNAMIC flag set' if f_ & 0x800000 else 'static'}")

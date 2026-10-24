"""Is on-chain order flow on the WETH/USDC pool informative, or is it MEV dust?
Samples a window, measures swap-size distribution and imbalance persistence."""
import json, numpy as np
from web3 import Web3
w = Web3(Web3.HTTPProvider("https://base-rpc.publicnode.com", request_kwargs={"timeout":25}))
POOL = Web3.to_checksum_address("0xd0b53D9277642d899DF5C87A3966A349A798F224")
TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
N = 600
head = w.eth.block_number
logs = w.eth.get_logs({"fromBlock": head-N, "toBlock": head, "address": POOL, "topics":[TOPIC]})
print(f"pool {POOL}  last {N} blocks (~{N*2/60:.0f} min)  ->  {len(logs)} Swap events")

rows=[]
for lg in logs:
    raw = bytes(lg["data"])
    a0 = int.from_bytes(raw[0:32], "big", signed=True)/1e18
    a1 = int.from_bytes(raw[32:64], "big", signed=True)/1e6
    rows.append((lg.blockNumber, a0, a1))
eth = np.array([abs(r[1]) for r in rows])
usd = np.array([abs(r[2]) for r in rows])
print(f"\nswap size (ETH):  min {eth.min():.6f}  median {np.median(eth):.6f}  p90 {np.percentile(eth,90):.4f}  max {eth.max():.4f}")
print(f"swap size (USDC): min {usd.min():.2f}  median {np.median(usd):.2f}  p90 {np.percentile(usd,90):.2f}  max {usd.max():.2f}")
tot = usd.sum()
print(f"\ntotal USDC volume: {tot:,.0f} across {len(rows)} swaps")
for thr in (10, 100, 1000, 10000):
    sel = usd[usd>=thr]
    print(f"  swaps >= ${thr:<7}: {len(sel):>5} ({100*len(sel)/len(usd):>5.1f}%)  = {100*sel.sum()/tot:>5.1f}% of volume")

# imbalance per block, only counting meaningful swaps
buckets={}
for bn,a0,a1 in rows:
    buckets.setdefault(bn, []).append((a0,a1))
imb=[]
for bn in sorted(buckets):
    b=sum(-a0 for a0,_ in buckets[bn] if a0<0)     # ETH bought from pool
    s=sum(a0 for a0,_ in buckets[bn] if a0>0)      # ETH sold into pool
    if b+s>0: imb.append(b/(b+s)*2-1)
imb=np.array(imb)
print(f"\nblocks with flow: {len(imb)}")
if len(imb)>3:
    print(f"imbalance (2*buyfrac-1): mean {imb.mean():+.3f}  std {imb.std():.3f}")
    same=sum(1 for i in range(1,len(imb)) if imb[i]*imb[i-1]>0)
    print(f"sign persistence: {same}/{len(imb)-1} ({same/(len(imb)-1):.0%})  [50% = no signal]")

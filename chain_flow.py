"""What on-chain data is ACTUALLY available on Base (vs what isn't).
Confirms: no public mempool -> only post-confirmation flow is observable."""
import json, time
from web3 import Web3

W3 = [Web3(Web3.HTTPProvider(u, request_kwargs={"timeout":20})) for u in
      ("https://base-rpc.publicnode.com","https://base.drpc.org","https://1rpc.io/base")]

def w3():
    for w in W3:
        try:
            w.eth.block_number; return w
        except Exception: continue
    raise RuntimeError("no RPC")

w = w3()
print("chain:", w.eth.chain_id, " head:", w.eth.block_number)

# 1. how much activity is in a block?
latest = w.eth.get_block("latest", full_transactions=False)
print(f"\nlatest block {latest.number}: {len(latest.transactions)} txs, "
      f"gas used {latest.gasUsed:,}, timestamp {latest.timestamp}")

# 2. block cadence over a short window
h = w.eth.block_number
ts = [w.eth.get_block(h-i).timestamp for i in range(6)]
gaps = [ts[i]-ts[i+1] for i in range(len(ts)-1)]
print(f"block cadence over last 6 blocks: {gaps}  (mean {sum(gaps)/len(gaps):.1f}s)")

# 3. the REAL observable flow layer: swap events on the WETH/USDC pools
SWAP_V3 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"  # UniswapV3 Swap
WETH = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bda02913")
pools = {
 "UniV3 0.01%": Web3.to_checksum_address("0xd0b53D9277642d899DF5C87A3966A349A798F224"),
 "Aerodrome":   Web3.to_checksum_address("0xcDAC0d6c6C59727a65F871236188350531885C43"),
}
start = h - 30
for name, pool in pools.items():
    try:
        logs = w.eth.get_logs({"fromBlock": start, "toBlock": "latest",
                                "address": pool, "topics": [SWAP_V3]})
        print(f"\n{name} {pool[:12]}...  {len(logs)} Swap events in the last 30 blocks")
        for lg in logs[-3:]:
            print(f"   block {lg.blockNumber}  tx {lg.transactionHash.hex()[:18]}...")
    except Exception as e:
        print(f"\n{name}: get_logs FAILED -> {type(e).__name__}: {str(e)[:90]}")

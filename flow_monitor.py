#!/usr/bin/env python3
"""Real-time confirmed order flow on the WETH/USDC pool we would actually trade.

NOT a mempool listener: Base has no public mempool (measured: newPendingTransactions
delivers 0). This is post-confirmation flow, which is all that is observable.

Goal: measure order-flow IMBALANCE (ETH bought vs sold), a signal that is NOT in the
price candles, and check whether it persists long enough to be tradeable.
"""
import asyncio, json, time
import websockets
from web3 import Web3

WS = "wss://base-rpc.publicnode.com"
HTTP = "https://base-rpc.publicnode.com"
POOL = Web3.to_checksum_address("0xd0b53D9277642d899DF5C87A3966A349A798F224")  # UniV3 0.01%
TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"   # Swap
W3 = Web3(Web3.HTTPProvider(HTTP, request_kwargs={"timeout": 20}))

def decode_swap(log):
    """UniV3 Swap: amount0 = WETH delta in pool. +ve = ETH sold into pool, -ve = ETH bought."""
    d = log["data"]
    raw = bytes(d) if not isinstance(d, str) else bytes.fromhex(d[2:] if d.startswith("0x") else d)
    a0 = int.from_bytes(raw[0:32], "big", signed=True)
    a1 = int.from_bytes(raw[32:64], "big", signed=True)
    return a0 / 1e18, a1 / 1e6        # WETH, USDC

async def main(seconds=40):
    start_block = W3.eth.block_number
    print(f"watching {POOL} from block {start_block} for {seconds}s")
    print(f"{'block':>10}{'swaps':>7}{'ETH bought':>12}{'ETH sold':>11}{'net ETH':>10}{'imbalance':>11}")
    seen = start_block
    totals = []
    async with websockets.connect(WS, open_timeout=10, ping_interval=None) as ws:
        await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newHeads"]}))
        sub = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))["result"]
        t0 = time.time()
        while time.time() - t0 < seconds:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=6))
            except asyncio.TimeoutError:
                continue
            if m.get("method") != "eth_subscription": continue
            r = m["params"]["result"]
            bn = int(r["number"], 16)
            if bn <= seen: continue
            try:
                logs = W3.eth.get_logs({"fromBlock": seen + 1, "toBlock": bn,
                                        "address": POOL, "topics": [TOPIC]})
            except Exception:
                seen = bn; continue
            bought = sold = 0.0
            for lg in logs:
                a0, a1 = decode_swap(lg)
                if a0 < 0: bought += -a0
                else:       sold  += a0
            net = bought - sold
            imb = (net / (bought + sold)) if (bought + sold) > 0 else 0.0
            totals.append(imb)
            print(f"{bn:>10}{len(logs):>7}{bought:>12.3f}{sold:>11.3f}{net:>10.3f}{imb:>+11.2f}")
            seen = bn
    if totals:
        n_pos = sum(1 for x in totals if x > 0.15); n_neg = sum(1 for x in totals if x < -0.15)
        print(f"\nblocks observed {len(totals)}  strong-buy {n_pos}  strong-sell {n_neg}")
        # persistence: does the sign of one block's imbalance predict the next?
        same = sum(1 for i in range(1, len(totals)) if totals[i]*totals[i-1] > 0)
        print(f"sign persistence block-to-block: {same}/{max(1,len(totals)-1)} "
              f"({same/max(1,len(totals)-1):.0%})  [50% = no signal]")

asyncio.run(main())

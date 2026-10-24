"""Probe Base over websocket: block cadence, and whether a public mempool is visible."""
import asyncio, json, time, websockets

URLS = ["wss://base-rpc.publicnode.com", "wss://base.drpc.org", "wss://mainnet.base.org"]

async def probe(url, secs=14):
    try:
        async with websockets.connect(url, open_timeout=8, ping_interval=None) as ws:
            await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newHeads"]}))
            await ws.send(json.dumps({"jsonrpc":"2.0","id":2,"method":"eth_subscribe","params":["newPendingTransactions"]}))
            subs, heads, pend, t0 = {}, [], 0, time.time()
            while time.time() - t0 < secs:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                except asyncio.TimeoutError:
                    continue
                if "id" in m and "result" in m:
                    subs[str(m["id"])] = m.get("result"); continue
                if m.get("method") == "eth_subscription":
                    p = m["params"]
                    if p["subscription"] == subs.get("1"):
                        r = p["result"]; heads.append((int(r["number"],16), int(r["timestamp"],16)))
                    elif p["subscription"] == subs.get("2"):
                        pend += 1
            gaps = [heads[i][1]-heads[i-1][1] for i in range(1,len(heads))]
            return {"url":url, "heads":len(heads), "pending_txs":pend,
                    "block_s":round(sum(gaps)/len(gaps),2) if gaps else None,
                    "head_sub":bool(subs.get("1")), "pend_sub":bool(subs.get("2")),
                    "err":None}
    except Exception as e:
        return {"url":url, "err":f"{type(e).__name__}: {str(e)[:70]}"}

async def main():
    for u in URLS:
        r = await probe(u)
        print(json.dumps(r))

asyncio.run(main())

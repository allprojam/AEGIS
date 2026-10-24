#!/usr/bin/env python3
"""IB preflight: verify connectivity and data access before building anything on top.

Run this WHERE THE GATEWAY LIVES (or through a forwarded port). It answers, in order:
  1. Is the API socket reachable at all?
  2. Which accounts are visible, and what is the buying power?
  3. Can we pull real market data for the instruments the research validated?

Ports: 7497 = TWS paper, 7496 = TWS live, 4002 = Gateway paper, 4001 = Gateway live.
Default here is PAPER. Do not point this at a live port until the strategy is settled.

usage: ib_preflight.py [host] [port] [client_id]
"""
import sys, asyncio, datetime as dt
from ib_async import IB, Stock, Index, util

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 7497      # paper
CID  = int(sys.argv[3]) if len(sys.argv) > 3 else 11

# instruments the research actually justified
WATCH = [("SPY", "STK", "ARCA"), ("TLT", "STK", "ARCA"), ("AGG", "STK", "ARCA"),
         ("SHY", "STK", "ARCA"), ("VIX", "IND", "CBOE"), ("SPX", "IND", "CBOE")]

def ok(b): return "OK" if b else "FAIL"

async def main():
    ib = IB()
    print(f"connecting to {HOST}:{PORT} (clientId {CID}) ...")
    try:
        await ib.connectAsync(HOST, PORT, clientId=CID, timeout=15)
    except Exception as e:
        print(f"CONNECT FAILED: {type(e).__name__}: {str(e)[:160]}")
        print("\nLikely causes:")
        print("  1. Gateway/TWS not running, or not logged in")
        print("  2. API not enabled: Configure -> API -> Settings -> 'Enable ActiveX and Socket Clients'")
        print("  3. Port mismatch (7497 paper TWS / 4002 paper Gateway / 7496 / 4001 live)")
        print("  4. Connecting from a remote host: 'Allow connections from localhost only' is the")
        print("     default and MUST be unticked -- or use an SSH/socat forward")
        print("  5. 'Read-Only API' is on (fine for data, blocks orders)")
        return
    print(f"CONNECTED  {ok(ib.isConnected())}   serverVersion={ib.client.serverVersion()}")

    print("\n--- accounts ---")
    try:
        for a in ib.managedAccounts():
            print(f"  account {a}")
    except Exception as e:
        print(f"  FAIL {e}")

    print("\n--- account values ---")
    try:
        for v in ib.accountValues():
            if v.tag in ("NetLiquidation", "TotalCashValue", "BuyingPower", "AvailableFunds"):
                print(f"  {v.tag:<18} {v.value:>16} {v.currency}")
    except Exception as e:
        print(f"  FAIL {e}")

    print("\n--- market data ---")
    print(f"  {'symbol':<8}{'secType':>9}{'exchange':>9}{'contract ok':>13}{'last':>12}{'close':>12}")
    for sym, sec, exch in WATCH:
        c = Index(sym, exch) if sec == "IND" else Stock(sym, exch, "USD")
        try:
            q = await ib.qualifyContractsAsync(c)
            got = bool(q)
            t = ib.reqMktData(c, "", False, False)
            await asyncio.sleep(2.5)
            last = t.last if t.last == t.last else float("nan")     # nan check
            close = t.close if t.close == t.close else float("nan")
            print(f"  {sym:<8}{sec:>9}{exch:>9}{ok(got):>13}{last:>12.2f}{close:>12.2f}")
            ib.cancelMktData(c)
        except Exception as e:
            print(f"  {sym:<8}{sec:>9}{exch:>9}{'ERR':>13}  {str(e)[:40]}")

    print("\n--- historical data (60 daily bars, for backtest parity) ---")
    try:
        c = Stock("SPY", "ARCA", "USD")
        await ib.qualifyContractsAsync(c)
        bars = await ib.reqHistoricalDataAsync(
            c, endDateTime="", durationStr="60 D", barSizeSetting="1 day",
            whatToShow="TRADES", useRTH=True, formatDate=1)
        print(f"  SPY daily bars: {len(bars)}   last: {bars[-1].date} close {bars[-1].close}")
        if bars:
            print(f"  first: {bars[0].date} close {bars[0].close}")
    except Exception as e:
        print(f"  FAIL {type(e).__name__}: {str(e)[:120]}")

    ib.disconnect()
    print("\npreflight complete.")

if __name__ == "__main__":
    util.startLoop() if False else None
    asyncio.run(main())

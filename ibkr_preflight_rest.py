#!/usr/bin/env python3
"""Preflight for the Client Portal REST API (port 5000).

IMPORTANT: this is NOT the same API as ib_async/ib_insync. Those speak the TWS/Gateway
SOCKET protocol (ports 7497/4001). The Client Portal Gateway is a REST service on 5000.
ib_async is therefore the wrong tool here -- use ibkr_client.py.
"""
import json, time
import ibkr_client as ib

def show(label, code, body):
    if isinstance(body, (dict, list)):
        txt = json.dumps(body)[:300]
    else:
        txt = str(body)[:300]
    print(f"  {label:<38} HTTP {code}   {txt}")

print("=== 1. session ===")
show("iserver/auth/status", *ib.status())

print("\n=== 2. accounts ===")
code, accts = ib.accounts()
show("portfolio/accounts", code, accts)
acct_id = None
if isinstance(accts, list) and accts:
    acct_id = accts[0].get("accountId")

print("\n=== 3. account summary ===")
if acct_id:
    code, summ = ib.summary(acct_id)
    if isinstance(summ, dict):
        for k in ("netliquidation", "totalcashvalue", "buyingpower", "availablefunds", "accruedcash"):
            v = summ.get(k) or {}
            if isinstance(v, dict) and v.get("amount") is not None:
                print(f"  {k:<22} {v.get('amount'):>18} {v.get('currency','')}")
        if not any(isinstance(summ.get(k), dict) for k in ("netliquidation","totalcashvalue")):
            print("  raw:", json.dumps(summ)[:300])
    else:
        show("summary", code, summ)

print("\n=== 4. contract lookup (needs conid for anything else) ===")
for sym in ("SPY", "TLT", "AGG", "SHY"):
    code, body = ib.secdef(sym)
    conid = None
    try:
        if isinstance(body, list) and body:
            rows = body[0].get("sections") or []
            for r in rows:
                if r.get("secType") == "STK":
                    conid = r.get("conid"); break
            if conid is None:
                conid = body[0].get("conid")
        elif isinstance(body, dict):
            conid = body.get("conid")
    except Exception:
        pass
    print(f"  {sym:<5} HTTP {code}  conid={conid}")

print("\n=== 5. market data snapshot (SPY) ===")
code, body = ib.secdef("SPY")
conid = None
if isinstance(body, list) and body:
    for r in (body[0].get("sections") or []):
        if r.get("secType") == "STK": conid = r.get("conid")
if conid:
    import requests
    r = requests.get(f"https://srv1619135.tailf16ee8.ts.net/v1/api/iserver/marketdata/snapshot"
                     f"?conids={conid}&fields=31,84,86", timeout=20)
    print(f"  snapshot conid {conid}: HTTP {r.status_code}  {r.text[:200]}")
    time.sleep(2)
    r = requests.get(f"https://srv1619135.tailf16ee8.ts.net/v1/api/iserver/marketdata/snapshot"
                     f"?conids={conid}&fields=31,84,86", timeout=20)
    print(f"  snapshot again    : HTTP {r.status_code}  {r.text[:200]}")

print("\n=== 6. historical bars (SPY, 30d daily) ===")
if conid:
    import requests
    r = requests.get(f"https://srv1619135.tailf16ee8.ts.net/v1/api/iserver/marketdata/history"
                     f"?conid={conid}&period=30d&bar=1d", timeout=25)
    try:
        j = r.json()
        d = j.get("data") or []
        print(f"  HTTP {r.status_code}  bars={len(d)}  {json.dumps(j)[:200]}")
    except Exception:
        show("history", r.status_code, r.text)

print("\n=== 7. options entitlement check ===")
if conid:
    code, body = ib.strikes(conid)
    show("iserver/secdef/strikes (SPY)", code, body)

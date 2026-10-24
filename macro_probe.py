#!/usr/bin/env python3
"""Probe availability of macro + prediction-market sources. No keys assumed."""
import json, urllib.request

def probe(name, url, is_json=True):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
        if is_json:
            j = json.loads(body.decode())
            keys = list(j.keys())[:6]
            n = len(j.get("markets") or j.get("events") or j.get("data") or [])
            print(f"  OK   {name:<34} json keys={keys} items={n}")
            return j
        else:
            lines = body.decode().splitlines()
            print(f"  OK   {name:<34} csv lines={len(lines)}   head: {lines[0][:60]} | {lines[1][:60] if len(lines)>1 else ''}")
            return lines
    except Exception as e:
        print(f"  FAIL {name:<34} {type(e).__name__}: {str(e)[:80]}")
        return None

print("=== KALSHI (prediction markets) ===")
probe("kalshi elections /markets", "https://api.elections.kalshi.com/trade-api/v2/markets?limit=3")
probe("kalshi /events",           "https://api.elections.kalshi.com/trade-api/v2/events?limit=3")
probe("kalshi trading-api /markets","https://trading-api.kalshi.com/trade-api/v2/markets?limit=3")

print("\n=== US TREASURY (debt) ===")
probe("fiscaldata debt_to_penny",
      "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?sort=-record_date&page%5Bsize%5D=3")

print("\n=== FRED (macro series, no key) ===")
for sid in ("T10Y3M","T10Y2Y","DGS10","UNRATE","VIXCLS","BAMLH0A0HYM2"):
    probe(f"FRED {sid}", f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", is_json=False)

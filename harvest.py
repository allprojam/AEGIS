#!/usr/bin/env python3
"""Harvest OPEN-SOURCE public TradingView strategies. We only keep scripts whose
Pine source is actually included - if we cannot read it, we cannot backtest it."""
import json, time, urllib.parse, urllib.request, os

QUERIES = ["trend","breakout","momentum","mean reversion","scalping","volatility","atr",
 "supertrend","donchian","bollinger","rsi","macd","ema cross","vwap","reversal","swing",
 "intraday","crypto","eth","bitcoin","session","opening range","squeeze","adx","keltner",
 "ichimoku","halftrend","ut bot","chandelier","parabolic","trailing stop","range",
 "liquidity","momentum strategy","trend following","pullback","ema","hull","stochastic",
 "profit","backtest","5 minute","15 minute","mean reversion strategy"]

os.makedirs("pine/library", exist_ok=True)
seen, recs = {}, []
for q in QUERIES:
    for t in (2,):
        url = ("https://www.tradingview.com/pubscripts-suggest-json/?search="
               + urllib.parse.quote(q) + f"&type={t}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            print("  err", q, str(e)[:60]); time.sleep(1); continue
        for rec in d.get("results", []):
            sid = rec.get("scriptIdPart")
            if not sid or sid in seen:
                continue
            seen[sid] = 1
            recs.append(rec)
        time.sleep(0.3)

with open("pine/library/raw.json", "w") as fh:
    json.dump(recs, fh)

withsrc = [r for r in recs if (r.get("scriptSource") or "").strip()]
print(f"harvested {len(recs)} strategy records; {len(withsrc)} include source")
withsrc.sort(key=lambda r: r.get("agreeCount", 0), reverse=True)
rows = []
for r in withsrc:
    src = r["scriptSource"]
    rows.append({"id": r["scriptIdPart"], "name": r.get("scriptName", "")[:70],
                 "author": (r.get("author") or {}).get("username"),
                 "likes": r.get("agreeCount"), "ver": r.get("version"),
                 "len": len(src),
                 "entry": "strategy.entry" in src,
                 "atr": "atr" in src.lower(),
                 "stop": ("strategy.exit" in src) or ("stop" in src.lower())})
open("pine/library/index.json", "w").write(json.dumps(rows, indent=1))
print(f"{'likes':>6} {'len':>6} {'strat':>6} {'atr':>5} name")
for x in rows[:30]:
    print(f"{x['likes']:>6} {x['len']:>6} {str(x['entry']):>6} {str(x['atr']):>5} {x['name']}")

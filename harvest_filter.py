#!/usr/bin/env python3
"""Routine discovery filter for public TradingView strategies.

QUERIES -> pubscripts-suggest-json (type=2) -> keep only scripts whose Pine source is
actually included (unreadable == unauditable == discard) -> structural screen -> manifest.
Survivors get ported, then registered in auto_oos.REGISTRY where the automatic H1/H2
out-of-sample gate decides keep/discard.
"""
from __future__ import annotations
import argparse, json, os, re, time, urllib.parse, urllib.request
import pandas as pd

QUERIES = ["trend following", "momentum", "trend", "breakout", "swing", "moving average",
           "supertrend", "donchian", "keltner", "ema cross", "momentum strategy",
           "trend strategy", "higher timeframe", "daily", "position trading",
           "golden cross", "death cross", "turtle", "ichimoku", "chandelier exit",
           "parabolic sar", "bollinger breakout", "bb squeeze", "volatility breakout",
           "range breakout", "opening range", "session breakout", "rsi divergence",
           "mean reversion", "macd histogram", "stochastic", "pivot points", "gap",
           "atr trailing stop", "trend filter", "adx", "trix", "vortex", "aroon",
           "linear regression", "regression channel", "keltner channel", "squeeze",
           "momentum breakout", "trend reversal", "pullback", "ema ribbon",
           "halftrend", "ut bot", "super trend strategy", "long term", "weekly",
           "4 hour", "1 hour", "btc", "bitcoin", "crypto strategy", "risk management"]

OUT = "pine/library"


def fetch(q, typ=2, tries=3):
    url = ("https://www.tradingview.com/pubscripts-suggest-json/?search="
           + urllib.parse.quote(q) + f"&type={typ}")
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode()).get("results", [])
        except Exception as e:
            if i == tries - 1:
                print(f"  ! {q}: {str(e)[:60]}")
            time.sleep(1.5)
    return []


def screen(src):
    low = src.lower()
    bad, m = [], {}
    m["long"] = ("strategy.long" in src)
    m["short"] = ("strategy.short" in src)
    lens = [int(x) for x in re.findall(r"ta\.(?:sma|ema|wma|hma|rma|rsi|atr|stoch)\s*\(\s*[^,]+,\s*(\d+)", low)]
    m["max_len"] = max(lens) if lens else 0
    m["atr_stop"] = bool(re.search(r"atr[^)\n]*\)\s*\*", low)) or ("strategy.exit" in low)
    sec = ("request.security(" in low) or bool(re.search(r"[^a-z]security\(", low))
    m["htf"] = bool(sec)
    m["lookahead_guard"] = ("lookahead" in low) or (not sec)
    m["churn"] = "HIGH" if (m["max_len"] and m["max_len"] < 30) else ("LOW" if m["atr_stop"] else "MED")
    if not m["long"]:
        bad.append("no long entry")
    if m["max_len"] and m["max_len"] < 14:
        bad.append("all lookbacks <14 (noise)")
    if not m["lookahead_guard"]:
        bad.append("security() w/o lookahead guard (repaint)")
    if m["churn"] == "HIGH":
        bad.append("churn risk: lookbacks <30")
    return (len(bad) == 0), bad, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="ETH")
    ap.add_argument("--timeframe", default="1h")
    a = ap.parse_args()
    os.makedirs(f"{OUT}/src", exist_ok=True)

    seen, recs = {}, []
    for q in QUERIES:
        for r in fetch(q):
            sid = r.get("scriptIdPart")
            if sid and sid not in seen:
                seen[sid] = 1
                recs.append(r)
        time.sleep(0.3)

    opensrc = [r for r in recs if (r.get("scriptSource") or "").strip()]
    rows = []
    for r in opensrc:
        src = r["scriptSource"]
        keep, why, m = screen(src)
        open(f"{OUT}/src/{r['scriptIdPart']}.pine", "w").write(src)
        rows.append({"id": r["scriptIdPart"], "name": r.get("scriptName", "")[:58],
                     "author": (r.get("author") or {}).get("username"),
                     "likes": r.get("agreeCount", 0), "keep": keep, "why": "; ".join(why),
                     "churn": m["churn"], "max_len": m["max_len"], "atr_stop": m["atr_stop"],
                     "htf": m["htf"], "len": len(src)})
    df = pd.DataFrame(rows).sort_values(["keep", "likes"], ascending=[False, False])
    os.makedirs("logs", exist_ok=True)
    df.to_csv(f"{OUT}/manifest_{a.asset}_{a.timeframe}.csv", index=False)

    print(f"discovered {len(recs)} records -> {len(opensrc)} with readable source")
    print(f"passed structural screen: {int(df.keep.sum())}/{len(df)}\n")
    print("=== SHORTLIST ===")
    print(df[df.keep].head(20).to_string(index=False))
    print("\n=== DISCARDED (top 10 by likes) ===")
    print(df[~df.keep].head(10)[["name", "likes", "churn", "why"]].to_string(index=False))
    print(f"\nmanifest -> {OUT}/manifest_{a.asset}_{a.timeframe}.csv")
    print(f"sources  -> {OUT}/src/*.pine")


if __name__ == "__main__":
    main()

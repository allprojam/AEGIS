#!/usr/bin/env python3
"""Paper-trade engine: TradingView signals + REAL Base DEX quotes. No keys, no writes.

Every tick it reads the chart signal and an executable DEX quote, then tracks a
simulated long in USDC terms. Costs modelled: venue fee, gas per swap.

Usage: python3 paper.py [--minutes M] [--interval S] [--size-eth E]
"""
from __future__ import annotations
import argparse, json, os, signal, sys, time, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/root/agency_bot/workspace")
import signals as sig
import dex

LOG_DIR = os.path.join(HERE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
GAS_USD_PER_SWAP = 0.02          # Base mainnet, typical
USDC_PER_TRADE = 250.0           # notional for the simulation


class Position:
    def __init__(self):
        self.side = "flat"
        self.entry_px = None
        self.entry_ts = None
        self.venue = None
        self.entry_fee_usd = 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=6.0)
    ap.add_argument("--interval", type=float, default=12.0)
    ap.add_argument("--size-eth", type=float, default=0.05)
    a = ap.parse_args()

    day = dt.datetime.now().strftime("%Y-%m-%d")
    ticks = os.path.join(LOG_DIR, f"paper-ticks-{day}.jsonl")
    trades = os.path.join(LOG_DIR, f"paper-trades-{day}.jsonl")
    stop = {"f": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("f", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("f", True))

    end = time.time() + a.minutes * 60
    pos = Position()
    prev, n, realized = None, 0, 0.0
    print(f"paper engine: {a.minutes}min @ {a.interval}s | ticks->{ticks} trades->{trades}")

    with open(ticks, "a") as tf, open(trades, "a") as trf:
        while time.time() < end and not stop["f"]:
            n += 1
            try:
                c = sig.read_chart()
            except Exception as e:
                print(f"[{n}] chart read failed: {str(e)[:80]}"); time.sleep(a.interval); continue
            try:
                q = dex.best_quote(a.size_eth)
            except Exception as e:
                q = {"ok": False, "error": str(e)[:80]}
            if not q.get("ok"):
                print(f"[{n}] quote failed: {q.get('error')}"); time.sleep(a.interval); continue

            px = q["best"]["price"]
            venue = q["best"]["venue"]
            ev = sig.classify(prev, c)
            fee_bps = q["best"]["fee_bps"]

            rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "n": n,
                   "signals": c, "events": ev, "dex": q["best"], "spread_pct": q["spread_best_worst_pct"],
                   "position": pos.side, "realized_usd": round(realized, 4)}
            tf.write(json.dumps(rec) + "\n"); tf.flush()

            bull = "HMA_BULL_CROSS" in ev
            bear = "HMA_BEAR_CROSS" in ev or "MACD_BB_BELOW_LOWER" in ev

            if pos.side == "flat" and bull:
                pos.side, pos.entry_px, pos.entry_ts, pos.venue = "long", px, rec["ts"], venue
                pos.entry_fee_usd = USDC_PER_TRADE * fee_bps / 10000.0
                tr = {"ts": rec["ts"], "action": "OPEN_LONG", "px": px, "venue": venue,
                      "size_usdc": USDC_PER_TRADE, "fee_usd": round(pos.entry_fee_usd, 4),
                      "gas_usd": GAS_USD_PER_SWAP, "reason": ev, "signals": c}
                trf.write(json.dumps(tr) + "\n"); trf.flush()
                print(f"[{n}] OPEN  @ {px:.4f} via {venue}  {ev}")
            elif pos.side == "long" and bear:
                gross = USDC_PER_TRADE * (px / pos.entry_px - 1)
                cost = pos.entry_fee_usd + USDC_PER_TRADE * fee_bps / 10000.0 + 2 * GAS_USD_PER_SWAP
                net = gross - cost
                realized += net
                tr = {"ts": rec["ts"], "action": "CLOSE_LONG", "px": px, "entry_px": pos.entry_px,
                      "gross_usd": round(gross, 4), "costs_usd": round(cost, 4), "net_usd": round(net, 4),
                      "realized_cum_usd": round(realized, 4), "reason": ev, "signals": c}
                trf.write(json.dumps(tr) + "\n"); trf.flush()
                print(f"[{n}] CLOSE @ {px:.4f}  net ${net:+.4f}  (cum ${realized:+.4f})  {ev}")
                pos.side, pos.entry_px = "flat", None
            else:
                print(f"[{n}] {c.get('symbol')} {c.get('tf')}m  dex={px:.4f} {venue} | HMA1={c['hull'].get('HMA1')} "
                      f"HMA2={c['hull'].get('HMA2')} MACD-BB={c['macd_bb'].get('line')} {ev if ev else ''}")

            if time.time() < end and not stop["f"]:
                time.sleep(a.interval)

    if pos.side == "long":
        print(f"NOTE: ended holding a paper long from {pos.entry_px:.4f} (unrealized)")
    print(f"ticks={n} realized=${realized:+.4f}")


if __name__ == "__main__":
    main()

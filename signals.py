#!/usr/bin/env python3
"""Signal engine: reads the TradingView chart (Hull MA v420 + Bollinguer sobre Macd)
and turns it into discrete events. Read-only; no keys, no chain writes.

Usage: python3 signals.py [--polls N] [--interval S]
"""
from __future__ import annotations
import argparse, json, os, signal, sys, time, datetime as dt

sys.path.insert(0, "/root/agency_bot/workspace")
sys.path.insert(0, "/root/agency_bot/workspace/aegis")
import tv_client as tv

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def num(s):
    """'2,685.27' / '−0.07' / '0.03' -> float. Handles unicode minus and commas."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).replace(",", "").replace("\u2212", "-").replace("\u2013", "-").strip()
    try:
        return float(t)
    except ValueError:
        return None


def read_chart() -> dict:
    """One read of chart state + all study values."""
    state = json.loads(tv.call("chart_get_state", {}))
    vals = json.loads(tv.call("data_get_study_values", {}))
    out = {"symbol": state.get("symbol"), "tf": state.get("resolution"), "hull": {}, "macd_bb": {}}
    for s in vals.get("studies", []):
        name, v = s.get("name", ""), s.get("values") or {}
        if "Hull" in name:
            for k, raw in v.items():
                n = num(raw)
                if k.startswith("HMA"):
                    out["hull"][k] = n
                elif k.startswith("Hourly"):
                    out["hull"][k.replace("Hourly ", "").strip()] = n
        elif "Bollinguer" in name or "Bollinger" in name:
            for k, raw in v.items():
                n = num(raw)
                kl = k.lower()
                if "linea" in kl:
                    out["macd_bb"]["line"] = n
                elif "superior" in kl:
                    out["macd_bb"]["upper"] = n
                elif "inferior" in kl:
                    out["macd_bb"]["lower"] = n
    return out


def classify(prev: dict | None, cur: dict) -> list[str]:
    """Derive discrete events from two consecutive reads."""
    ev = []
    h, m = cur.get("hull", {}), cur.get("macd_bb", {})
    if h.get("HMA1") and h.get("HMA2") and prev:
        p1, p2 = prev.get("hull", {}).get("HMA1"), prev.get("hull", {}).get("HMA2")
        if p1 is not None and p2 is not None:
            if p1 <= p2 and h["HMA1"] > h["HMA2"]:
                ev.append("HMA_BULL_CROSS")
            elif p1 >= p2 and h["HMA1"] < h["HMA2"]:
                ev.append("HMA_BEAR_CROSS")
    line, up, lo = m.get("line"), m.get("upper"), m.get("lower")
    if None not in (line, up, lo):
        if line > up:
            ev.append("MACD_BB_ABOVE_UPPER")
        elif line < lo:
            ev.append("MACD_BB_BELOW_LOWER")
        else:
            ev.append("MACD_BB_INSIDE")
    return ev


def describe(c: dict) -> str:
    h, m = c.get("hull", {}), c.get("macd_bb", {})
    return (f"{c.get('symbol')} {c.get('tf')}m | "
            f"HMA1={h.get('HMA1')} HMA2={h.get('HMA2')} HMA3={h.get('HMA3')} "
            f"P={h.get('Pivot')} R1={h.get('R1')} S1={h.get('S1')} | "
            f"MACD-BB L={m.get('line')} U={m.get('upper')} B={m.get('lower')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--polls", type=int, default=12)
    ap.add_argument("--interval", type=float, default=5.0)
    a = ap.parse_args()

    day = dt.datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"signals-{day}.jsonl")
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))

    prev, n = None, 0
    print(f"logging -> {path}")
    with open(path, "a") as fh:
        while n < a.polls and not stop["flag"]:
            n += 1
            try:
                cur = read_chart()
            except Exception as e:
                print(f"[{n}] read error: {str(e)[:90]}")
                time.sleep(a.interval)
                continue
            ev = classify(prev, cur)
            rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"),
                   "symbol": cur.get("symbol"), "tf": cur.get("tf"),
                   "hull": cur.get("hull"), "macd_bb": cur.get("macd_bb"), "events": ev}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(f"[{n}] {describe(cur)}  {ev if ev else ''}")
            prev = cur
            if n < a.polls:
                time.sleep(a.interval)
    print("done")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Automated out-of-sample gate for strategy discovery.

Any ported candidate registers itself here; the runner then:
  1. evaluates it on the FULL window, on H1, and on H2 independently
  2. auto-DISCARDS anything that is not positive in BOTH halves
  3. auto-DISCARDS anything with fewer than MIN_TRADES (underpowered)
  4. reports fee drag: trade count and cost as a share of gross P&L
and finally tests survivors on a second asset.

Register new candidates with @candidate(...) and they are picked up automatically.
"""
from __future__ import annotations
import argparse, json, os
import pandas as pd, numpy as np

from lib_strategies import keltner_signals, simulate_events
from pine_port import compute
from lib_public import PUBLIC

MIN_TRADES = 15           # below this a positive result is noise
SIZE_USD = 250.0
FEE_BPS_RT = 5.0          # venue fee + slippage + gas, round trip

# ---------------- registry ----------------
REGISTRY = []

def candidate(family, **params):
    def deco(fn):
        REGISTRY.append({"family": family, "params": params, "sig": fn,
                         "name": f"{family}{params}" if params else family})
        return fn
    return deco


def _hmabsm(df, rapida, lenta, stdv, entry):
    d = compute(df, rapida=rapida, lenta=lenta, stdv=stdv)
    d["en"] = d["compra"] if entry == "bsm" else d["hma_bull"]
    d["ex"] = d["hma_bear"] | d["venta"]
    return d


def build_registry(keltner_grid=True, hmabsm_grid=True, public=True):
    REGISTRY.clear()
    if public:
        for name, fn in PUBLIC.items():
            def wrapped(df, fn=fn):
                d, ec, xc, mb = fn(df)
                return d, ec, xc, mb
            candidate(f"public/{name}")(wrapped)
    if keltner_grid:
        for klen in (50, 100, 200, 300):
            for atrlen in (50, 100, 200):
                for dev in (3, 4, 6, 8, 10):
                    for ex in ("ema", "band"):
                        xc = "k_exit_tp" if ex == "ema" else "k_exit_band"
                        def fn(df, klen=klen, atrlen=atrlen, dev=dev, xc=xc):
                            d = keltner_signals(df, klen=klen, atrlen=atrlen, dev=dev)
                            return d, "k_entry", xc, None
                        candidate(f"keltner/{klen}/{atrlen}/{dev}/{ex}")(fn)
    if hmabsm_grid:
        for rap in (6, 8, 12):
            for lent in (20, 26, 34):
                for sdv in (0.6, 0.8, 1.2):
                    for emode in ("bsm", "hma"):
                        def fn(df, rap=rap, lent=lent, sdv=sdv, emode=emode):
                            d = _hmabsm(df, rap, lent, sdv, emode)
                            return d, "en", "ex", None
                        candidate(f"hmabsm/{rap}/{lent}/{sdv}/{emode}")(fn)


def evaluate(sigfn, df, label):
    d, ec, xc, mb = sigfn(df)
    r = simulate_events(d, ec, xc, max_bars=mb, size_usd=SIZE_USD, fee_bps_rt=FEE_BPS_RT)
    gross = sum(abs(t["usd"]) for t in r["_trades"])
    return {"label": label, "trades": r["trades"], "net": r["net_usd"], "win": r["win_rate"],
            "aw": r["avg_win_bps"], "al": r["avg_loss_bps"], "bars": r["avg_bars"],
            "dd": r["max_dd_usd"], "fee_drag_pct": None, "_trades": r["_trades"]}


def run_on(path, tag):
    d0 = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    mid = len(d0) // 2
    H1, H2 = d0.iloc[:mid].reset_index(drop=True), d0.iloc[mid:].reset_index(drop=True)
    out = []
    for c in REGISTRY:
        f = evaluate(c["sig"], d0, "full")
        a = evaluate(c["sig"], H1, "H1")
        b = evaluate(c["sig"], H2, "H2")
        # fee drag: total cost paid / gross movement captured
        cost = f["trades"] * SIZE_USD * FEE_BPS_RT / 10000.0
        # fee drag = cost as a share of GROSS WINS (meaningful even when net < 0)
        gross_wins = max(sum(t["usd"] for t in f["_trades"] if t["usd"] > 0), 1e-9)
        out.append({**c["params"], "name": c["name"], "n": f["trades"], "net": f["net"],
                    "win": f["win"], "aw": f["aw"], "al": f["al"], "bars": f["bars"],
                    "dd": f["dd"], "H1": a["net"], "H2": b["net"],
                    "fee_usd": round(cost, 2),
                    "fee_drag_pct": round(100 * cost / gross_wins, 1),
                    "powered": f["trades"] >= MIN_TRADES,
                    "both": (a["net"] > 0) and (b["net"] > 0)})
    df = pd.DataFrame(out)
    df["KEEP"] = df.both & df.powered
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="ETH")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--oos", default=None, help="second asset csv for transfer test")
    ap.add_argument("--oos-tag", default="OOS")
    a = ap.parse_args()
    build_registry()
    df = run_on(a.csv, a.tag)
    df.to_csv(f"logs/auto_{a.tag}.csv", index=False)
    print(f"### {a.tag}: {len(df)} candidates")
    print(f"  positive (full)      {df.net.gt(0).sum():>4} ({df.net.gt(0).mean():.0%})")
    print(f"  positive BOTH halves {df.both.sum():>4} ({df.both.mean():.0%})")
    print(f"  adequate sample      {df.powered.sum():>4}")
    print(f"  KEEP (both + powered){df.KEEP.sum():>4}")
    print(f"  median trades {df.n.median():.0f}   median net ${df.net.median():.2f}")
    if df.n.median():
        print(f"  median fee drag {df.fee_drag_pct.median():.0f}% of gross gain")
    if df.KEEP.any():
        print("\n=== SURVIVORS ===")
        print(df[df.KEEP].sort_values("net", ascending=False)
                .head(15)[["name","n","net","win","bars","dd","H1","H2","fee_drag_pct"]].to_string(index=False))
    else:
        print("\n=== NO SURVIVORS -> every candidate is regime-lucky or underpowered ===")
    if a.oos and df.KEEP.any():
        keep = df[df.KEEP]
        d0 = pd.read_csv(a.oos).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        mid = len(d0)//2
        H1, H2 = d0.iloc[:mid].reset_index(drop=True), d0.iloc[mid:].reset_index(drop=True)
        print(f"\n=== transfer test of survivors -> {a.oos_tag} ===")
        for _, row in keep.iterrows():
            c = next(x for x in REGISTRY if x["name"] == row["name"])
            f = evaluate(c["sig"], d0, "full"); x = evaluate(c["sig"], H1, "H1"); y = evaluate(c["sig"], H2, "H2")
            verdict = "TRANSFERS" if f["net"] > 0 else "FAILS"
            print(f"  {row['name']:<34} {a.tag} ${row['net']:+8.2f} -> {a.oos_tag} ${f['net']:+8.2f} "
                  f"({f['trades']:>3} trades, H1 {x['net']:+.2f} H2 {y['net']:+.2f})  {verdict}")


if __name__ == "__main__":
    main()

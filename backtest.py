#!/usr/bin/env python3
"""Backtest the HMA420+BSM rules on 5m bars, with the pitfalls handled explicitly:

- signals evaluated on CLOSED bars only; the trade happens at the NEXT bar's open
  (no look-ahead, no same-bar fill)
- non-linear price impact from the size ladder, not a flat bps guess
- full parameter sweep to expose overfitting, not one flattering config
"""
from __future__ import annotations
import argparse, itertools, json
import numpy as np, pandas as pd
from pine_port import compute


def load(path):
    d = pd.read_csv(path)
    d = d.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return d


def simulate(d, size_usd=250.0, gas_usd=0.02, fee_bps_rt=3.0,
             exit_on_venta=True, exit_on_hma=True, require_hma=False,
             entry="bsm", impact_fn=None):
    """Trade on bar close signals, execute at the next bar's open."""
    pos = 0.0
    entry_px = None
    realized = []
    curve = []
    cum = 0.0
    n = len(d)
    o = d["open"].to_numpy(); cl = d["close"].to_numpy()
    compra = d["compra"].to_numpy(); venta = d["venta"].to_numpy()
    hb = d["hma_bull"].to_numpy(); hbear = d["hma_bear"].to_numpy()
    h_ok = (d["hma1"] > d["hma2"]).to_numpy()
    valid = d["banda_inf"].notna().to_numpy() & d["hma3"].notna().to_numpy()

    for i in range(n - 1):
        if not valid[i]:
            curve.append(cum); continue
        if pos == 0.0:
            want = compra[i] if entry == "bsm" else hb[i]
            if require_hma:
                want = want and h_ok[i]
            if want:
                px = o[i + 1]                      # next open = honest fill
                imp = impact_fn(size_usd, px) if impact_fn else 0.0
                pos, entry_px = size_usd / px, px
                costs = size_usd * (fee_bps_rt / 10000.0) + gas_usd + imp
                cum -= costs
        else:
            want = (exit_on_hma and hbear[i]) or (exit_on_venta and venta[i])
            if want:
                px = o[i + 1]
                imp = impact_fn(size_usd, px) if impact_fn else 0.0
                pnl = pos * (px - entry_px) - size_usd * (fee_bps_rt / 10000.0) - gas_usd - imp
                cum += pnl
                realized.append({"i": i, "t": int(d["time"].iloc[i]),
                                 "entry": entry_px, "exit": px, "usd": pnl})
                pos, entry_px = 0.0, None
        curve.append(cum)
    open_pos = pos * (cl[-1] - entry_px) if pos else 0.0
    eq = np.array(curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak).min() if len(eq) else 0.0
    wins = [t for t in realized if t["usd"] > 0]
    return {
        "trades": len(realized), "net_usd": round(cum, 3),
        "open_pnl_usd": round(float(open_pos), 3),
        "net_incl_open": round(cum + float(open_pos), 3),
        "win_rate": round(len(wins) / len(realized), 3) if realized else None,
        "avg_usd": round(cum / len(realized), 4) if realized else None,
        "max_dd_usd": round(float(dd), 3),
        "gross_win": round(sum(t["usd"] for t in realized if t["usd"] > 0), 3),
        "gross_loss": round(sum(t["usd"] for t in realized if t["usd"] <= 0), 3),
        "_trades": realized,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="bars_cb_5m_30d.csv")
    ap.add_argument("--sweep", action="store_true")
    a = ap.parse_args()
    raw = load(a.data)
    print(f"data: {len(raw)} bars, {a.data}")
    d = compute(raw)

    base = simulate(d)
    print("\n=== base config ===")
    print(json.dumps({k: v for k, v in base.items() if k != "_trades"}, indent=2))
    for t in base["_trades"][:8]:
        print(f"   {pd.to_datetime(t['t'], unit='s')}  in {t['entry']:.2f} -> out {t['exit']:.2f}  ${t['usd']:+.4f}")

    if a.sweep:
        print("\n=== parameter sweep (is there a stable region, or one lucky cell?) ===")
        rows = []
        for rap, lent, sdv, emode in itertools.product([6, 8, 12], [20, 26, 34], [0.6, 0.8, 1.2], ["bsm", "hma"]):
            dd_ = compute(raw, rapida=rap, lenta=lent, stdv=sdv)
            r = simulate(dd_, entry=emode)
            rows.append({"rapida": rap, "lenta": lent, "stdv": sdv, "entry": emode,
                         "trades": r["trades"], "net": r["net_incl_open"],
                         "win": r["win_rate"], "dd": r["max_dd_usd"]})
        s = pd.DataFrame(rows).sort_values("net", ascending=False)
        print(s.head(12).to_string(index=False))
        print(f"\ncells positive: {(s['net'] > 0).sum()}/{len(s)}   median net: {s['net'].median():.3f}")
        print(f"best {s.iloc[0]['net']:.2f} vs worst {s.iloc[-1]['net']:.2f}")


if __name__ == "__main__":
    main()

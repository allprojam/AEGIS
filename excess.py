"""Fair comparison for a bear-market window: does a strategy beat BUY & HOLD?
Absolute net is a misleading test for long-only systems in a falling market."""
import pandas as pd, numpy as np
from lib_public import PUBLIC
from lib_strategies import keltner_signals, simulate_events

def bh(df): return 100*(df.close.iloc[-1]/df.close.iloc[0]-1)

for csv, tag in (("bars_btc_1h_365d.csv","BTC"), ("bars_eth_1h_365d.csv","ETH")):
    d0 = pd.read_csv(csv).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    mid = len(d0)//2
    H1, H2 = d0.iloc[:mid].reset_index(drop=True), d0.iloc[mid:].reset_index(drop=True)
    b_full, b1, b2 = bh(d0), bh(H1), bh(H2)
    print(f"\n===== {tag} 365d 1h =====  buy&hold: full {b_full:+.1f}%  H1 {b1:+.1f}%  H2 {b2:+.1f}%")
    print(f"{'strategy':<28}{'net$':>9}{'ret%':>8}{'vs B&H':>9}{'H1 net':>8}{'H2 net':>8}")
    rows=[]
    for name, fn in PUBLIC.items():
        d, ec, xc, mb = fn(d0)
        f = simulate_events(d, ec, xc, max_bars=mb)
        a = simulate_events(fn(H1)[0], ec, xc, max_bars=mb)
        b = simulate_events(fn(H2)[0], ec, xc, max_bars=mb)
        ret = 100*f["net_usd"]/250.0
        rows.append((name, f["net_usd"], ret, ret-b_full, a["net_usd"], b["net_usd"], f["trades"]))
    for r in sorted(rows, key=lambda x:-x[3]):
        print(f"{r[0]:<28}{r[1]:>9.2f}{r[2]:>8.1f}{r[3]:>+9.1f}{r[4]:>8.2f}{r[5]:>8.2f}")

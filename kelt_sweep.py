"""Sweep the Keltner mean-reversion family on 30d first: is there a stable region?"""
import itertools, pandas as pd, numpy as np
from lib_strategies import keltner_signals, simulate_events
raw = pd.read_csv("bars_cb_5m_30d.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
rows=[]
for klen, atrlen, dev, exitmode in itertools.product([100,200,300],[50,100,200],[4,6,8,10],["ema","band"]):
    d = keltner_signals(raw, klen=klen, atrlen=atrlen, dev=dev)
    xc = "k_exit_tp" if exitmode=="ema" else "k_exit_band"
    r = simulate_events(d, "k_entry", xc)
    rows.append({"klen":klen,"atrlen":atrlen,"dev":dev,"exit":exitmode,"trades":r["trades"],
                 "net":r["net_usd"],"win":r["win_rate"],"aw":r["avg_win_bps"],"al":r["avg_loss_bps"],
                 "bars":r["avg_bars"],"dd":r["max_dd_usd"]})
s=pd.DataFrame(rows)
print("--- top 12 by net ---"); print(s.sort_values("net",ascending=False).head(12).to_string(index=False))
print(f"\ncells: {len(s)}  positive: {(s.net>0).sum()}  median net: {s.net.median():.2f}")
print(f"trades range: {s.trades.min()}-{s.trades.max()}   median trades: {s.trades.median():.0f}")
print("\n--- by exit mode ---")
print(s.groupby("exit")[["net","trades","win"]].median().to_string())

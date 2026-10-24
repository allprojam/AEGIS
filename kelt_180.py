"""Keltner mean-reversion family on 180 days, with a split-half out-of-sample check.
If a config only works in one half, it is regime luck, not edge."""
import itertools, pandas as pd, numpy as np
from lib_strategies import keltner_signals, simulate_events

d0 = pd.read_csv("bars_cb_5m_180d.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
mid = len(d0)//2
halves = {"H1": d0.iloc[:mid].reset_index(drop=True), "H2": d0.iloc[mid:].reset_index(drop=True)}
print(f"bars {len(d0)} | H1 {len(halves['H1'])}  H2 {len(halves['H2'])}")
print(f"H1 {pd.to_datetime(halves['H1'].time.iloc[0],unit='s')} -> {pd.to_datetime(halves['H1'].time.iloc[-1],unit='s')}")
print(f"H2 {pd.to_datetime(halves['H2'].time.iloc[0],unit='s')} -> {pd.to_datetime(halves['H2'].time.iloc[-1],unit='s')}\n")

rows=[]
for klen, atrlen, dev, ex in itertools.product([50,100,200,300],[50,100,200],[3,4,6,8,10],["ema","band"]):
    d = keltner_signals(d0, klen=klen, atrlen=atrlen, dev=dev)
    xc = "k_exit_tp" if ex=="ema" else "k_exit_band"
    full = simulate_events(d, "k_entry", xc)
    rec = {"klen":klen,"atrlen":atrlen,"dev":dev,"exit":ex,
           "n":full["trades"],"net":full["net_usd"],"win":full["win_rate"],
           "aw":full["avg_win_bps"],"al":full["avg_loss_bps"],"bars":full["avg_bars"],"dd":full["max_dd_usd"]}
    for tag, half in halves.items():
        dh = keltner_signals(half, klen=klen, atrlen=atrlen, dev=dev)
        rh = simulate_events(dh, "k_entry", xc)
        rec[tag+"_net"] = rh["net_usd"]; rec[tag+"_n"] = rh["trades"]
    rows.append(rec)
s = pd.DataFrame(rows)
s["both_pos"] = (s.H1_net > 0) & (s.H2_net > 0)
s.to_csv("logs/kelt_180_results.csv", index=False)

print("=== top 15 by full-period net (min 20 trades) ===")
q = s[s.n >= 20].sort_values("net", ascending=False)
print(q.head(15).to_string(index=False))
print(f"\ncells: {len(s)}   positive full: {(s.net>0).sum()}   both-halves positive: {s.both_pos.sum()}")
print(f"median trades: {s.n.median():.0f}   median net: {s.net.median():.2f}")
print("\n=== the ones that survive BOTH halves (candidate real edge) ===")
b = s[s.both_pos & (s.n>=20)].sort_values("net", ascending=False)
if len(b): print(b.to_string(index=False))
else: print("none with >=20 trades")

#!/usr/bin/env python3
"""Parameter grid on any timeframe, with an H1/H2 out-of-sample split.
grid.py <csv> <family: keltner|hmabsm> [tag]"""
import itertools, json, sys
import pandas as pd, numpy as np
from lib_strategies import keltner_signals, simulate_events
from pine_port import compute

path, fam = sys.argv[1], sys.argv[2]
tag = sys.argv[3] if len(sys.argv) > 3 else fam
d0 = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
mid = len(d0) // 2
H1, H2 = d0.iloc[:mid].reset_index(drop=True), d0.iloc[mid:].reset_index(drop=True)
bh_f = 100*(d0.close.iloc[-1]/d0.close.iloc[0]-1)
bh_1 = 100*(H1.close.iloc[-1]/H1.close.iloc[0]-1)
bh_2 = 100*(H2.close.iloc[-1]/H2.close.iloc[0]-1)
print(f"### {tag}: {len(d0)} bars  buy&hold H1 {bh_1:+.1f}%  H2 {bh_2:+.1f}%  full {bh_f:+.1f}%")

def run(df, ec, xc, mb=None):
    return simulate_events(df, ec, xc, max_bars=mb)

rows = []
if fam == "keltner":
    for klen, atrlen, dev, ex in itertools.product([50,100,200,300],[50,100,200],[3,4,6,8,10],["ema","band"]):
        xc = "k_exit_tp" if ex == "ema" else "k_exit_band"
        f = run(keltner_signals(d0,klen,atrlen,dev), "k_entry", xc)
        a = run(keltner_signals(H1,klen,atrlen,dev), "k_entry", xc)
        b = run(keltner_signals(H2,klen,atrlen,dev), "k_entry", xc)
        rows.append(dict(klen=klen,atrlen=atrlen,dev=dev,exit=ex, n=f["trades"], net=f["net_usd"],
                         win=f["win_rate"], aw=f["avg_win_bps"], al=f["avg_loss_bps"],
                         bars=f["avg_bars"], dd=f["max_dd_usd"], H1=a["net_usd"], H2=b["net_usd"]))
else:
    for rap, lent, sdv, emode in itertools.product([6,8,12],[20,26,34],[0.6,0.8,1.2],["bsm","hma"]):
        def sig(df):
            d = compute(df, rapida=rap, lenta=lent, stdv=sdv)
            d["en"] = d["compra"] if emode=="bsm" else d["hma_bull"]
            d["ex"] = d["hma_bear"] | d["venta"]
            return d
        f = run(sig(d0), "en", "ex"); a = run(sig(H1), "en", "ex"); b = run(sig(H2), "en", "ex")
        rows.append(dict(rapida=rap,lenta=lent,stdv=sdv,entry=emode, n=f["trades"], net=f["net_usd"],
                         win=f["win_rate"], aw=f["avg_win_bps"], al=f["avg_loss_bps"],
                         bars=f["avg_bars"], dd=f["max_dd_usd"], H1=a["net_usd"], H2=b["net_usd"]))

s = pd.DataFrame(rows)
s["both"] = (s.H1 > 0) & (s.H2 > 0)
s.to_csv(f"logs/grid_{tag}.csv", index=False)
print(f"cells {len(s)}  positive {s.net.gt(0).sum()} ({s.net.gt(0).mean():.0%})  "
      f"both-halves {s.both.sum()} ({s.both.mean():.0%})  median net {s.net.median():.2f}  "
      f"median trades {s.n.median():.0f}  corr(H1,H2) {s.H1.corr(s.H2):+.3f}")
print("\ntop 10 by net:")
print(s.sort_values("net",ascending=False).head(10).to_string(index=False))
print("\n=== survivors (both halves positive, >=15 trades) ===")
b = s[s.both & (s.n>=15)].sort_values("net",ascending=False)
print(b.to_string(index=False) if len(b) else "none")

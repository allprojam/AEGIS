"""Test the custom design on BTC (apex) 3 years, with the fair benchmark: buy & hold."""
import pandas as pd, numpy as np
from custom import custom, simulate_trail, bh

d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
d0["dt"] = pd.to_datetime(d0.time, unit="s")
print(f"BTC 1h {len(d0)} bars  buy&hold {bh(d0):+.1f}%\n")

best = None
rows = []
for regime_len in (100, 200, 300):
    for slope_len in (10, 20, 40):
        for entry_len in (20, 50, 100):
            for atr_mult in (2.5, 4.0, 6.0):
                d = custom(d0, regime_len=regime_len, slope_len=slope_len,
                           entry_len=entry_len, atr_mult=atr_mult)
                r = simulate_trail(d)
                ret = 100*r["net_usd"]/250.0
                rows.append(dict(regime_len=regime_len, slope_len=slope_len, entry_len=entry_len,
                                 atr_mult=atr_mult, n=r["trades"], net=r["net_usd"], ret=ret,
                                 win=r["win_rate"], bars=r["avg_bars"], dd=r["max_dd_usd"],
                                 vs=ret-bh(d0)))
s = pd.DataFrame(rows).sort_values("ret", ascending=False)
print(f"cells {len(s)}  positive {(s.ret>0).sum()} ({(s.ret>0).mean():.0%})  "
      f"beat B&H {(s.vs>0).sum()} ({(s.vs>0).mean():.0%})")
print("\ntop 12:")
print(s.head(12).to_string(index=False))

# yearly breakdown of the best
b = s.iloc[0]
print(f"\n=== best config: regime={int(b.regime_len)} slope={int(b.slope_len)} entry={int(b.entry_len)} atr={b.atr_mult} ===")
print(f"{'year':<8}{'strategy':>12}{'buy&hold':>12}{'trades':>8}")
for y in sorted(d0.dt.dt.year.unique()):
    sl = d0[d0.dt.dt.year == y].reset_index(drop=True)
    r = simulate_trail(custom(sl, regime_len=int(b.regime_len), slope_len=int(b.slope_len),
                              entry_len=int(b.entry_len), atr_mult=b.atr_mult))
    print(f"{y:<8}{100*r['net_usd']/250.0:>+12.1f}{bh(sl):>+12.1f}{r['trades']:>8}")

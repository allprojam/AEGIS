import pandas as pd, numpy as np
from custom import custom, simulate_trail, bh
d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
d0["dt"]=pd.to_datetime(d0.time,unit="s")
B=bh(d0)
print(f"BTC 1h 3y  buy&hold {B:+.1f}%\n")
print(f"{'reg':>5}{'entry':>6}{'atrX':>6}{'n':>5}{'ret%':>8}{'win':>7}{'bars':>7}{'vs B&H':>9}")
best=None
for rl in (200,300,400):
    for el in (50,100,150):
        for am in (4.0,6.0,8.0,10.0):
            r=simulate_trail(custom(d0,regime_len=rl,slope_len=20,entry_len=el,atr_mult=am))
            ret=100*r["net_usd"]/250.0
            if best is None or ret>best[0]: best=(ret,rl,el,am,r)
            print(f"{rl:>5}{el:>6}{am:>6}{r['trades']:>5}{ret:>8.1f}{(r['win_rate'] or 0):>7.2f}{(r['avg_bars'] or 0):>7.1f}{ret-B:>+9.1f}")
print(f"\nbest: {best[0]:+.1f}% (regime={best[1]} entry={best[2]} atr={best[3]}) vs B&H {B:+.1f}%")

"""CONTROL: the simplest possible timing system, to prove the result isn't an artefact
of my ATR trail or breakout logic. Just: hold BTC when the regime filter is on, else flat.
No breakout, no stop, no trail."""
import pandas as pd, numpy as np
from custom import bh

d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
d0["dt"] = pd.to_datetime(d0.time, unit="s")
c = d0["close"]

def hold_when(mask):
    """Return % of holding only on masked bars, 5bps per switch."""
    pos = 0; cum = 1.0; switches = 0
    r = c.pct_change().fillna(0).to_numpy(); m = mask.to_numpy()
    for i in range(1, len(d0)):
        if m[i] and pos == 0: pos = 1; switches += 1; cum *= (1 - 0.0005)
        elif not m[i] and pos == 1: pos = 0; switches += 1; cum *= (1 - 0.0005)
        if pos: cum *= (1 + r[i])
    return 100*(cum-1), switches

print(f"buy & hold: {bh(d0):+.1f}%\n")
print(f"{'regime filter':<34}{'ret%':>9}{'switches':>10}{'vs B&H':>10}")
for rl in (50, 100, 200, 300, 400):
    reg = c.rolling(rl).mean()
    for sl in (0, 20):
        m = c > reg
        if sl: m = m & (reg > reg.shift(sl))
        ret, sw = hold_when(m)
        print(f"SMA{rl} {'+ slope'+str(sl) if sl else '          ':>14}{ret:>9.1f}{sw:>10}{ret-bh(d0):>+10.1f}")

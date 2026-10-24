#!/usr/bin/env python3
"""Does macro data (VIX as the testable proxy for 'macro sentiment') improve TIMING or
SIZING on SPX? Benchmarked against buy & hold, which has beaten everything so far.

No lookahead: every exposure uses data up to bar i-1 to set the position on bar i.

NOTE on data joins: SPX daily bars are stamped 14:30 UTC and VIX at 08:00 UTC, so both
must be normalised to a DATE before merging or the join silently returns nothing.
"""
import numpy as np, pandas as pd

def load(f):
    d = pd.read_csv(f).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"] = pd.to_datetime(d.time, unit="s", utc=True).dt.normalize()
    return d.set_index("dt")["close"]

spx = load("bars_spx_fresh_1d.csv"); vix = load("bars_vix_1d.csv")
df = pd.DataFrame({"spx": spx, "vix": vix}).dropna()
r = df.spx.pct_change().fillna(0).to_numpy()
v = df.vix.to_numpy(); n = len(df)
print(f"SPX+VIX overlap {df.index[0].date()} -> {df.index[-1].date()}  ({n} days, {n/252:.1f} yrs)\n")

def stats(eq):
    e = (1+eq).cumprod(); pk = np.maximum.accumulate(e)
    dd = 100*((e-pk)/pk).min(); yrs = n/252
    return 100*(e[-1]-1), 100*(e[-1]**(1/yrs)-1), dd, np.mean(eq)/np.std(eq)*np.sqrt(252)

def run(exp):
    exp = np.nan_to_num(np.asarray(exp, dtype=float))
    return stats(exp*r)

rows = [("buy & hold", np.ones(n))]
for th in (20, 25, 30):
    e = np.where(np.roll(v,1) < th, 1.0, 0.0); e[0] = 0
    rows.append((f"VIX < {th} else cash", e))
for k in (15, 20, 25):                       # the user's idea: size down when stress is high
    e = np.clip(k/np.roll(v,1), 0, 1.0); e[0] = 0
    rows.append((f"size = {k}/VIX", e))
for tgt in (0.10, 0.15, 0.20):              # vol targeting, the standard version
    rv = pd.Series(r).rolling(20).std().to_numpy()*np.sqrt(252)
    e = np.clip(tgt/np.roll(rv,1), 0, 1.5); e[0] = 0
    rows.append((f"vol target {int(tgt*100)}%", e))

print(f"{'strategy':<24}{'total%':>11}{'CAGR%':>8}{'maxDD%':>9}{'Sharpe':>8}{'ret/DD':>8}")
bh = None
for name, exp in rows:
    tot, cagr, dd, sh = run(exp)
    if bh is None: bh = tot
    print(f"{name:<24}{tot:>11,.0f}{cagr:>8.2f}{dd:>9.1f}{sh:>8.2f}{tot/abs(dd):>8.2f}")

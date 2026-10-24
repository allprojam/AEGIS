"""Five public strategies on 3 years of BTC 1h, split into yearly slices.
Tests whether the 'beats buy & hold' property survives MULTIPLE regimes."""
import pandas as pd, numpy as np, datetime as dt
from lib_public import PUBLIC
from lib_strategies import simulate_events

def bh(df): return 100*(df.close.iloc[-1]/df.close.iloc[0]-1)

d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
d0["dt"] = pd.to_datetime(d0.time, unit="s")
years = sorted(d0.dt.dt.year.unique())
print(f"BTC 1h: {len(d0)} bars, {d0.dt.iloc[0].date()} -> {d0.dt.iloc[-1].date()}")
print(f"full-period buy&hold {bh(d0):+.1f}%\n")

hdr = f"{'strategy':<24}" + "".join(f"{y:>10}" for y in years) + f"{'FULL':>10}{'vsB&H':>9}"
print(hdr); print("-"*len(hdr))
print(f"{'buy & hold':<24}" + "".join(f"{bh(d0[d0.dt.dt.year==y]):>+10.1f}" for y in years) + f"{bh(d0):>+10.1f}")
print()
rows=[]
for name, fn in PUBLIC.items():
    cells, nets = [], []
    for y in years:
        sl = d0[d0.dt.dt.year == y].reset_index(drop=True)
        d, ec, xc, mb = fn(sl)
        r = simulate_events(d, ec, xc, max_bars=mb)
        cells.append(100*r["net_usd"]/250.0); nets.append((r["net_usd"], r["trades"]))
    d, ec, xc, mb = fn(d0)
    full = simulate_events(d, ec, xc, max_bars=mb)
    ret = 100*full["net_usd"]/250.0
    pos_years = sum(1 for c in cells if c > 0)
    rows.append((name, cells, ret, ret - bh(d0), pos_years, full["trades"], sum(n for _, n in nets)))
    print(f"{name:<24}" + "".join(f"{c:>+10.1f}" for c in cells) + f"{ret:>+10.1f}{ret-bh(d0):>+9.1f}")

print("\n=== summary (BTC 3y, 1h) ===")
print(f"{'strategy':<24}{'trades':>8}{'profitable yrs':>16}{'full ret%':>11}{'vs B&H':>9}")
for name, cells, ret, ex, py, ft, _ in sorted(rows, key=lambda x:-x[2]):
    print(f"{name:<24}{ft:>8}{py:>10}/{len(years):<5}{ret:>11.1f}{ex:>+9.1f}")

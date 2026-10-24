"""Return alone is the wrong scoreboard for a volatile asset. Measure drawdown too:
a system that returns half as much with a quarter of the drawdown may be the better trade."""
import pandas as pd, numpy as np
from custom import custom, simulate_trail, bh

d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
d0["dt"] = pd.to_datetime(d0.time, unit="s")

def bh_dd(df):
    eq = df.close.to_numpy(); pk = np.maximum.accumulate(eq)
    return float(((eq-pk)/pk).min()*100)

print(f"BTC 1h 3y: buy&hold return {bh(d0):+.1f}%   max drawdown {bh_dd(d0):.1f}%")
print(f"            return/|DD| = {bh(d0)/abs(bh_dd(d0)):.2f}\n")

rows=[]
for regime_len in (200,300,400):
    for entry_len in (50,100,150):
        for atr_mult in (4.0,6.0,8.0,10.0):
            d = custom(d0, regime_len=regime_len, slope_len=20, entry_len=entry_len, atr_mult=atr_mult)
            r = simulate_trail(d)
            ret = 100*r["net_usd"]/250.0
            bd = None
            rows.append(dict(regime_len=regime_len, entry_len=entry_len, atr_mult=atr_mult,
                             n=r["trades"], ret=ret, win=r["win_rate"], bars=r["avg_bars"],
                             dd_usd=r["max_dd_usd"], dd_pct=100*r["max_dd_usd"]/250.0,
                             rdd=ret/abs(100*r["max_dd_usd"]/250.0) if r["max_dd_usd"] else 0))
s = pd.DataFrame(rows)
s["vs_bh_rdd"] = s.rdd - bh(d0)/abs(bh_dd(d0))
print(f"{'reg':>5}{'entry':>6}{'atrX':>6}{'n':>5}{'ret%':>8}{'maxDD%':>8}{'ret/DD':>8}{'vs B&H':>9}{'bars':>7}")
for _, r in s.sort_values("rdd", ascending=False).head(14).iterrows():
    print(f"{int(r.regime_len):>5}{int(r.entry_len):>6}{r.atr_mult:>6}{int(r.n):>5}{r.ret:>8.1f}{r.dd_pct:>8.1f}{r.rdd:>8.2f}{r.vs_bh_rdd:>+9.2f}{r.bars:>7.1f}")
print(f"\ncells beating B&H on return/DD: {(s.vs_bh_rdd>0).sum()}/{len(s)}")
s.to_csv("logs/custom_riskadj.csv", index=False)

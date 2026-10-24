"""CONTROL, third attempt. The previous version was INVALID: it set the position from
close[i] and then collected bar i's return, which is lookahead. Signals must be lagged
one bar: decide at i-1, hold through bar i."""
import pandas as pd, numpy as np

d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
close = d0["close"].to_numpy()
ret = np.zeros(len(close)); ret[1:] = close[1:]/close[:-1] - 1
COST = 0.0005

def timing(mask):
    """mask[i] is the DECISION taken at the close of bar i; it governs bar i+1."""
    m = np.asarray(mask, dtype=bool)
    pos = 0; eq = 1.0; sw = 0
    for i in range(1, len(close)):
        want = m[i-1]                      # <- LAG: decide on previous close
        if want and pos == 0:
            pos, sw, eq = 1, sw+1, eq*(1-COST)
        elif not want and pos == 1:
            pos, sw, eq = 0, sw+1, eq*(1-COST)
        if pos:
            eq *= (1 + ret[i])
    return 100*(eq-1), sw

bh_true = 100*(close[-1]/close[0]-1)
chk, sw = timing(np.ones(len(close), dtype=bool))
print(f"buy & hold: {bh_true:+.1f}%    unit test always-in: {chk:+.1f}%  switches={sw}")
assert abs(chk-(bh_true-0.05)) < 0.2
print("self-test PASSED  (mask now lagged one bar)\n")

c = pd.Series(close, index=d0.index)
print(f"{'regime filter':<30}{'ret%':>10}{'switches':>10}{'vs B&H':>10}")
res=[]
for rl in (50,100,200,300,400):
    reg = c.rolling(rl).mean()
    for tag, m in (("", c > reg), ("+slope20", (c > reg) & (reg > reg.shift(20)))):
        r, s = timing(m.fillna(False))
        res.append((f"SMA{rl}{tag}", r, s))
        print(f"SMA{rl} {tag:<22}{r:>10.1f}{s:>10}{r-bh_true:>+10.1f}")
    print()
print(f"best timing filter beats B&H: {sum(1 for _,r,_ in res if r>bh_true)}/{len(res)}")

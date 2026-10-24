"""CONTROL, rewritten with a self-test.
UNIT TEST: mask=all-True must reproduce buy&hold minus costs. If it does not, the
harness is wrong and no output from it may be reported."""
import pandas as pd, numpy as np

d0 = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
d0["dt"] = pd.to_datetime(d0.time, unit="s")
close = d0["close"].to_numpy()
ret = np.zeros(len(close)); ret[1:] = close[1:]/close[:-1] - 1
COST = 0.0005

def timing(mask):
    pos = 0; eq = 1.0; sw = 0
    m = np.asarray(mask, dtype=bool)
    for i in range(len(close)):
        if m[i] and pos == 0:
            pos, sw, eq = 1, sw+1, eq*(1-COST)
        elif not m[i] and pos == 1:
            pos, sw, eq = 0, sw+1, eq*(1-COST)
        if pos:
            eq *= (1 + ret[i])
    return 100*(eq-1), sw

bh_true = 100*(close[-1]/close[0]-1)
print(f"buy & hold actual: {bh_true:+.1f}%")
chk, sw = timing(np.ones(len(close), dtype=bool))
print(f"UNIT TEST always-in: {chk:+.1f}%  (expect buy&hold minus one 5bps switch)  switches={sw}")
assert abs(chk - (bh_true - 0.05)) < 0.2, "HARNESS FAILED SELF-TEST -> discard results"
print("self-test PASSED\n")

c = pd.Series(close, index=d0.index)
print(f"{'regime filter':<30}{'ret%':>10}{'switches':>10}{'vs B&H':>10}")
for rl in (50, 100, 200, 300, 400):
    reg = c.rolling(rl).mean()
    for tag, m in (("", c > reg), ("+slope20", (c > reg) & (reg > reg.shift(20)))):
        r, s = timing(m.fillna(False))
        print(f"SMA{rl} {tag:<22}{r:>10.1f}{s:>10}{r-bh_true:>+10.1f}")
    print()

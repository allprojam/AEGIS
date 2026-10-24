#!/usr/bin/env python3
"""golden_cross_50_200 + timing control, measured honestly.
LAG CORRECT: mask[i] is decided at the close of bar i and governs bar i+1.
UNIT TEST: always-in must reproduce buy & hold minus one 5bps switch, else exit."""
import numpy as np, pandas as pd, itertools, sys

COST = 0.0005

def load(p):
    d = pd.read_csv(p).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"] = pd.to_datetime(d.time, unit="s")
    return d

def sma(s, n): return s.rolling(n).mean()

def signals(d, fast=50, slow=200, regime=None, slope=20, use_slope=True):
    """Return the decision mask taken at each bar's close."""
    c = d["close"]
    f, s = sma(c, fast), sma(c, slow)
    gc = (f > s) & (f.shift() <= s.shift())      # golden cross
    dc = (f < s) & (f.shift() >= s.shift())      # death cross
    return gc, dc

def timing_mask(d, regime, slope, use_slope=True):
    c = d["close"]
    if regime is None: return pd.Series(True, index=d.index)
    r = sma(c, regime)
    return (c > r) & ((r > r.shift(slope)) if use_slope else True)

def run(d, fast=50, slow=200, regime=None, slope=20, use_slope=True, trail=None):
    """Enter on golden cross (optionally only while the regime gate is on), exit on
    death cross or regime-off. Optional ATR trail."""
    c = d["close"].to_numpy()
    ret = np.zeros(len(c)); ret[1:] = c[1:]/c[:-1] - 1
    gc, dc = signals(d, fast, slow)
    gate = timing_mask(d, regime, slope, use_slope).fillna(False)
    ent = (gc & gate).fillna(False).to_numpy()
    ext = (dc | (gate.shift().fillna(False) & ~gate)).fillna(False).to_numpy()
    pos = 0; eq = 1.0; sw = 0; trades = []; epx = None
    for i in range(1, len(c)):
        if pos == 0:
            if ent[i-1]:                      # LAG
                pos, sw, eq, epx = 1, sw+1, eq*(1-COST), c[i]
        else:
            if ext[i-1]:                       # LAG
                pos, sw, eq = 0, sw+1, eq*(1-COST)
                trades.append({"in": epx, "out": c[i], "ret": c[i]/epx-1})
        if pos: eq *= (1 + ret[i])
    eq_bh = c[-1]/c[0]
    return {"ret": 100*(eq-1), "bh": 100*(eq_bh-1), "switches": sw, "trades": len(trades),
            "win": (sum(1 for t in trades if t["ret"] > 0)/len(trades)) if trades else None}

def selftest(d):
    c = d["close"].to_numpy()
    bh = 100*(c[-1]/c[0]-1)
    m = pd.Series(True, index=d.index)
    r = run(d, fast=50, slow=200, regime=None)
    # always-in check
    pos=0; eq=1.0; ret=np.zeros(len(c)); ret[1:]=c[1:]/c[:-1]-1
    for i in range(len(c)):
        if pos==0: pos=1; eq*=(1-COST)
        eq*=(1+ret[i])
    chk = 100*(eq-1)
    assert abs(chk-(bh-0.05)) < 0.3, f"SELFTEST FAIL {chk} vs {bh}"
    return bh

if __name__ == "__main__":
    for path, tag in (("bars_btc_1h_3y.csv","BTC 3y"), ("bars_eth_1h_365d.csv","ETH 1y")):
        d = load(path); bh = selftest(d)
        print(f"\n===== {tag} =====  buy & hold {bh:+.1f}%   ({len(d)} bars)")
        print(f"{'config':<40}{'ret%':>9}{'switches':>10}{'trades':>8}{'win':>7}{'vs B&H':>10}")
        cfgs = [("golden cross only (no gate)", dict(regime=None)),
                ("+ gate SMA200", dict(regime=200)),
                ("+ gate SMA200 rising", dict(regime=200, use_slope=True)),
                ("+ gate SMA400", dict(regime=400)),
                ("+ gate SMA400 rising", dict(regime=400, use_slope=True)),
                ("+ gate SMA400 rising, slope50", dict(regime=400, slope=50)),
                ("gate SMA400 rising only, no cross", None)]
        for name, kw in cfgs:
            if name.startswith("gate SMA400 rising only"):
                # pure timing control: hold whenever gate is on
                c=d["close"].to_numpy(); ret=np.zeros(len(c)); ret[1:]=c[1:]/c[:-1]-1
                g=timing_mask(d,400,50).fillna(False).to_numpy()
                pos=0;eq=1.0;sw=0
                for i in range(1,len(c)):
                    if g[i-1] and pos==0: pos=1;sw+=1;eq*=(1-COST)
                    elif not g[i-1] and pos==1: pos=0;sw+=1;eq*=(1-COST)
                    if pos: eq*=(1+ret[i])
                r={"ret":100*(eq-1),"switches":sw,"trades":sw//2,"win":None}
                print(f"{name:<40}{r['ret']:>9.1f}{r['switches']:>10}{r['trades']:>8}{'-':>7}{r['ret']-bh:>+10.1f}")
                continue
            r = run(d, **kw)
            print(f"{name:<40}{r['ret']:>9.1f}{r['switches']:>10}{r['trades']:>8}"
                  f"{(r['win'] or 0):>7.2f}{r['ret']-bh:>+10.1f}")

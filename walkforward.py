#!/usr/bin/env python3
"""Walk-forward (anchored) test of E2 on BTC 1h.
Each fold picks params using ONLY the training window, then trades the next window that
the selection never saw. This is the real-time question: would this have worked if we
had been choosing params as we went? No future information reaches the parameter choice.
"""
import numpy as np, pandas as pd, itertools, math

COST = 0.0005
GRID = list(itertools.product((10,14,20),(80,100,120),(1.5,2.0,2.5)))   # fast, slow, k

def precompute(c, hi, lo):
    return c

def arrays(d, fast, slow, bb_k):
    c = d.close
    f = c.rolling(fast).mean()
    s = c.rolling(slow).mean()
    basis = c.rolling(slow).mean(); sd = c.rolling(slow).std()
    up = basis + bb_k*sd
    ent = ((c > s) & (c.shift() <= s.shift()) & (f > s)).fillna(False).to_numpy()
    ext = ((c > up) & (c > f)).fillna(False).to_numpy()
    return ent, ext

def sim(c, ent, ext, lo, hi):
    pos = 0; eq = 1.0; n_tr = 0; ei = None
    for i in range(lo+1, hi):
        if pos:
            eq *= c[i]/c[i-1]
        if pos == 0 and ent[i]:
            pos = 1; ei = i; eq *= (1-COST)
        elif pos == 1 and ext[i]:
            pos = 0; n_tr += 1; eq *= (1-COST)
    return eq, n_tr

if __name__ == "__main__":
    d = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    c = d.close.to_numpy(); n = len(c)
    # precompute every param combo once
    A = {(f,s,k): arrays(d,f,s,k) for f,s,k in GRID}
    TRAIN, TEST = 9000, 2500
    print(f"BTC 1h {n} bars. Walk-forward: train {TRAIN} bars -> test {TEST} bars, roll forward.")
    print(f"param grid: {len(GRID)} combos (fast, slow, bb_k)\n")
    print(f"{'fold':>5}{'test from':>20}{'chosen params':>26}{'train%':>9}{'TEST%':>9}{'trades':>8}")
    start = 0; oos_eq = 1.0; folds = 0; wins = 0
    while start + TRAIN + TEST <= n:
        tr_lo, tr_hi = start, start+TRAIN
        te_lo, te_hi = start+TRAIN, start+TRAIN+TEST
        best = None
        for p in GRID:
            ent, ext = A[p]
            eq, nt = sim(c, ent, ext, tr_lo, tr_hi)
            if nt >= 3 and (best is None or eq > best[0]): best = (eq, p, nt)
        if best is None: break
        eq_tr, p, nt_tr = best
        ent, ext = A[p]
        eq_te, nt_te = sim(c, ent, ext, te_lo, te_hi)
        oos_eq *= eq_te; folds += 1; wins += (eq_te > 1)
        ts = pd.to_datetime(d.time.iloc[te_lo], unit="s").strftime("%Y-%m-%d")
        print(f"{folds:>5}{ts:>20}{str(p):>26}{100*(eq_tr-1):>9.1f}{100*(eq_te-1):>9.1f}{nt_te:>8}")
        start += TEST
    bh = c[-1]/c[0] - 1
    print(f"\nWALK-FORWARD total (compounded OOS): {100*(oos_eq-1):+.1f}%   folds {folds}  profitable folds {wins}/{folds}")
    print(f"buy & hold over the FULL series (incl. the initial train window): {100*bh:+.1f}%")
    print(f"\nFor reference, E2 with params FIXED at (14,100,2.0) over the whole series: +101.0%")

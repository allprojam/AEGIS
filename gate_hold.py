#!/usr/bin/env python3
"""GATE AS A REGIME FILTER FOR BUY & HOLD TIMING.

Question: hold BTC while a regime filter says 'favourable', step aside into cash when it
breaks. Does that beat simply holding, AFTER FEES?

Design notes that matter:
  * Signal is decided at bar i's close and the position applies from bar i+1 -> no lookahead.
  * Cash leg earns 0 (conservative; stablecoin yield would only help the strategy).
  * Fees charged per switch (in and out), tested across a realistic range.
  * Reported on the FULL series, the RECENT window, both halves, and per year.
"""
import numpy as np, pandas as pd

def sma(s, n): return s.rolling(n).mean()

def run(d, regime_len=200, slope=0, cost_bps=5.0):
    c = d.close.to_numpy(); n = len(c)
    ret = np.zeros(n); ret[1:] = c[1:]/c[:-1] - 1
    reg = sma(d.close, regime_len).to_numpy()
    on = c > reg
    if slope:
        rising = reg > np.roll(reg, slope); rising[:slope] = False
        on = on & rising
    on = on & ~np.isnan(reg)
    pos = 0; eq = 1.0; sw = 0; bars_in = 0
    for i in range(1, n):
        want = on[i-1]                      # decided on previous close
        if want and pos == 0:
            pos = 1; sw += 1; eq *= (1 - cost_bps/10000.0)
        elif not want and pos == 1:
            pos = 0; sw += 1; eq *= (1 - cost_bps/10000.0)
        if pos:
            eq *= (1 + ret[i]); bars_in += 1
    bh = c[-1]/c[0]
    return {"ret": 100*(eq-1), "bh": 100*(bh-1), "switches": sw,
            "exposure": 100*bars_in/(n-1), "vs": 100*(eq-bh)}

def window(d, lo, hi):
    return d.iloc[lo:hi].reset_index(drop=True)

if __name__ == "__main__":
    d = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"] = pd.to_datetime(d.time, unit="s")
    n = len(d)
    print(f"BTC 1h, {n} bars, {d.dt.iloc[0].date()} -> {d.dt.iloc[-1].date()}")
    print("cash leg earns 0%. fees per switch.\n")
    for label, sl in (("FULL SERIES", d),
                      ("RECENT (~16mo, bars 9000+)", window(d, 9000, n)),
                      ("H1", window(d, 0, n//2)),
                      ("H2", window(d, n//2, n))):
        bh = 100*(sl.close.iloc[-1]/sl.close.iloc[0]-1)
        print(f"===== {label} =====  buy & hold {bh:+.1f}%")
        print(f"{'filter':<26}{'fee':>6}{'ret%':>9}{'vs B&H':>10}{'switch':>8}{'expo%':>8}")
        for rl, sp in ((200,0),(200,20),(300,20),(400,50),(100,20)):
            for cb in (5, 30, 60):
                r = run(sl, rl, sp, cb)
                tag = f"SMA{rl}" + (f"+slope{sp}" if sp else "")
                print(f"{tag:<26}{cb:>6}{r['ret']:>9.1f}{r['vs']:>+10.1f}{r['switches']:>8}{r['exposure']:>8.0f}")
        print()

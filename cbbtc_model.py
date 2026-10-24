#!/usr/bin/env python3
"""
CBBTC 1h trading model development.
CBBTC = Coinbase Wrapped BTC, trades ~1:1 to BTC but only ~90d of hourly history exists.
So: build/validate on 3y BTC-USD 1h (long proxy), then confirm on real CBBTC 90d 1h.

Models tested are the pine-derived rules that already survived the earlier research:
  M1  Reclaim 100 (E2)          entry: close reclaims SMA100 while SMA14>SMA100, exit: exhaustion BB(100,2)
  M2  14/100 golden cross       entry: SMA14 crosses SMA100, exit: BB(100,2) exhaustion
  M3  Golden cross 50/200       entry: SMA50 crosses SMA200, exit: death cross
  M4  HMA420 + BSM              entry: BSM compra + HMA1>HMA2, exit: BSM venta / HMA cross
  M5  Aegis Trend v1            regime gate + 50-bar breakout + ATR chandelier trail
Costs: 2bp/side venue+gas (0.0002 per side), applied both sides per trade.
"""
import numpy as np, pandas as pd, math, sys

COST = 0.0002  # per side

def sma(s, n): return s.rolling(n).mean()
def wma(s, n):
    n = int(n)
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

def hma(s, n):
    return wma(2 * wma(s, n / 2) - wma(s, n), math.sqrt(n))

def backtest(d, entries, exits):
    c = d.close.to_numpy()
    e = entries.to_numpy().astype(bool)
    x = exits.to_numpy().astype(bool)
    n = len(c)
    pos = 0; ei = 0; epx = 0.0; trades = []
    for i in range(1, n):
        if pos == 0:
            if e[i]:
                pos, ei, epx = 1, i, c[i]
        else:
            if x[i]:
                trades.append((ei, i, epx, c[i])); pos = 0
    if pos == 1:
        trades.append((ei, n - 1, epx, c[-1]))
    if not trades:
        return dict(ret=0.0, n=0, win=0.0, bars=0.0, worst=0.0, t=float('nan'),
                   exp=0.0, avg_ret=0.0, dd=0.0)
    eq = 1.0
    for _, j, a, b in trades:
        eq *= (b / a) * (1 - COST) ** 2
    r = np.array([b / a - 1 for _, j, a, b in trades])
    held = np.array([j - i for i, j, a, b in trades], dtype=float)
    ts = r.mean() / (r.std(ddof=1) / math.sqrt(len(r))) if len(r) > 2 and r.std(ddof=1) > 0 else float('nan')
    eqs = [1.0]
    for _, j, a, b in trades:
        eqs.append(eqs[-1] * (b / a) * (1 - COST) ** 2)
    eqs = np.array(eqs); peak = np.maximum.accumulate(eqs)
    dd = float(((eqs - peak) / peak).min() * 100)
    return dict(ret=100 * (eq - 1), n=len(trades), win=float((r > 0).mean()),
                bars=float(held.mean()), worst=float(r.min() * 100), t=ts,
                exp=100 * held.sum() / n, avg_ret=float(r.mean() * 100), dd=dd)

def build_models(d):
    c = d.close
    h = d.high if 'high' in d.columns else c
    lo = d.low if 'low' in d.columns else c
    f14, s100 = sma(c, 14), sma(c, 100)
    f50, s200 = sma(c, 50), sma(c, 200)
    basis = sma(c, 100); sd = c.rolling(100).std()
    upper = basis + 2.0 * sd
    M = {}

    reclaim = (c > s100) & (c.shift() <= s100.shift()) & (f14 > s100)
    exhaust = (c > upper) & (c > f14)
    M["M1 reclaim100/BBexit"] = (reclaim, exhaust)

    gc = (f14 > s100) & (f14.shift() <= s100.shift())
    M["M2 14/100 cross/BBexit"] = (gc, exhaust)

    gc50200 = (f50 > s200) & (f50.shift() <= s200.shift())
    dc50200 = (f50 < s200) & (f50.shift() >= s200.shift())
    M["M3 50/200 cross/deathcross"] = (gc50200, dc50200)

    hma1, hma2 = hma(c, 14), hma(c, 100)
    bbmacd = c.ewm(span=8, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    bavg = bbmacd.ewm(span=9, adjust=False).mean()
    bsd = bbmacd.rolling(9).std()
    upperB = bavg + 0.8 * bsd; lowerB = bavg - 0.8 * bsd
    compra = (bbmacd > upperB) & (bbmacd.shift() <= upperB.shift())
    venta = (bbmacd < lowerB) & (bbmacd.shift() >= lowerB.shift())
    hmaBear = (hma1 < hma2) & (hma1.shift() >= hma2.shift())
    m4e = compra & (hma1 > hma2)
    m4x = venta | hmaBear
    M["M4 HMA420+BSM"] = (m4e, m4x)

    regime = sma(c, 400); rising = regime > regime.shift(20)
    bull = (c > regime) & rising
    hh = h.rolling(50).max().shift()
    m5e = bull & (c > hh)
    atr = (h - lo).rolling(14).mean()
    en = m5e.to_numpy().astype(bool)
    cn = c.to_numpy(); atrn = atr.to_numpy(); bwn = bull.to_numpy()
    ex = np.zeros(len(d), dtype=bool)
    pos = False; peak = 0.0; stop = 0.0
    for i in range(1, len(d)):
        if not pos:
            if en[i]:
                pos = True; peak = h.iloc[i]; stop = peak - 10 * atrn[i]
        else:
            peak = max(peak, h.iloc[i])
            stop = max(stop, peak - 10 * atrn[i])
            if lo.iloc[i] <= stop or not bwn[i]:
                ex[i] = True; pos = False
    M["M5 AegisTrend v1"] = (m5e, pd.Series(ex, index=d.index))

    return M

def run(path, tag):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if "close" not in d:
        print(f"\n{tag}: no close column; cols={list(d.columns)}")
        return d
    bh = 100 * (d.close.iloc[-1] / d.close.iloc[0] - 1)
    print(f"\n===== {tag} ===== bars={len(d)} buy&hold {bh:+.1f}%")
    M = build_models(d)
    print(f"{'model':<26}{'ret%':>9}{'n':>5}{'win%':>7}{'bars':>7}{'worst%':>8}{'t':>6}{'exp%':>7}{'dd%':>7}")
    for name, (e, x) in M.items():
        r = backtest(d, e, x)
        print(f"{name:<26}{r['ret']:>9.1f}{r['n']:>5}{r['win']*100:>7.1f}{r['bars']:>7.0f}"
              f"{r['worst']:>8.1f}{r['t']:>6.2f}{r['exp']:>7.0f}{r['dd']:>7.1f}")
    return d

if __name__ == "__main__":
    run("bars_btc_1h_3y.csv", "BTC-USD 1h 3y (CBBTC long proxy)")
    run("bars_cbbtc_1h_90d.csv", "CBBTC-USD 1h 90d (actual, close-only)")

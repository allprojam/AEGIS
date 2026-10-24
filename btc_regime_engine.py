#!/usr/bin/env python3
"""
BTC regime engine — goal is NOT USD alpha, it is MAX BTC.
Start with 1 BTC. Each bar the engine is in one of three regimes:
  BUY   = accumulate (all cash -> BTC)
  HOLD  = stay (hold BTC if in, hold cash if out)
  SELL  = de-risk (all BTC -> cash/USD)
Only 3 states, all-in/all-out, no shorting. Costs 0.0002/side.

We measure the FINAL BTC COUNT, not USD return. A regime set only "wins"
if it ends with MORE BTC than simply holding (1.000).
"""
import numpy as np, pandas as pd, math

COST = 0.0002

def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def btc_backtest(d, regime):  # regime: int series, 1=BUY, 0=HOLD, -1=SELL
    c = d.close.to_numpy()
    r = np.asarray(regime, dtype=int)
    n = len(c)
    btc = 1.0; cash = 0.0; in_pos = True
    events = []
    for i in range(n):
        s = r[i]
        if s == 1 and not in_pos:      # buy: cash -> btc
            btc = cash / c[i] * (1 - COST); cash = 0.0; in_pos = True
            events.append((i, 'buy', c[i]))
        elif s == -1 and in_pos:       # sell: btc -> cash
            cash = btc * c[i] * (1 - COST); btc = 0.0; in_pos = False
            events.append((i, 'sell', c[i]))
    # if still long at end, value in btc terms = btc (held)
    end_btc = btc if in_pos else cash / c[-1]
    end_usd = (btc if in_pos else cash) * c[-1]
    hold_usd = 1.0 * c[-1]
    return dict(end_btc=end_btc, end_usd=end_usd, hold_usd=hold_usd, events=events,
                trades=len([e for e in events if e[1] == 'buy']))

def regimes_ma(d, fast, slow, gate=None, gate_rising=True):
    """BUY when fast>SMA and close>gate; SELL when fast<SMA; HOLD when gate off but trend on? 
    Actually: BUY=fast>slow, SELL=fast<slow, HOLD=gate blocks (flat)."""
    c = d.close
    f = sma(c, fast); s = sma(c, slow)
    trend = (f > s).astype(int) - (f < s).astype(int)  # +1 buy, -1 sell
    if gate is not None:
        g = sma(c, gate)
        ok = c > g
        if gate_rising:
            ok = ok & (g > g.shift(gate // 20))
        # HOLD (0) when gate off; else follow trend
        reg = trend.where(ok, 0)
    else:
        reg = trend
    return reg.fillna(0).astype(int)

def regimes_donchian(d, look, gate=None):
    """BUY when close breaks above N-bar high; SELL when breaks below N-bar low."""
    c = d.close
    hh = d.high.rolling(look).max().shift() if 'high' in d.columns else c.rolling(look).max().shift()
    ll = d.low.rolling(look).min().shift() if 'low' in d.columns else c.rolling(look).min().shift()
    reg = pd.Series(0, index=d.index)
    pos = 0
    cn = c.to_numpy(); hhn = hh.to_numpy(); lln = ll.to_numpy()
    for i in range(look, len(d)):
        if np.isnan(hhn[i]) or np.isnan(lln[i]): continue
        if pos <= 0 and cn[i] > hhn[i]: pos = 1
        elif pos >= 0 and cn[i] < lln[i]: pos = -1
        reg.iloc[i] = pos
    if gate is not None:
        g = sma(c, gate)
        ok = c > g
        reg = reg.where(ok, 0)
    return reg.astype(int)

def regimes_regime_slope(d, rlen, slen):
    """BUY = close>regimeSMA and rising; SELL = close<regimeSMA; HOLD = close>regime but falling."""
    c = d.close
    g = sma(c, rlen)
    rising = g > g.shift(slen)
    reg = pd.Series(0, index=d.index)
    reg[(c > g) & rising] = 1      # BUY
    reg[c < g] = -1                # SELL
    # (c>g) and not rising -> 0 HOLD
    return reg.astype(int)

def run(d, path, tag):
    c = d.close
    bh_btc = 1.0
    bh_usd = c.iloc[-1] / c.iloc[0]
    print(f"\n===== {tag} ===== bars={len(d)}  hold = 1.000 BTC (${c.iloc[0]:.0f} -> ${c.iloc[-1]:.0f}, {100*bh_usd:+.0f}%)")
    print(f"{'engine':<38}{'end BTC':>9}{'vs hold':>9}{'trades':>7}{'USD end':>10}{'hold USD':>10}")

    engines = [
        ("MA14/100", regimes_ma(d, 14, 100)),
        ("MA50/200", regimes_ma(d, 50, 200)),
        ("MA14/100 + gate400", regimes_ma(d, 14, 100, gate=400)),
        ("MA14/100 + gate400 rising", regimes_ma(d, 14, 100, gate=400, gate_rising=True)),
        ("MA50/200 + gate400 rising", regimes_ma(d, 50, 200, gate=400, gate_rising=True)),
        ("Donchian 50", regimes_donchian(d, 50)),
        ("Donchian 100", regimes_donchian(d, 100)),
        ("Donchian 50 + gate400", regimes_donchian(d, 50, gate=400)),
        ("Regime slope 400/20", regimes_regime_slope(d, 400, 20)),
        ("Regime slope 200/20", regimes_regime_slope(d, 200, 20)),
    ]
    for name, reg in engines:
        r = btc_backtest(d, reg)
        delta = r['end_btc'] - 1.0
        print(f"{name:<38}{r['end_btc']:>9.4f}{delta:>+9.4f}{r['trades']:>7}"
              f"{r['end_usd']:>10.0f}{r['hold_usd']:>10.0f}")

if __name__ == "__main__":
    d = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    run(d, None, "BTC-USD 1h 3y (goal = max BTC)")

#!/usr/bin/env python3
"""The synthesis: regime-gated trend continuation with an ATR trailing stop.

Design criteria taken directly from what the research established:
  1. REGIME GATE  - only long when a slow trend filter is up. This is the fix for the
     single biggest flaw found: long-only systems bleed in bear markets. Flat is the
     short, because a plain AMM swap cannot short.
  2. LONG HOLDS   - ATR trailing stop, never a fixed small target. At ~5bps round trip
     only trades lasting tens of hours clear the friction.
  3. NO CHURN     - entry requires a fresh breakout in the trend direction, not a
     crossover that fires constantly.
  4. PULLBACK ENTRY - buy strength after a pause, not a dip into weakness (the failure
     mode of every mean-reversion candidate tested).
"""
import numpy as np, pandas as pd
from pine_port import pine_ema, pine_stdev
from lib_strategies import pine_atr, pine_rma, simulate_events


def custom(df, regime_len=200, slope_len=20, entry_len=50, atr_len=14,
           atr_mult=4.0, exit_on_regime=False, use_slope=True):
    d = df.copy()
    c = d["close"]
    # --- 1. regime gate ---
    reg = c.rolling(regime_len).mean()
    rising = reg > reg.shift(slope_len)
    bull = (c > reg) & (rising if use_slope else True)
    d["regime"] = bull
    # --- 4. entry: breakout of the entry_len high, only inside the regime ---
    hh = d["high"].rolling(entry_len).max().shift()
    d["entry"] = bull & (c > hh)
    # --- 2/3. exit: ATR chandelier trail, or regime loss if enabled ---
    a = pine_atr(d, atr_len)
    d["atr"] = a
    d["atr_mult"] = atr_mult
    if exit_on_regime:
        d["exit"] = (~bull) & bull.shift().fillna(False)
    else:
        d["exit"] = pd.Series(False, index=d.index)
    return d


def simulate_trail(d, size_usd=250.0, fee_bps_rt=5.0, gas_usd=0.02, entry_col="entry"):
    """Trend-continuation engine with a live ATR chandelier trailing stop.
    Fill at next bar open on entry. Trail ratchets from the highest high since entry."""
    o, hi, lo, cl = (d[x].to_numpy() for x in ("open", "high", "low", "close"))
    a = d["atr"].to_numpy(); mult = float(d["atr_mult"].iloc[0])
    en = d[entry_col].fillna(False).to_numpy()
    rex = d["exit"].fillna(False).to_numpy()
    pos = 0.0; epx = None; peak = None; stop = None
    cum = 0.0; trades = []; curve = []
    for i in range(len(d) - 1):
        if pos == 0.0:
            if en[i] and not np.isnan(a[i]):
                epx = o[i + 1]; pos = size_usd / epx
                peak = max(hi[i + 1], epx); stop = peak - mult * a[i]
                cum -= size_usd * fee_bps_rt / 10000.0 + gas_usd
        else:
            # LAG: the trail is set from the PREVIOUS bar's high and ATR, then tested
            # against this bar's low. Using hi[i]/a[i] here was same-bar lookahead.
            peak = max(peak, hi[i-1])
            stop = max(stop, peak - mult * a[i-1])
            hit = lo[i] <= stop
            flip = rex[i]
            if hit or flip:
                px = min(o[i + 1], stop) if hit else o[i + 1]
                pnl = pos * (px - epx) - size_usd * fee_bps_rt / 10000.0 - gas_usd
                cum += pnl
                trades.append({"t": int(d["time"].iloc[i]), "in": epx, "out": px,
                               "usd": pnl, "bars": i - _idx(en, i)})
                pos = 0.0; epx = peak = stop = None
        curve.append(cum)
    eq = np.array(curve); peakc = np.maximum.accumulate(eq)
    wins = [t for t in trades if t["usd"] > 0]
    return {"trades": len(trades), "net_usd": round(cum, 3),
            "win_rate": round(len(wins)/len(trades), 3) if trades else None,
            "avg_bars": round(float(np.mean([t["bars"] for t in trades])), 1) if trades else None,
            "max_dd_usd": round(float((eq - peakc).min()), 3), "_trades": trades}


def _idx(en, i):
    """bars held: walk back to the entry bar (approximate but consistent)."""
    j = i
    while j > 0 and not en[j - 1]:
        j -= 1
    return j


def bh(df): return 100*(df.close.iloc[-1]/df.close.iloc[0]-1)

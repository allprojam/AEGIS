"""Faithful ports of the top-ranked public strategies from the harvester shortlist.
Pine v2/v3 -> pandas. Each returns (df, entry_col, exit_col, max_bars)."""
import numpy as np, pandas as pd
from pine_port import pine_ema


def _sma(x, n): return x.rolling(n).mean()


def _zlema(x, n):
    """f_LB_zlema: e1=ema(x,n); e2=ema(e1,n); zlema = e1 + (e1-e2)."""
    e1 = pine_ema(x, n)
    e2 = pine_ema(e1, n)
    return e1 + (e1 - e2)


def _consec(up: np.ndarray) -> np.ndarray:
    """Consecutive-bar counter, Pine's nz(x[1])+1 / 0 pattern."""
    out = np.zeros(len(up), dtype=int)
    for i in range(1, len(up)):
        out[i] = out[i - 1] + 1 if up[i] else 0
    return out


# ---- PUB;2811  Golden Cross, SMA 50/200, long only (ChartArt, 11.4k likes) ----
def golden_cross(df, fast=50, slow=200):
    d = df.copy()
    f, s = _sma(d["close"], fast), _sma(d["close"], slow)
    d["gc_entry"] = (f > s) & (f.shift() <= s.shift())
    d["gc_exit"] = (f < s) & (f.shift() >= s.shift())
    return d, "gc_entry", "gc_exit", None


# ---- PUB;1844  MicuRobert EMA cross V2 (ZLEMA 5/34, long+short) ----
# NOTE: the original TP/SL are in forex pips and are not transferable to BTC;
# the core ZLEMA cross is ported, the pip-based stops are dropped.
def micurobert(df, fast=5, slow=34):
    d = df.copy()
    a, b = _zlema(d["open"], fast), _zlema(d["open"], slow)
    d["mb_entry"] = (a > b) & (a.shift() <= b.shift())
    d["mb_exit"] = (a < b) & (a.shift() >= b.shift())
    return d, "mb_entry", "mb_exit", None


# ---- PUB;2119  MA Consecutive Up/Down (ChartArt) -- momentum persistence ----
def consecutive_updown(df, n=4):
    d = df.copy()
    up = (d["close"] > d["close"].shift()).to_numpy()
    dn = (d["close"] < d["close"].shift()).to_numpy()
    cu, cd = _consec(up), _consec(dn)
    d["cu_entry"] = cu == n          # exactly n consecutive up bars -> long
    d["cu_exit"] = cd == n           # n consecutive down -> flat
    return d, "cu_entry", "cu_exit", None


# ---- PUB;2627  Moving Average Crossover (ema14 vs sma56, gated by ema28) ----
# NOTE: the original has a hardcoded 2014-2015 backtest window; dropped so it trades.
def ma_cross_2627(df, a_len=14, b_len=28, c_len=56):
    d = df.copy()
    e14, e28, s56 = pine_ema(d["close"], a_len), pine_ema(d["close"], b_len), _sma(d["close"], c_len)
    cross = ((e14 > s56) & (e14.shift() <= s56.shift())) | ((e14 < s56) & (e14.shift() >= s56.shift()))
    d["c_entry"] = cross & (e14 > e28)
    d["c_exit"] = cross & (e14 < e28)
    return d, "c_entry", "c_exit", None


# ---- PUB;2505  Mbit Simple MA: deep mean reversion, SMA 520 + 27-bar count ----
def mbit_ma(df, length=520, confirm=27):
    d = df.copy()
    ma = _sma(d["close"], length)
    below = (d["close"] < ma).to_numpy()
    above = (d["close"] > ma).to_numpy()
    sc, bc = _consec(below), _consec(above)
    d["m_entry"] = sc == confirm      # confirm bars below the long MA -> long
    d["m_exit"] = bc == confirm       # confirm bars above -> exit
    return d, "m_entry", "m_exit", None


PUBLIC = {
    "golden_cross_50_200":        golden_cross,
    "micurobert_zlema_5_34":      micurobert,
    "consecutive_updown_4":       consecutive_updown,
    "ma_cross_14_28_56":          ma_cross_2627,
    "mbit_sma520_27":             mbit_ma,
}

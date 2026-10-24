"""Faithful pandas port of the two Pine indicators. Pine semantics, not numpy defaults."""
import numpy as np, pandas as pd


def pine_wma(x: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return x.rolling(n).apply(lambda a: float(np.dot(a, w) / w.sum()), raw=True)


def pine_ema(x: pd.Series, n: int) -> pd.Series:
    """Pine ta.ema: seed with SMA of the first n VALID values, then recurse.

    Leading NaNs must be skipped, not averaged: seeding on an all-NaN window
    poisons every later value (that bug made the BSM bands come back as NaN).
    """
    a = 2.0 / (n + 1.0)
    out = pd.Series(np.nan, index=x.index, dtype=float)
    first = x.first_valid_index()
    if first is None:
        return out
    v = x.loc[first:].to_numpy(dtype=float)
    off = x.index.get_loc(first)
    if len(v) < n:
        return out
    out.iloc[off + n - 1] = float(np.mean(v[:n]))
    for i in range(n, len(v)):
        out.iloc[off + i] = a * v[i] + (1 - a) * out.iloc[off + i - 1]
    return out


def pine_stdev(x: pd.Series, n: int) -> pd.Series:
    """Pine ta.stdev = POPULATION stdev (ddof=0)."""
    return x.rolling(n).std(ddof=0)


def pine_hma(x: pd.Series, n: int) -> pd.Series:
    """wma(2*wma(x, n/2) - wma(x, n), round(sqrt(n))) ; n/2 truncates like Pine."""
    h = n // 2
    return pine_wma(2 * pine_wma(x, h) - pine_wma(x, n), int(round(np.sqrt(n))))


def compute(df: pd.DataFrame, len1=14, len2=100, len3=200, rapida=8, lenta=26,
            stdv=0.8, avg_len=9) -> pd.DataFrame:
    d = df.copy()
    d["hma1"] = pine_hma(d["open"], len1)
    d["hma2"] = pine_hma(d["open"], len2)
    d["hma3"] = pine_hma(d["open"], len3)
    d["bbmacd"] = pine_ema(d["close"], rapida) - pine_ema(d["close"], lenta)
    d["bsm_avg"] = pine_ema(d["bbmacd"], avg_len)
    d["bsm_sdev"] = pine_stdev(d["bbmacd"], avg_len)
    d["banda_supe"] = d["bsm_avg"] + stdv * d["bsm_sdev"]
    d["banda_inf"] = d["bsm_avg"] - stdv * d["bsm_sdev"]
    d["compra"] = (d["bbmacd"] > d["banda_supe"]) & (d["bbmacd"].shift() <= d["banda_supe"].shift())
    d["venta"] = (d["bbmacd"] < d["banda_inf"]) & (d["bbmacd"].shift() >= d["banda_inf"].shift())
    d["hma_bull"] = (d["hma1"] > d["hma2"]) & (d["hma1"].shift() <= d["hma2"].shift())
    d["hma_bear"] = (d["hma1"] < d["hma2"]) & (d["hma1"].shift() >= d["hma2"].shift())
    return d

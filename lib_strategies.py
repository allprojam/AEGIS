"""Faithful pandas ports of three public TradingView strategies.
Pine v2 semantics. Same honest fill model: signal on closed bar, fill next open."""
import numpy as np, pandas as pd
from pine_port import pine_ema


def pine_sma(x, n): return x.rolling(n).mean()
def pine_stdev(x, n): return x.rolling(n).std(ddof=0)


def pine_rma(x: pd.Series, n: int) -> pd.Series:
    """Pine ta.rma (Wilder): alpha = 1/n, seeded with SMA."""
    v = x.to_numpy(dtype=float); out = np.full(len(v), np.nan)
    if len(v) < n: return pd.Series(out, index=x.index)
    out[n-1] = np.nanmean(v[:n])
    for i in range(n, len(v)):
        out[i] = (out[i-1] * (n - 1) + v[i]) / n
    return pd.Series(out, index=x.index)


def pine_atr(df, n):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return pine_rma(tr, n)


def pine_rsi(x: pd.Series, n: int) -> pd.Series:
    d = x.diff()
    up = d.clip(lower=0); dn = (-d).clip(lower=0)
    ru, rd = pine_rma(up, n), pine_rma(dn, n)
    return 100 - 100 / (1 + ru / rd)


# ---------------- 1. Keltner bounce (Zelibobla) ----------------
def keltner_signals(df, klen=200, atrlen=200, dev=8.0, exit_on_ema=True):
    d = df.copy()
    ema = pine_sma(d["close"], klen)
    a = pine_atr(d, atrlen)
    top, bot = ema + a * dev, ema - a * dev
    c = d["close"]
    d["k_entry"] = (c > bot) & (c.shift() <= bot.shift())
    d["k_exit_tp"] = (c > ema) & (c.shift() <= ema.shift())      # "close on EMA touch"
    d["k_exit_band"] = (c < top) & (c.shift() >= top.shift())
    return d


# ---------------- 2. Bollinger + RSI v1.1 (ChartArt) ----------------
def bbrsi_signals(df, rsi_len=6, bb_len=200, bb_mult=2.0):
    d = df.copy()
    c = d["close"]
    basis = pine_sma(c, bb_len); sd = pine_stdev(c, bb_len)
    up, lo = basis + bb_mult * sd, basis - bb_mult * sd
    d["b_entry"] = (c > lo) & (c.shift() <= lo.shift())
    d["b_exit"] = (c < up) & (c.shift() >= up.shift())
    d["rsi"] = pine_rsi(c, rsi_len)
    return d


# ---------------- 3. Fractal Breakout (ChartArt) ----------------
def fractal_signals(df, n_time=3, avg3=True):
    d = df.copy()
    h, l = d["high"], d["low"]; price = (h + l) / 2
    ft = (h.shift(2) > h.shift(3)) & (h.shift(2) > h.shift(4)) & (h.shift(2) > h.shift(1)) & (h.shift(2) > h)
    # valuewhen(ft, price, 1): the most recent fractal price, evaluated 1 bar ago
    fp = pd.Series(np.nan, index=d.index)
    fp[ft.fillna(False)] = price[ft.fillna(False)]
    fp_prev = fp.ffill().shift(1)          # valuewhen(...,1) -> previous occurrence
    fa = (fp_prev.shift(1) + fp_prev.shift(2) + fp_prev.shift(3)) / 3 if avg3 else (fp_prev.shift(1) + fp_prev.shift(2)) / 2
    d["f_entry"] = price.shift(1) > fp_prev    # no_repainting default true
    d["f_trend"] = fa > fa.shift(1)
    d["f_ntime"] = n_time
    return d


def simulate_events(d, entry_col, exit_col, max_bars=None, size_usd=250.0,
                    fee_bps_rt=5.0, gas_usd=0.02, bars_per_year=24*365):
    """Honest engine: signal on closed bar, fill at NEXT bar open, one position at a time.

    Every result now carries a BUY-AND-HOLD baseline over the identical window, so a
    strategy is graded against what simply holding the same capital would have returned.

    Design choices, all made to favour the STRATEGY (so a negative verdict is robust):
      - HODL buys at bar 0 open and pays the same round-trip fee + gas as a trade.
        Charging the baseline friction makes HODL look worse, not better.
      - HODL is measured to the final close, the full window including warmup, because
        an investor could genuinely have held from bar 0 while the strategy waited for
        its lookback to fill.
      - An open position at the last bar is marked to the final close rather than
        silently dropped, which the earlier engine did.
    """
    o = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    en = d[entry_col].fillna(False).to_numpy()
    ex = d[exit_col].fillna(False).to_numpy()
    n = len(d)

    cum = 0.0; pos = 0.0; epx = None; ebar = None
    trades = []; equity = []
    ruined = False; ruin_bar = None
    cur_notional = size_usd
    fees_paid = 0.0; bars_in_market = 0

    for i in range(n - 1):
        if pos == 0.0:
            if en[i]:
                # bet from AVAILABLE equity, not a fixed notional. Betting the full
                # $250 after the account has fallen to $100 is over-betting and
                # produced an impossible -108% ROI before this guard.
                avail = size_usd + cum
                notional = min(size_usd, avail)
                epx = o[i + 1]
                pos = notional / epx
                ebar = i + 1
                f = notional * fee_bps_rt / 10000.0 + gas_usd
                cum -= f; fees_paid += f
                cur_notional = notional
        else:
            bars_in_market += 1
            hold = i - ebar
            timeup = (max_bars is not None) and (hold >= max_bars)
            if ex[i] or timeup:
                px = o[i + 1]
                f = cur_notional * fee_bps_rt / 10000.0 + gas_usd
                pnl = pos * (px - epx) - f
                cum += pnl; fees_paid += f
                trades.append({"t": int(d["time"].iloc[i]), "in": epx, "out": px,
                               "usd": pnl, "bars": hold})
                pos = 0.0; epx = None; ebar = None
                # RUIN: the account cannot lose more than it holds. Without this the
                # model re-bets the full notional forever and reports -645% ROI on a
                # $250 account, which is unachievable. Stop trading when wiped.
                if size_usd + cum <= 0:
                    ruined = True
                    ruin_bar = i
                    equity.append(0.0)
                    break
        equity.append(size_usd + cum)

    # mark any still-open position to the final close instead of dropping it
    if pos != 0.0:
        px = cl[-1]
        f = cur_notional * fee_bps_rt / 10000.0 + gas_usd
        pnl = pos * (px - epx) - f
        cum += pnl; fees_paid += f
        trades.append({"t": int(d["time"].iloc[-1]), "in": epx, "out": px,
                       "usd": pnl, "bars": (n - 1) - ebar, "open_at_end": True})
        pos = 0.0
        if size_usd + cum <= 0:
            ruined = True; ruin_bar = n - 1

    # ---- buy & hold over the identical window ----
    hodl_entry = o[0]
    hodl_exit = cl[-1]
    hodl_fee = size_usd * fee_bps_rt / 10000.0 + gas_usd   # one round trip, charged to HODL too
    hodl_pnl = (size_usd / hodl_entry) * (hodl_exit - hodl_entry) - hodl_fee

    if cum < -size_usd:          # floor at total loss; you cannot lose more than you have
        cum = -size_usd
    strat_roi = cum / size_usd * 100.0
    hodl_roi = hodl_pnl / size_usd * 100.0
    alpha = strat_roi - hodl_roi

    eq = np.array(equity) if equity else np.array([size_usd])
    peak = np.maximum.accumulate(eq)
    dd_pct = float(((eq - peak) / peak).min() * 100.0) if len(eq) else 0.0
    rets = np.diff(eq) / eq[:-1]
    if len(rets) > 1 and rets.std(ddof=1) > 0:
        sharpe = float(rets.mean() / rets.std(ddof=1) * np.sqrt(bars_per_year))
    else:
        sharpe = None

    hodl_eq = size_usd + (size_usd / hodl_entry) * (cl - hodl_entry)
    hpeak = np.maximum.accumulate(hodl_eq)
    hodl_dd = float(((hodl_eq - hpeak) / hpeak).min() * 100.0)
    hrets = np.diff(hodl_eq) / hodl_eq[:-1]
    hodl_sharpe = (float(hrets.mean() / hrets.std(ddof=1) * np.sqrt(bars_per_year))
                   if len(hrets) > 1 and hrets.std(ddof=1) > 0 else None)

    wins = [t for t in trades if t["usd"] > 0]
    losses = [t for t in trades if t["usd"] <= 0]
    return {
        "bars": int(n),
        "trades": len(trades),
        "net_usd": round(cum, 3),
        "strategy_roi_pct": round(strat_roi, 3),
        "hodl_roi_pct": round(hodl_roi, 3),
        "alpha_pct": round(alpha, 3),
        "beats_hodl": bool(alpha > 0),
        # A third verdict is needed. A strategy that never trades prints alpha=+100%
        # in a falling market simply by not participating. That is absence, not skill.
        # Validated by test: an all-False signal set "beat" HODL by 50 points on a
        # price that halved. Reported as SAT_OUT so it can never be read as alpha.
        "verdict": ("SAT_OUT" if (len(trades) == 0 or bars_in_market == 0)
                    else "BEATS_HODL" if alpha > 0 else "LOSES_TO_HODL"),
        "win_rate": round(len(wins) / len(trades), 3) if trades else None,
        "avg_win_bps": round(float(np.mean([(t["out"]/t["in"]-1)*10000 for t in wins])), 1) if wins else 0.0,
        "avg_loss_bps": round(float(np.mean([(t["out"]/t["in"]-1)*10000 for t in losses])), 1) if losses else 0.0,
        "avg_bars": round(float(np.mean([t["bars"] for t in trades])), 1) if trades else None,
        "max_dd_pct": round(dd_pct, 2),
        "hodl_max_dd_pct": round(hodl_dd, 2),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "hodl_sharpe": round(hodl_sharpe, 3) if hodl_sharpe is not None else None,
        "fees_paid_usd": round(fees_paid, 2),
        "ruined": bool(ruined),
        "ruin_bar": ruin_bar,
        "note": ("account wiped; trading stopped. ROI is floored at -100%." if ruined else None),
        "exposure_pct": round(bars_in_market / max(n - 1, 1) * 100.0, 1),
        "_trades": trades,
    }

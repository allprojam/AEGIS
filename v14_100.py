#!/usr/bin/env python3
"""14/100 cross entries, with a Bollinger-band exhaustion exit around the 100.

User's proposal:
  entry  : fast MA (14) crosses UP over slow MA (100)
  exit   : candle closes ABOVE the fast MA and is extended far from the slow MA
           -> use a Bollinger band around the 100 as the "far away" threshold
  short  : mirror image

Signals use bar i's close and execute at bar i's close -> no lookahead.
Costs 5 bps round trip.
"""
import numpy as np, pandas as pd, math

COST = 0.0005

def sma(s, n): return s.rolling(n).mean()

def run(d, fast=14, slow=100, bb_k=2.0, exit_mode="cross", shorts=False,
        short_on_extension=False, rearm=True):
    c = d["close"].to_numpy(); n = len(c)
    ret = np.zeros(n); ret[1:] = c[1:]/c[:-1] - 1
    cl = d["close"]
    f, s = sma(cl, fast).to_numpy(), sma(cl, slow).to_numpy()
    basis = sma(cl, slow); sd = cl.rolling(slow).std()
    up = (basis + bb_k*sd).to_numpy(); lo = (basis - bb_k*sd).to_numpy()

    pos = 0; eq = 1.0; trades = []; ent_i = None; ent_px = None; switches = 0
    armed_l = armed_s = True
    for i in range(1, n):
        if pos != 0:
            eq *= (1 + ret[i])                      # held through bar i
        # ---- decision on bar i's close ----
        cu = (f[i] > s[i]) and (f[i-1] <= s[i-1])    # cross up
        cd = (f[i] < s[i]) and (f[i-1] >= s[i-1])    # cross down
        ext_up = (not np.isnan(up[i])) and (c[i] > up[i]) and (c[i] > f[i])
        ext_dn = (not np.isnan(lo[i])) and (c[i] < lo[i]) and (c[i] < f[i])
        if pos == 0:
            if cu and armed_l:
                pos, ent_i, ent_px = 1, i, c[i]; switches += 1; eq *= (1-COST); armed_l = False
            elif shorts and cd and armed_s:
                pos, ent_i, ent_px = -1, i, c[i]; switches += 1; eq *= (1-COST); armed_s = False
        else:
            close = False
            if pos == 1:
                if exit_mode == "cross" and cd: close = True; armed_l = True
                elif exit_mode == "bb" and ext_up: close = True; armed_l = rearm
            else:
                if exit_mode == "cross" and cu: close = True; armed_s = True
                elif exit_mode == "bb" and ext_dn: close = True; armed_s = rearm
            if short_on_extension and exit_mode == "bb":
                pass  # handled below: immediate reversal
            if close:
                # BUG FIX: gain from ent_px to c[i] is ALREADY in eq -- eq *= (1+ret[i])
                # ran on every held bar. Re-applying pnl double-counted each trade and
                # inflated returns through compounding (produced a fake +346%).
                pnl = pos*(c[i]-ent_px)/ent_px
                eq *= (1 - COST); switches += 1
                trades.append({"r": pnl, "bars": i-ent_i, "side": pos})
                if short_on_extension and shorts:
                    pos, ent_i, ent_px = -pos, i, c[i]
                    eq *= (1-COST); switches += 1
                else:
                    pos = 0
    bh = 100*(c[-1]/c[0]-1)
    r = np.array([t["r"] for t in trades])
    t_stat = (r.mean()/(r.std(ddof=1)/math.sqrt(len(r)))) if len(r) > 1 and r.std(ddof=1) > 0 else float("nan")
    return {"ret": 100*(eq-1), "bh": bh, "trades": len(trades), "switches": switches,
            "win": float((r > 0).mean()) if len(r) else None,
            "bars": float(np.mean([t["bars"] for t in trades])) if trades else None,
            "t": t_stat}

def selftest(d):
    c = d["close"].to_numpy(); bh = 100*(c[-1]/c[0]-1)
    ret = np.zeros(len(c)); ret[1:] = c[1:]/c[:-1]-1
    eq = 1.0
    for i in range(len(c)):
        if i == 0: eq *= (1-COST)
        eq *= (1+ret[i])
    assert abs(100*(eq-1) - (bh-0.05)) < 0.3, "SELFTEST FAILED"
    return bh

if __name__ == "__main__":
    import sys
    for path, tag in (("bars_btc_1h_3y.csv","BTC 3y 1h"), ("bars_eth_1h_365d.csv","ETH 1y 1h")):
        d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        bh = selftest(d)
        print(f"\n===== {tag} =====  buy & hold {bh:+.1f}%")
        print(f"{'config':<46}{'ret%':>9}{'trades':>8}{'win':>7}{'bars':>7}{'t':>7}{'vs B&H':>9}")
        cfgs = [
            ("14/100 cross in, cross out, longs only", dict()),
            ("14/100 + BB(100,2.0) exhaustion exit", dict(exit_mode="bb")),
            ("14/100 + BB exit, shorts on cross-down", dict(exit_mode="bb", shorts=True)),
            ("14/100 + BB exit, SHORT ON EXTENSION (literal)", dict(exit_mode="bb", shorts=True, short_on_extension=True)),
            ("14/100 + BB exit, no re-arm", dict(exit_mode="bb", rearm=False)),
            ("14/100 + BB(100,1.5) exit", dict(exit_mode="bb", bb_k=1.5)),
            ("14/100 + BB(100,3.0) exit", dict(exit_mode="bb", bb_k=3.0)),
            ("50/200 golden cross (current best)", None),
        ]
        for name, kw in cfgs:
            if kw is None:
                from lib_public import golden_cross
                from lib_strategies import simulate_events
                dd, ec, xc, mb = golden_cross(d)
                rr = simulate_events(dd, ec, xc, max_bars=mb)
                print(f"{name:<46}{100*rr['net_usd']/250.0:>9.1f}{rr['trades']:>8}"
                      f"{(rr['win_rate'] or 0):>7.2f}{(rr['avg_bars'] or 0):>7.1f}{'-':>7}"
                      f"{100*rr['net_usd']/250.0-bh:>+9.1f}")
                continue
            r = run(d, **kw)
            print(f"{name:<46}{r['ret']:>9.1f}{r['trades']:>8}{(r['win'] or 0):>7.2f}"
                  f"{(r['bars'] or 0):>7.1f}{r['t']:>7.2f}{r['ret']-bh:>+9.1f}")

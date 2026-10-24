#!/usr/bin/env python3
"""Sizing plan for the frozen strategy at any account size, with turnover control.

Frozen strategy (verified on 36.7y, see README):
    60% SPY / 40% TLT, vol target 15%, 60d window, exposure cap 1.0 (no leverage)

Added here: a REBALANCE BAND. At small accounts the fractional commission is ~1% per order,
so rebalancing on every drift would destroy the edge. We only trade when a leg drifts more
than BAND percentage points from target, with a minimum interval between rebalances.

usage: ibkr_plan.py [--nav 200] [--band 5] [--min-days 30]
"""
import argparse, json, math, statistics, time
import requests, urllib3
import ibkr_client as ib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
B = ib.BASE
CONIDS = {"SPY": 756733, "TLT": 15547841}
W = {"SPY": 0.60, "TLT": 0.40}
VOL_TARGET, VOL_WINDOW, CAP = 0.15, 60, 1.0
MIN_ORDER_USD = 0.0     # fractional has no minimum notional, only 0.0001 share precision
TICK = 0.0001


def history(conid, period="1y", bar="1d"):
    r = requests.get(f"{B}/iserver/marketdata/history",
                     params={"conid": conid, "period": period, "bar": bar}, timeout=30)
    try:
        return r.json().get("data") or []
    except Exception:
        return []


def rvol(closes):
    rets = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))][-VOL_WINDOW:]
    return statistics.pstdev(rets)*math.sqrt(252) if len(rets) > 5 else None


def snap(conid):
    for _ in range(3):
        r = requests.get(f"{B}/iserver/marketdata/snapshot",
                         params={"conids": conid, "fields": "31"}, timeout=20)
        try:
            b = r.json()
            if isinstance(b, list) and b and b[0].get("31") not in (None, "C"):
                return float(b[0]["31"])
        except Exception:
            pass
        time.sleep(2.5)
    return None


def round_tick(q):
    return round(math.floor(q/TICK)*TICK, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nav", type=float, default=None, help="override NAV (else read from IBKR)")
    ap.add_argument("--band", type=float, default=5.0, help="rebalance band in pct points")
    ap.add_argument("--min-days", type=int, default=30, help="min days between rebalances")
    a = ap.parse_args()

    # --- which login is active? ---
    code, accts = ib.accounts()
    acct = accts[0].get("accountId") if isinstance(accts, list) and accts else None
    code, summ = ib.summary(acct) if acct else (0, {})
    nav = a.nav if a.nav is not None else float((summ.get("netliquidation") or {}).get("amount") or 0)
    is_paper = str(acct).upper().startswith("DU")
    print(f"account {acct}   NAV ${nav:,.2f}")
    print(f"login type: {'PAPER (DU prefix)' if is_paper else 'LIVE (no DU prefix)'}")
    if not is_paper:
        print("  ^ NOTE: paper requires logging the gateway in with PAPER credentials.\n")
    else:
        print()

    # --- volatility & target ---
    spy_h, tlt_h = history(CONIDS["SPY"]), history(CONIDS["TLT"])
    if not spy_h or not tlt_h:
        print("no history; aborting"); return
    rv_s, rv_t = rvol([b["c"] for b in spy_h]), rvol([b["c"] for b in tlt_h])
    rv_b = math.sqrt((W["SPY"]*rv_s)**2 + (W["TLT"]*rv_t)**2)
    scale = min(CAP, VOL_TARGET/rv_b) if rv_b > 0 else 1.0
    px = {"SPY": snap(CONIDS["SPY"]), "TLT": snap(CONIDS["TLT"])}
    if not all(px.values()):
        px = {"SPY": spy_h[-1]["c"], "TLT": tlt_h[-1]["c"]}
        print("(using last daily close; snapshot unavailable)")

    print("--- frozen strategy ---")
    print(f"  realized vol   SPY {rv_s*100:6.2f}%   TLT {rv_t*100:6.2f}%   blend {rv_b*100:6.2f}%")
    print(f"  vol target {VOL_TARGET*100:.0f}%  ->  exposure scale {scale:.3f}")
    print(f"  target weights  SPY {W['SPY']*scale*100:.1f}%  TLT {W['TLT']*scale*100:.1f}%"
          f"  cash {(1-(W['SPY']+W['TLT'])*scale)*100:.1f}%")
    print()
    print(f"--- orders at NAV ${nav:,.2f} (prices SPY {px['SPY']:.2f} / TLT {px['TLT']:.2f}) ---")
    tot_comm = 0.0
    for s in ("SPY", "TLT"):
        notional = nav*W[s]*scale
        qty = round_tick(notional/px[s])
        actual = qty*px[s]
        print(f"  {s}: ${notional:>8.2f} -> qty {qty:.4f}  (actual ${actual:>8.2f})")
    print()
    print("--- turnover control (why the band matters) ---")
    print(f"  band {a.band:.1f} pp, min {a.min_days} days between rebalances")
    # Accurate commission: per order it is min(1% of notional, max($1.00, $0.005*shares)).
    # Below ~$100 notional the 1% cap binds; at/above ~$100 the $1.00 floor binds.
    def commission(notional):
        return min(0.01*notional, max(1.00, 0.005*max(1, round(notional/px["SPY"]))))
    print("  IBKR Pro: min(1% of trade, max($1.00, $0.005/share)). Below $100 the 1% cap binds.")
    for leg in ("SPY", "TLT"):
        n = nav*W[leg]*scale
        print(f"    {leg} leg ${n:>7.2f} -> commission ${commission(n):.2f} = {100*commission(n)/n:.2f}%")
    cycle_cost = sum(commission(nav*W[l]*scale) for l in ("SPY","TLT"))
    print(f"    full rebalance both legs = ${cycle_cost:.2f} = {100*cycle_cost/nav:.2f}% of account")
    print()
    for label, cycles in (("every drift (worst)", 12), ("band 5pp (~quarterly)", 4), ("annual only", 1)):
        drag = 100*cycles*cycle_cost/nav
        net = 6.7 - drag
        print(f"  {label:<24} {cycles:>3} cyc/yr -> drag {drag:>4.1f}%  net ~{net:>5.1f}%/yr  "
              f"{'OK' if net > 3 else 'MARGINAL' if net > 0 else 'FATAL'}")
    print()
    print("--- reaching the $1,500 goal ---")
    gross = 6.7
    drag_annual = 100*1*cycle_cost/nav
    net = gross - drag_annual
    if net > 0:
        yrs = math.log(1500/nav)/math.log(1+net/100)
        print(f"  at net {net:.1f}%/yr -> ${nav:.0f} to $1,500 takes {yrs:.1f} YEARS")
    else:
        print(f"  at net {net:.1f}%/yr the account never reaches $1,500")
    req = 100*((1500/nav)**(1/5) - 1)
    print(f"  to reach $1,500 in 5 years you need {req:.1f}%/yr COMPOUNDED -- "
          f"roughly {req/ (gross-100*1*cycle_cost/nav):.1f}x the strategy's net return")
    print()
    print(f"  DRY RUN. No orders placed. Paper login required to change account.")


if __name__ == "__main__":
    main()

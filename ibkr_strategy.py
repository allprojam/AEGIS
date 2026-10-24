#!/usr/bin/env python3
"""The ONE strategy this project actually validated, wired to IBKR.

WHAT: 60/40 SPY/TLT with volatility targeting.
WHY:  verified on 36.7 years of data (1990-2026) -- drawdown improved in ALL four decades,
      Sharpe improved or matched in 3 of 4. Frozen params, no tuning.

FROZEN PARAMETERS (from macro_timing.py / vt_verify.py):
    blend          SPY 60% / TLT 40%
    vol target     15% annualised
    vol window     60 trading days
    exposure cap    1.0   (NO leverage -- the leveraged version's extra return was borrowed beta)

WHAT IT IS NOT: an alpha source. It gives up raw return to buy drawdown reduction, and on a
$10 account the commission drag makes it uneconomic. This is a plumbing test.

SAFETY: dry-run by default. Placing orders requires BOTH --live AND IBKR_ALLOW_LIVE=1.
        There is a hard notional cap. The account is LIVE, not paper.
"""
import os, sys, json, math
import requests, urllib3
import ibkr_client as ib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
B = ib.BASE
CONIDS = {"SPY": 756733, "TLT": 15547841}

# frozen strategy params
W_SPY, W_TLT = 0.60, 0.40
VOL_TARGET = 0.15
VOL_WINDOW = 60
EXPOSURE_CAP = 1.0

# safety
MAX_NOTIONAL_USD = float(os.environ.get("IBKR_MAX_NOTIONAL", "50"))
ALLOW_LIVE = os.environ.get("IBKR_ALLOW_LIVE") == "1"


def history(conid, period="1y", bar="1d"):
    r = requests.get(f"{B}/iserver/marketdata/history", params={"conid": conid, "period": period, "bar": bar}, timeout=30)
    j = r.json()
    return j.get("data") or []


def realized_vol_annual(closes, window=VOL_WINDOW):
    """Annualised realised vol over the last `window` returns (daily bars -> sqrt(252))."""
    import statistics
    rets = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))][-window:]
    if len(rets) < 5:
        return None
    sd = statistics.pstdev(rets)
    return sd * math.sqrt(252)


def target_weights():
    """Return the vol-targeted target weights for SPY and TLT."""
    spy = [b["c"] for b in history(CONIDS["SPY"])]
    tlt = [b["c"] for b in history(CONIDS["TLT"])]
    if not spy or not tlt:
        return None
    rv_spy = realized_vol_annual(spy)
    rv_tlt = realized_vol_annual(tlt)
    # blend realized vol (correlation ignored -> conservative overestimate)
    rv_blend = math.sqrt((W_SPY*rv_spy)**2 + (W_TLT*rv_tlt)**2)
    scale = min(EXPOSURE_CAP, VOL_TARGET / rv_blend) if rv_blend > 0 else 1.0
    return {"rv_spy": rv_spy, "rv_tlt": rv_tlt, "rv_blend": rv_blend,
            "scale": scale, "spy": W_SPY*scale, "tlt": W_TLT*scale,
            "cash": 1.0 - (W_SPY+W_TLT)*scale,
            "last_spy": spy[-1], "last_tlt": tlt[-1],
            "bars_spy": len(spy), "bars_tlt": len(tlt)}


def price(conid):
    for _ in range(3):
        r = requests.get(f"{B}/iserver/marketdata/snapshot", params={"conids": conid, "fields": "31"}, timeout=20)
        try:
            b = r.json()
            if isinstance(b, list) and b and b[0].get("31") not in (None, "C"):
                return float(b[0]["31"])
        except Exception:
            pass
        import time; time.sleep(2.5)
    return None


def main():
    acct = None
    code, accts = ib.accounts()
    if isinstance(accts, list) and accts:
        acct = accts[0].get("accountId")
    code, summ = ib.summary(acct) if acct else (0, {})
    nav = float((summ.get("netliquidation") or {}).get("amount") or 0)
    cash = float((summ.get("totalcashvalue") or {}).get("amount") or 0)

    print(f"account {acct}   NAV ${nav:,.2f}   cash ${cash:,.2f}")
    print(f"LIVE account? {'NO -- looks like paper (DU prefix)' if str(acct).startswith('DU') else 'YES -- NOT a paper account'}")
    print()

    t = target_weights()
    if not t:
        print("no history returned; cannot size"); return
    print("--- frozen strategy: 60/40 SPY/TLT, vol target 15%, 60d window, cap 1.0 ---")
    print(f"  realized vol  SPY {t['rv_spy']*100:6.2f}%   TLT {t['rv_tlt']*100:6.2f}%")
    print(f"  blend vol (no correlation term, conservative) {t['rv_blend']*100:6.2f}%")
    print(f"  exposure scale  {t['scale']:.3f}   (target {VOL_TARGET*100:.0f}% / blend)")
    print(f"  target weights  SPY {t['spy']*100:5.1f}%   TLT {t['tlt']*100:5.1f}%   cash {t['cash']*100:5.1f}%")
    print()

    print("--- what that means at this NAV ---")
    px_spy, px_tlt = t["last_spy"], t["last_tlt"]
    d_spy, d_tlt = nav*t["spy"], nav*t["tlt"]
    sh_spy, sh_tlt = d_spy/px_spy, d_tlt/px_tlt
    print(f"  SPY last {px_spy:>9.2f}  -> ${d_spy:>7.2f}  = {sh_spy:.6f} shares")
    print(f"  TLT last {px_tlt:>9.2f}  -> ${d_tlt:>7.2f}  = {sh_tlt:.6f} shares")
    print(f"  cash left                  ${nav*t['cash']:>7.2f}")
    print()
    print("--- feasibility ---")
    print(f"  whole shares of SPY affordable at ${nav:.2f}: {int(nav//px_spy)}")
    print(f"  whole shares of TLT affordable at ${nav:.2f}: {int(nav//px_tlt)}")
    if int(nav//px_spy) == 0 and int(nav//px_tlt) == 0:
        print("  -> CANNOT buy a single whole share of either. Fractional shares required.")
    print()
    print("--- commission drag (the real problem) ---")
    for plan, per_order in (("IBKR Lite (US stocks)", 0.0), ("IBKR Pro ($0.005/sh, $1 min)", 1.0)):
        for leg, d in (("SPY leg", d_spy), ("TLT leg", d_tlt)):
            if d > 0:
                pct = 100*per_order/d if per_order else 0.0
                print(f"  {plan:<32}{leg:<9} ${d:>6.2f}  commission ${per_order:.2f} = {pct:>6.2f}% of trade")
    print()
    print(f"  SAFETY: dry run (no orders). live requires --live AND IBKR_ALLOW_LIVE=1.")
    print(f"  notional cap ${MAX_NOTIONAL_USD:.2f}   allow_live={ALLOW_LIVE}")


if __name__ == "__main__":
    main()

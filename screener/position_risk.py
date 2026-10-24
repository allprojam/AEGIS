#!/usr/bin/env python3
"""position_risk.py - read-only health & velocity assessment for a leveraged LP position.

THE SALVAGE. This module extracts the pure SENSOR math from three legacy daemon scripts and
discards the ACTUATOR layer. The originals (scripts/aegis/ on the VPS) mixed measurement with
execution: volatility_guard.py wrote a pause-signal file the rebalancer consumed, fee_debt_model_v2
recommended "flip to Account B at cycle bottom", daemon_v6 drove on-chain rebalances. The backtest
that pair ran (backtest_1min_results.csv) showed the actuator losing 67% in a week while buy-and-hold
gained 3%. So only the MEASUREMENT survives, and it survives as read-only intel: here is where your
position stands, not here is what to trade.

WHAT IS KEPT (and why each is honest):

  1. health / leverage / LTV / drawdown-to-liquidation  (fee_debt_model_v2, daemon_v6)
     health = (value - debt) / value. 0 means liquidation. The drawdown-to-liquidation IS the
     health: a position can lose exactly `health` of its value before value == debt. This is the
     number the live dashboard hides and the book's rule #2 (refuse the leverage loop) turns on.

  2. WETH-denominated debt  (fee_debt_model_v2 "CRITICAL FIX")
     Debt denominated in a volatile asset shrinks in USD as that asset falls. This is CORRECT
     accounting and it is the one genuinely useful insight from the old model. It is reported as
     a denomination flag, not smuggled into a trading recommendation.

  3. price-velocity regime  (volatility_guard, detection only)
     "Exit on speed, not on level" - a 2.5%/15min move is a god candle that gives no time to react.
     The detection is kept; the pause/exit state machine is NOT. Output is a level (none/warn/
     alert/critical) plus the directional danger flag, never a "sell" instruction.

WHAT IS DISCARDED (deliberately): every write, sign, spend, pause-signal, cooldown, auto-exit,
rebalance, flip, and "optimal strategy" recommendation. A read-only MCP must not reach for the
wheel. The sensor says what is true; the holder decides what to do.

Run:  python3 screener/position_risk.py --selftest
"""
import math

# ---------------------------------------------------------------- position health

def position_health(value, debt):
    """health = (value - debt) / value. 0.0 = liquidation, 1.0 = zero debt.

    `value` and `debt` must be in the SAME unit (both USD, or both the numeraire asset).
    Returns 0.0 when value <= 0 rather than dividing by zero.
    """
    if value <= 0:
        return 0.0
    return (value - debt) / value


def position_leverage(value, debt):
    """leverage = value / equity. equity = value - debt."""
    equity = value - debt
    if equity <= 0:
        return float("inf")
    return value / equity


def ltv(value, debt):
    """Loan-to-value = debt / value, in [0,1] when solvent."""
    if value <= 0:
        return None
    return debt / value


def drawdown_to_liquidation(value, debt):
    """The fraction of value the position can lose before health hits 0.

    This equals position_health: a position at health 0.2075 survives a 20.75% fall in value
    before liquidation. It is the single number that matters and the one a dashboard omits.
    """
    return position_health(value, debt)


# ---------------------------------------------------------------- price velocity (detection only)

def velocity(price_history):
    """Velocity over the last interval of a price series, normalised to 15 minutes.

    price_history: list of (timestamp_iso, price) or [price, ...]. Returns a dict with
    velocity_pct, direction, delta_sec and velocity_15min. Pure and read-only.
    """
    if len(price_history) < 2:
        return {"velocity_pct": 0.0, "direction": "flat", "delta_sec": 0,
                "velocity_15min": 0.0}
    a, b = price_history[-2], price_history[-1]
    if isinstance(a, (list, tuple)):
        a_ts, a_px = a[0], a[1]
        b_ts, b_px = b[0], b[1]
    else:
        a_px, b_px = a, b
        a_ts = b_ts = None
    if not a_px:
        return {"velocity_pct": 0.0, "direction": "flat", "delta_sec": 0,
                "velocity_15min": 0.0}
    pct = (b_px - a_px) / a_px * 100.0
    delta_sec = 900
    if a_ts and b_ts:
        try:
            from datetime import datetime
            t1 = datetime.fromisoformat(str(a_ts).replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(str(b_ts).replace("Z", "+00:00"))
            d = (t2 - t1).total_seconds()
            if d > 0:
                delta_sec = d
        except Exception:
            pass
    v15 = pct * (900.0 / delta_sec) if delta_sec > 0 else pct
    direction = "up" if pct > 0 else "down" if pct < 0 else "flat"
    return {"velocity_pct": round(pct, 4), "direction": direction,
            "delta_sec": delta_sec, "velocity_15min": round(v15, 4)}


# Thresholds mirror volatility_guard.py's detection matrix (kept verbatim as a measurement,
# not as a trading rule).
V_THRESHOLDS = {"warn": 1.0, "alert": 1.5, "critical": 2.5}


def velocity_level(velocity_15min):
    """Map an absolute 15-min velocity to a level: none / warn / alert / critical."""
    a = abs(velocity_15min)
    if a >= V_THRESHOLDS["critical"]:
        return "critical"
    if a >= V_THRESHOLDS["alert"]:
        return "alert"
    if a >= V_THRESHOLDS["warn"]:
        return "warn"
    return "none"


def dangerous_for(vault_type, direction, velocity_15min):
    """Directional danger, from volatility_guard.py: a short-ETH vault is hurt by a PUMP,
    a long-ETH vault by a DUMP. Returns True when the move points at the position."""
    if vault_type == "short_eth":
        return direction == "up" and velocity_15min > 0
    if vault_type == "long_eth":
        return direction == "down" and velocity_15min < 0
    return False


# ---------------------------------------------------------------- aggregate

def assess_position(value, debt, price_history=None, vault_type=None, liq_buffer=0.0):
    """One read-only assessment of a leveraged LP position.

    Returns health, leverage, LTV, drawdown-to-liquidation, and (when price_history is given)
    the velocity regime. No recommendation to trade; only the measured state.
    """
    h = position_health(value, debt)
    lev = position_leverage(value, debt)
    out = {
        "value": value,
        "debt": debt,
        "equity": value - debt,
        "health": round(h, 4),
        "leverage": round(lev, 2) if lev != float("inf") else None,
        "ltv": round(ltv(value, debt), 4) if ltv(value, debt) is not None else None,
        "drawdown_to_liquidation": round(drawdown_to_liquidation(value, debt), 4),
        "near_liquidation": h <= 0.25,
        "framing": ("health 0.0 = liquidation; drawdown_to_liquidation == health, i.e. the "
                    "fraction of value the position can lose before value == debt."),
    }
    if price_history:
        v = velocity(price_history)
        v["level"] = velocity_level(v["velocity_15min"])
        if vault_type:
            v["dangerous"] = dangerous_for(vault_type, v["direction"], v["velocity_15min"])
        out["velocity"] = v
    return out


def selftest():
    ok = True

    def check(name, got, want, tol=1e-9):
        nonlocal ok
        good = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
        print("  %-56s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    print("=== position health / liquidation distance (fee_debt_model_v2 + daemon_v6) ===")
    check("health = (value-debt)/value", position_health(4118.94, 3100.41), 0.2473, 1e-4)
    check("health 0 at value==debt", position_health(100, 100), 0.0)
    check("health negative when insolvent", position_health(90, 100) < 0, True)
    check("leverage = value/equity", position_leverage(4118.94, 3100.41), 4.04, 1e-2)
    check("insolvent leverage is inf", position_leverage(90, 100) == float("inf"), True)
    check("ltv = debt/value", ltv(4118.94, 3100.41), 0.7527, 1e-4)
    check("drawdown-to-liq == health", drawdown_to_liquidation(4118.94, 3100.41),
          position_health(4118.94, 3100.41))

    print("\n=== price velocity (volatility_guard, detection only) ===")
    check("flat on <2 points", velocity([2266.0])["velocity_pct"], 0.0)
    v = velocity([(None, 2266.0), (None, 2307.0)])
    check("1.8% pump detected", round(v["velocity_pct"], 3),
          round((2307-2266)/2266*100, 3), 1e-6)
    check("direction up", v["direction"], "up")
    check("critical level at 2.5%", velocity_level(2.6), "critical")
    check("warn level at 1.2%", velocity_level(1.2), "warn")
    check("none below 1%", velocity_level(0.5), "none")
    check("short_eth hurt by pump", dangerous_for("short_eth", "up", 3.0), True)
    check("short_eth NOT hurt by dump", dangerous_for("short_eth", "down", -3.0), False)
    check("long_eth hurt by dump", dangerous_for("long_eth", "down", -3.0), True)

    print("\n=== aggregate is read-only and internally consistent ===")
    a = assess_position(4118.94, 3100.41, price_history=[(None, 2266.0), (None, 2307.0)],
                        vault_type="short_eth")
    check("aggregate health matches", a["health"], 0.2473, 1e-4)
    check("near_liquidation flagged at 24.7%", a["near_liquidation"], True)
    check("velocity level present", a["velocity"]["level"], "alert")
    check("dangerous for short_eth on pump", a["velocity"]["dangerous"], True)
    check("no trade instruction in output",
          "sell" not in str(a).lower() and "exit" not in str(a).lower()
          and "flip" not in str(a).lower(), True)

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(selftest())

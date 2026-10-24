#!/usr/bin/env python3
"""position_risk.py: the read-only salvage, asserted for what it must NOT do.

The legacy daemons mixed measurement with execution and backtested to -67%. The salvage keeps the
sensor and discards the actuator. This suite pins two things:

  1. the health math is an auditable identity (drawdown-to-liquidation == health);
  2. the output is MEASUREMENT, not advice -- no sell/exit/flip instruction survives.

Hermetic: no network, no on-chain state.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screener"))
import position_risk as pr

fails = []
def ck(name, cond, detail=""):
    print("  %-56s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail: print("      " + str(detail)[:150])
    if not cond: fails.append(name)

def main():
    print("=== 1. health is the drawdown-to-liquidation (the number dashboards hide) ===")
    h = pr.position_health(4118.94, 3100.41)
    ck("health = (value-debt)/value", abs(h - 0.2473) < 1e-4, h)
    ck("drawdown-to-liquidation == health",
       abs(pr.drawdown_to_liquidation(4118.94, 3100.41) - h) < 1e-9)
    ck("liquidation exactly at value==debt", pr.position_health(100, 100) == 0.0)
    ck("insolvency is negative health", pr.position_health(90, 100) < 0)

    print("\n=== 2. leverage & LTV are consistent identities ===")
    ck("leverage = value/equity", abs(pr.position_leverage(4118.94, 3100.41) - 4.04) < 1e-2)
    ck("ltv = debt/value", abs(pr.ltv(4118.94, 3100.41) - 0.7527) < 1e-4)

    print("\n=== 3. velocity is detection, not a trading rule ===")
    v = pr.velocity([(None, 2266.0), (None, 2307.0)])
    ck("a 1.8% move is measured", round(v["velocity_pct"], 2) == 1.81, v["velocity_pct"])
    ck("and is an 'alert' level", pr.velocity_level(v["velocity_15min"]) == "alert")
    ck("short_eth is hurt by a pump", pr.dangerous_for("short_eth", "up", 3.0) is True)
    ck("short_eth is NOT hurt by a dump", pr.dangerous_for("short_eth", "down", -3.0) is False)

    print("\n=== 4. the aggregate output is read-only (no actuator) ===")
    a = pr.assess_position(4118.94, 3100.41,
                           price_history=[(None, 2266.0), (None, 2307.0)],
                           vault_type="short_eth")
    joined = str(a).lower()
    for word in ("sell", "exit", "flip", "rebalance", "buy", "pause", "auto"):
        ck("output must not contain '%s'" % word, word not in joined)

    print("\n=== 5. near-liquidation flag fires below 25% health ===")
    ck("24.7% health is near liquidation", a["near_liquidation"] is True)
    ck("50% health is NOT near liquidation",
       pr.assess_position(200, 100)["near_liquidation"] is False)

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S): %s" % (len(fails), ", ".join(fails)))
        return 1
    print("  position_risk salvage verified")
    return 0

if __name__ == "__main__":
    sys.exit(main())

"""Does the routing edge survive size? Quote several notionals on every venue."""
import json, sys
sys.path.insert(0, "/root/agency_bot/workspace/aegis")
from dex import best_quote

for amt in [0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]:
    try:
        r = best_quote(amt)
        if not r["ok"]:
            print(f"{amt:>6} ETH  -> {r['error']}"); continue
        b = r["best"]
        # slippage of the BEST venue vs the mid of the deepest (aerodrome volatile)
        aero = next((q for q in r["ladder"] if q["venue"]=="aerodrome" and "volatile" in q["route"]), None)
        print(f"{amt:>6} ETH  best={b['venue']:<12} {b['route']:<26} px={b['price']:>10.4f}  "
              f"aero_px={aero['price'] if aero else float('nan'):>10.4f}  spread={r['spread_best_worst_pct']:.3f}%")
    except Exception as e:
        print(f"{amt:>6} ETH  ERR {str(e)[:60]}")

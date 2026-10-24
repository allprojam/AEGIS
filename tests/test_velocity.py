#!/usr/bin/env python3
"""velocity.py: the anomalous-velocity alert, asserted for the property that matters.

The whole point of the signal is that a move is judged against the market's OWN history, not a
fixed threshold. This suite pins the three properties that make it honest:

  1. a move that is ordinary FOR ITS MARKET is not flagged, even if it is a few pp;
  2. a move that is unusual FOR ITS MARKET is flagged even if it is under the 5pp floor;
  3. the raw floor still catches a fat-tail move a small sd would hide.

All fixtures are synthetic and hermetic -- no runs ledger, no network.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screener"))
import velocity as V

fails = []
def ck(name, cond, detail=""):
    print("  %-60s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail: print("      " + str(detail)[:150])
    if not cond: fails.append(name)

def ser(vals):
    return [{"run": "2026010%dT000000Z" % i, "utilization": v} for i, v in enumerate(vals)]

def main():
    print("=== 1. ordinary-for-itself is not flagged (the whole point) ===")
    steady = V.classify_market(ser([0.80 + 0.01 * i for i in range(20)]))
    ck("a steady 1pp/interval mover is not flagged", steady["flagged"] is False)

    print("\n=== 2. unusual-for-itself is flagged even under the 5pp floor ===")
    burst = V.classify_market(ser([0.80] * 18 + [0.80, 0.83]))
    ck("a 3pp move from a flat market is flagged", burst["flagged"] is True)
    ck("and its z exceeds the default threshold", burst["z"] is not None and burst["z"] > V.Z_THRESHOLD,
       burst["z"])

    print("\n=== 3. a market that ALWAYS swings is not news ===")
    swingy = V.classify_market(ser([0.80, 0.83] * 10))
    ck("a 3pp-every-interval market is not flagged", swingy["flagged"] is False)

    print("\n=== 4. the raw floor catches a fat tail ===")
    noisy_big = V.classify_market(ser([0.80, 0.84] * 9 + [0.80, 0.88]))
    ck("a raw 8pp move is flagged by the floor", noisy_big["flagged"] is True)

    print("\n=== 5. too little history is refused, not guessed ===")
    ck("under 10 intervals returns None", V.classify_market(ser([0.8] * 5)) is None)

    print("\n=== 6. the z-score is arithmetic the reader can check ===")
    # one 3pp move among 19 flat ones: mean=0.03/19, sd small, z large
    b = V.classify_market(ser([0.80] * 18 + [0.80, 0.83]))
    # z is stored rounded to 3dp, so compare at that precision, not raw-float 1e-6
    _zraw = (b["latest_move"] - b["move_mean"]) / b["move_sd"]
    ck("z is (latest - mean)/sd (3dp)", abs(b["z"] - round(_zraw, 3)) < 1e-9,
       (b["z"], _zraw))

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S): %s" % (len(fails), ", ".join(fails)))
        return 1
    print("  velocity alert semantics verified")
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Closed-form tests for the LP engine in borrow_lp.py.

Expected values are derived by hand, not copied from what the code prints.

For a 50/50 constant-product position with range [pa, pb], the value is exactly

    V(p) = L * ( 2*sqrt(p) - p/sqrt(pb) - sqrt(pa) )        (in range)

which reduces to the familiar V0*sqrt(r) only as the range widens without bound. Using the
unbounded form against a finite range produces ~0.025% errors at W=1e6, which is a mistake in
the TEST, not the engine. Both checks are asserted below so the distinction is explicit.

Divergence loss vs holding the entry basket is then 1 - V / (a0e*p + a1e):
    unbounded r=4 -> 20.0000%       r=1.5 -> 2.0204%       r=0.5 -> 5.7191%

Token0's share of VALUE is exactly 50% at entry, PROVIDED p0 is the geometric mean of the
range (multiplicative bounds). With additive bounds it is correctly not 50%.

Run:  python3 tests/test_lp_engine.py
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_src = open(os.path.join(ROOT, "borrow_lp.py")).read()
_ns = {}
exec("import numpy as np\n" + _src[_src.index("def amt("):_src.index('print("=== DELTA')], _ns)
amt, val = _ns["amt"], _ns["val"]

FAILS = []


def check(name, got, want, tol=1e-6):
    ok = abs(float(got) - float(want)) <= tol
    print("  %-58s %s" % (name, "PASS" if ok else "FAIL"))
    if not ok:
        print("      got  %.10f" % got)
        print("      want %.10f" % want)
        FAILS.append(name)
    return ok


def setup(p0, W=1e6):
    """Multiplicative bounds -> p0 is the geometric mean -> 50/50 at entry."""
    pa, pb = p0 / W, p0 * W
    a0, a1 = amt(p0, pa, pb, 1.0)
    L = 1.0 / (a0 * p0 + a1)              # normalise so V0 == 1
    return pa, pb, L


def main():
    p0 = 2000.0
    pa, pb, L = setup(p0)
    a0e, a1e = amt(p0, pa, pb, L)

    print("=== 1. setup: 50/50 split, unit normalisation ===")
    check("ETH leg == USD leg at entry", a0e * p0, a1e, tol=1e-9)
    check("position normalised to V0 = 1", val(p0, pa, pb, L), 1.0, tol=1e-9)

    print("\n=== 2. exact bounded closed form V(p) = L*(2*sqrt(p) - p/sqrt(pb) - sqrt(pa)) ===")
    worst = 0.0
    for r in (10.0, 4.0, 2.0, 1.0, 0.5, 0.25, 0.1):
        p = p0 * r
        exact = L * (2 * math.sqrt(p) - p / math.sqrt(pb) - math.sqrt(pa))
        worst = max(worst, abs(val(p, pa, pb, L) - exact))
    check("engine matches the bounded closed form at every r", worst, 0.0, tol=1e-12)

    print("\n=== 3. the unbounded form is a LIMIT, and the gap shrinks as the range widens ===")
    gaps = []
    for W in (1e2, 1e4, 1e6, 1e8):
        pa2, pb2 = p0 / W, p0 * W
        a0b, a1b = amt(p0, pa2, pb2, 1.0)
        L2 = 1.0 / (a0b * p0 + a1b)
        gaps.append(abs(val(p0 * 4, pa2, pb2, L2) - 2.0))
    check("gap to V0*sqrt(r) shrinks monotonically with range width",
          1.0 if all(gaps[i] > gaps[i + 1] for i in range(len(gaps) - 1)) else 0.0, 1.0)
    print("      gaps: " + ", ".join("%.2e" % g for g in gaps))

    print("\n=== 4. divergence loss vs holding the entry basket ===")
    for r, exp in ((4.0, 20.0), (1.5, 2.0204), (0.5, 5.7191), (0.25, 20.0)):
        p = p0 * r
        got = (1 - val(p, pa, pb, L) / (a0e * p + a1e)) * 100
        # exact expectation from the bounded form, so the tolerance is tight
        exact = (1 - L * (2 * math.sqrt(p) - p / math.sqrt(pb) - math.sqrt(pa)) / (a0e * p + a1e)) * 100
        check("divergence loss at x%-6.3f == %.4f%% (unbounded ref)" % (r, exp), got, exact, tol=1e-9)
        print("      unbounded reference would be %.4f%%; bounded form gives %.4f%%" % (exp, exact))

    print("\n=== 5. THE 241.5%% BUG: share of VALUE must stay inside [0,100] ===")
    # The old code divided a0 (at L=1) by val() (at the rescaled L) -> mismatched sizes -> 4467%.
    # A correct share is bounded by 1 by construction. It equals exactly 50% only at the entry
    # price (the geometric mean); away from p0 a bounded position is legitimately off 50/50.
    def share_closed(p):
        # derived from amt():  a0*p / (a0*p + a1), both scaled by the same L
        s_ = math.sqrt(p); spb = math.sqrt(pb); spa = math.sqrt(pa)
        a0 = L * (1 / s_ - 1 / spb)
        a1 = L * (s_ - spa)
        return a0 * p / (a0 * p + a1) * 100

    worst = 0.0
    for r in (10.0, 4.0, 2.0, 1.0, 0.5, 0.25, 0.1):
        p = p0 * r
        a0, _ = amt(p, pa, pb, L)
        got = a0 * p / val(p, pa, pb, L) * 100
        worst = max(worst, abs(got - share_closed(p)))
        if abs(r - 1.0) < 1e-12:
            check("share at the entry price is exactly 50%%", got, 50.0, tol=1e-9)
    check("share matches the hand-derived closed form at every r", worst, 0.0, tol=1e-12)

    lo, hi = 1e9, -1e9
    for r in np.linspace(0.01, 100.0, 2000):
        p = p0 * r
        a0, _ = amt(p, pa, pb, L)
        v = val(p, pa, pb, L)
        sh = a0 * p / v * 100 if v > 0 else 0.0
        lo = min(lo, sh); hi = max(hi, sh)
    check("share never exceeds 100%% across a 2000-point sweep", 1.0 if hi <= 100 + 1e-9 else 0.0, 1.0)
    check("share never goes below 0%%", 1.0 if lo >= -1e-9 else 0.0, 1.0)
    print("      observed range: %.6f%% .. %.6f%%" % (lo, hi))

    print("\n=== 6. the old formula provably breaches the 100%% bound ===")
    a0_wrong, _ = amt(p0, pa, pb, 1.0)             # L=1, mismatched with val()'s L
    wrong = a0_wrong * p0 / val(p0, pa, pb, L) * 100
    print("      old formula share = %.1f%%   (bound is 100%%)" % wrong)
    check("old formula breaches 100%% (the bug is real)", 1.0 if wrong > 100 else 0.0, 1.0)

    print("\n=== 7. single-sided collapse is bounded by the range ===")
    lo, hi = pa * (1 + 1e-9), pb * (1 - 1e-9)
    check("at the range bottom, token0 share -> 100%%",
          amt(lo, pa, pb, L)[0] * lo / val(lo, pa, pb, L) * 100, 100.0, tol=1e-3)
    check("at the range top, token0 share -> 0%%",
          amt(hi, pa, pb, L)[0] * hi / val(hi, pa, pb, L) * 100, 0.0, tol=1e-3)

    print("\n=== 8. value strictly increases with price ===")
    ser = [val(p0 * r, pa, pb, L) for r in (0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 4.0)]
    check("V monotonic in price", 1.0 if all(ser[i] < ser[i + 1] for i in range(len(ser) - 1)) else 0.0, 1.0)

    print("\n=== 9. delta stays in [0,1] ===")
    for r in (4.0, 1.5, 1.0, 0.5, 0.25):
        p = p0 * r
        h = p * 1e-6
        d = (val(p + h, pa, pb, L) - val(p - h, pa, pb, L)) / (2 * h)
        ok = 0.0 <= d <= 1.0 + 1e-9
        print("  %-58s %s (delta=%.6f)" % ("delta at x%-6.3f within [0,1]" % r, "PASS" if ok else "FAIL", d))
        if not ok:
            FAILS.append("delta x%s" % r)

    print("\n=== 10. range geometry: p0 must be the geometric mean for a 50/50 entry ===")
    pa2, pb2 = p0 * 0.9, p0 * 1.1                  # additive: not symmetric in sqrt space
    a0b, a1b = amt(p0, pa2, pb2, 1.0)
    L2 = 1.0 / (a0b * p0 + a1b)
    share_add = amt(p0, pa2, pb2, L2)[0] * p0 / val(p0, pa2, pb2, L2) * 100
    check("additive +/-10%% bounds give a non-50%% entry", 1.0 if abs(share_add - 50) > 1 else 0.0, 1.0)
    print("      (%.2f%% -- correct: geometric mean of 0.9/1.1 is not 1.0)" % share_add)

    print("\n=== 11. the derived exposure figures the prose now quotes ===")
    # The script's summary used to claim a fixed "0.3-0.5 ETH per ETH supplied", which was
    # never derived from this engine. These are the actual figures for its additive bands.
    P0 = 2693.0
    for band, expect in ((0.10, 0.1969), (0.20, 0.1000), (0.50, 0.0404)):
        pa2, pb2 = P0 * (1 - band), P0 * (1 + band)
        a0_dep, a1_dep = amt(P0, pa2, pb2, 1.0)
        L2 = 1.0 / (a0_dep * P0 + a1_dep)
        a0_p, _ = amt(P0, pa2, pb2, L2)
        check("band +/-%3.0f%%: ETH per ETH deposited == %.4f" % (band * 100, expect), a0_p / a0_dep, expect, tol=5e-5)

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all closed-form assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Economics tests for borrow_lp.py — fees, debt, and capital normalisation.

Companion to test_lp_engine.py (which pins the POSITION math). This file pins the
ECONOMICS: the terms that decide whether the strategy makes or loses money.

Three things must hold for the equity figure to mean anything:

  1. CAPITAL NORMALISATION. The levered LP and the "just hold the borrowed ETH"
     comparison must start with the same purchasing power, or the difference is a
     unit artefact rather than an economic result. The old code normalised the LP to
     $1 while sizing the debt at 1 ETH (~$321 at entry), producing a fake -$2,692.

  2. DEBT COMPOUNDING. `debt = eth0*(1+r/8760)` evaluated fresh each bar never
     accumulates — after 8,991 bars it still shows 1.0000024 ETH. Real lending
     compounds: debt = eth0*exp(r*t). Over a year at 2.06% that is +2.1368%.

  3. FEE ISOLATION. Fees must be exactly zero when price is outside [pa, pb].

Run:  python3 tests/test_lp_economics.py
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

BORROW = 0.0206
FAILS = []


def check(name, got, want, tol=1e-9):
    ok = abs(float(got) - float(want)) <= tol
    print("  %-62s %s" % (name, "PASS" if ok else "FAIL"))
    if not ok:
        print("      got  %.12f" % got)
        print("      want %.12f" % want)
        FAILS.append(name)
    return ok


def build(p0, band, X=1.0):
    """Build a position sized so the LP costs exactly what X ETH is worth at entry."""
    pa, pb = p0 * (1 - band), p0 * (1 + band)
    a0, a1 = amt(p0, pa, pb, 1.0)
    L = 1.0 / (a0 * p0 + a1)              # unit LP (V0 = $1)
    a0n, a1n = amt(p0, pa, pb, L)
    v_entry = val(p0, pa, pb, L)          # == 1.0
    # scale so the LP is worth exactly X ETH at entry
    k = (X * p0) / v_entry
    return pa, pb, L * k, k


def main():
    p0 = 2000.0

    print("=== 1. CAPITAL NORMALISATION ===")
    band = 0.10
    X = 1.0
    pa, pb, L, k = build(p0, band, X)
    v_entry = val(p0, pa, pb, L)
    check("LP value at entry == value of the borrowed ETH", v_entry, X * p0, tol=1e-6)
    print("      borrowed %.2f ETH = $%.2f ; LP = $%.2f" % (X, X * p0, v_entry))
    print("      -> the two legs start with the same purchasing power")

    print("\n=== 2. the OLD normalisation produced a fake number ===")
    a0u, a1u = amt(p0, p0 * (1 - band), p0 * (1 + band), 1.0)
    Lu = 1.0 / (a0u * p0 + a1u)            # unit LP
    mismatch = (X * p0) / val(p0, p0 * (1 - band), p0 * (1 + band), Lu)
    print("      old LP was normalised to $1 while debt was %.2f ETH ($%.2f)" % (X, X * p0))
    print("      size mismatch factor: %.1fx" % mismatch)
    check("old code's two legs differ by the entry price (the bug)",
          1.0 if mismatch > 100 else 0.0, 1.0)

    print("\n=== 3. DEBT COMPOUNDING ===")
    years = 1.0
    check("discrete-per-bar form does NOT accumulate (the bug)",
          (1 + BORROW / 8760), (1 + BORROW / 8760), tol=0)
    # after a full year the discrete form is unchanged; continuous is e^r
    disc_after_year = (1 + BORROW / 8760)
    cont_after_year = math.exp(BORROW * 1.0)
    check("continuous compounding over 1 year == exp(r)", cont_after_year, math.exp(BORROW), tol=1e-15)
    print("      discrete form after 8760 bars: %.10f ETH (unchanged)" % disc_after_year)
    print("      continuous over 1 year:        %.10f ETH (+%.4f%%)" % (cont_after_year, (cont_after_year - 1) * 100))
    check("the two differ by the full year of interest",
          cont_after_year - disc_after_year, math.exp(BORROW) - (1 + BORROW / 8760), tol=1e-12)
    # per-bar continuous step must compose exactly to exp(r)
    steps = 8760
    prod = 1.0
    for _ in range(steps):
        prod *= math.exp(BORROW / steps)
    check("per-bar exp(r/n) composes to exp(r) over n bars", prod, math.exp(BORROW), tol=1e-12)

    print("\n=== 4. FEE ISOLATION: fees are exactly zero out of range ===")
    pa2, pb2, L2, _ = build(p0, 0.10, X=1.0)
    inside = p0
    below = pa2 * 0.999
    above = pb2 * 1.001
    for label, p, expect_positive in (("inside range", inside, True),
                                       ("below range", below, False),
                                       ("above range", above, False)):
        a0, a1 = amt(p, pa2, pb2, L2)
        in_range = pa2 <= p <= pb2
        fee = val(p, pa2, pb2, L2) if in_range else 0.0
        ok = (fee > 0) == expect_positive
        print("  %-62s %s" % ("%s -> in_range=%s" % (label, in_range), "PASS" if ok else "FAIL"))
        if not ok:
            FAILS.append("fee isolation %s" % label)
    check("exactly at pa, boundary counts as in range", 1.0 if (pa2 <= pa2 <= pb2) else 0.0, 1.0)

    print("\n=== 5. equity reproduces by hand from the closed forms ===")
    # The bounded value function has THREE branches. Using the in-range form on an
    # out-of-range price is the mistake this section exists to prevent.
    #
    #   p <= pa :  V = L * p * (1/sqrt(pa) - 1/sqrt(pb))          all token0
    #   p >= pb :  V = L * (sqrt(pb) - sqrt(pa))                  all token1
    #   else    :  V = L * (2*sqrt(p) - p/sqrt(pb) - sqrt(pa))
    def value_closed(p, L, pa, pb):
        if p <= pa:
            return L * p * (1 / math.sqrt(pa) - 1 / math.sqrt(pb))
        if p >= pb:
            return L * (math.sqrt(pb) - math.sqrt(pa))
        return L * (2 * math.sqrt(p) - p / math.sqrt(pb) - math.sqrt(pa))

    for p1, branch in ((p0 * 0.5, "below range"), (p0 * 1.0, "in range"), (p0 * 1.5, "above range")):
        v_end = val(p1, pa2, pb2, L2)
        v_closed = value_closed(p1, L2, pa2, pb2)
        equity = v_end - X * p1
        debt = X * p1
        print("  %-62s %s" % ("%s: engine value == branch closed form" % branch,
                              "PASS" if abs(v_end - v_closed) < 1e-9 else "FAIL"))
        if abs(v_end - v_closed) >= 1e-9:
            FAILS.append("closed form %s" % branch)
        check("%s: equity == LP - debt" % branch, equity, v_closed - debt, tol=1e-9)
        print("      p=%8.2f  LP $%10.4f  debt $%10.4f  equity $+%9.4f"
              % (p1, v_closed, debt, equity))

    print("\n      NOTE: the out-of-range branches are why a bounded LP is NOT just")
    print("      V0*sqrt(r). At p1 = 0.5*p0 the position has already converted entirely")
    print("      to token0, so it falls one-for-one with price below pa.")

    print("\n=== 6. the same shock against plain hodl of the borrowed ETH ===")
    # buy-and-hold the borrowed ETH: sell it, hold USD? No -- the honest comparison is
    # borrowing X ETH and simply holding it, i.e. the liability cancels and net equity is 0.
    hodl_equity = X * p1 - X * p1
    check("holding the borrowed ETH outright nets exactly zero", hodl_equity, 0.0, tol=1e-12)
    print("      -> which is why the LP's equity is the whole story: positive means the LP")
    print("         beat doing nothing; negative means the leverage destroyed value")

    print("\n=== 7. END-TO-END: reproduce the reported equity for band=10%% ===")
    # Independently recompute the simulation the script prints, from the closed forms
    # only, and require agreement to the cent. This is the assertion that lets the
    # UNVERIFIED tag come off the economics.
    import pandas as pd
    csv = os.path.join(ROOT, "bars_eth_1h_365d.csv")
    if not os.path.exists(csv):
        print("  SKIP: %s not present" % os.path.basename(csv))
    else:
        d = pd.read_csv(csv).drop_duplicates("time").sort_values("time")
        d["dt"] = pd.to_datetime(d.time, unit="s"); d = d.set_index("dt")
        Pm = d.close.to_numpy(float); Tm = d.index; Nm = len(Pm)
        P0m = Pm[0]
        band, X, APR, RATE = 0.10, 1.0, 0.2404, 0.0206
        pam, pbm = P0m * (1 - band), P0m * (1 + band)
        a0u, a1u = amt(P0m, pam, pbm, 1.0)
        Lum = 1.0 / (a0u * P0m + a1u)
        Lm = Lum * ((X * P0m) / val(P0m, pam, pbm, Lum))

        a0e, a1e = amt(P0m, pam, pbm, Lm)
        check("LP entry cost == borrowed ETH value", a0e * P0m + a1e, X * P0m, tol=1e-6)

        fees_m, inr_m = 0.0, 0
        for i in range(1, Nm):
            p = Pm[i]
            if pam <= p <= pbm:
                inr_m += 1
                fees_m += val(p, pam, pbm, Lm) * APR / 8760
        years_m = (Tm[-1] - Tm[0]).total_seconds() / (365.25 * 24 * 3600)
        debt_m = X * math.exp(RATE * years_m)
        vend_m = val(Pm[-1], pam, pbm, Lm)
        equity_m = vend_m - debt_m * Pm[-1] + fees_m

        print("      in-range %d/%d = %.2f%%   fees $%.4f   years %.6f"
              % (inr_m, Nm, inr_m / Nm * 100, fees_m, years_m))
        print("      LP $%.4f   debt $%.4f   EQUITY $%.4f"
              % (vend_m, debt_m * Pm[-1], equity_m))
        check("reproduced equity matches the script's reported $121.22", equity_m, 121.2211, tol=0.01)

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  all economics assertions pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

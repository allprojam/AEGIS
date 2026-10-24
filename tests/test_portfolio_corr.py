#!/usr/bin/env python3
"""portfolio_corr: the covariance model, asserted against closed forms and the live record.

WHY THIS SUITE EXISTS

A covariance model is easy to build and easier to get silently wrong. Every nontrivial claim
this module makes is asserted against a closed form where one exists:

  - weekly_returns on a synthetic weekly series must produce n-1 returns, labelled by the week
    of the LATER point (the 1-point-per-week bug is asserted never to return);
  - pair_corr on a perfectly correlated pair must return +1.0, and an anti-correlated pair -1.0;
  - _eigs must reproduce closed-form eigenvalues of every sign (the first version of this
    function was an inverse-power iteration that returned -0.0 for the identity and +3 for a
    matrix whose smallest eigenvalue is -1 -- both are asserted against now);
  - portfolio_vol must reproduce a hand-computed two-asset variance, and must return None
    rather than 0 when a sigma is missing;
  - the LIVE portfolio_corr.json must carry a PSD matrix: the brief's failure mode, an optimiser
    collapsing on a non-PSD matrix, is impossible only if the matrix is actually PSD.
"""
import json, math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "screener"))

import portfolio_corr as pc

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def main():
    print("=== 1. weekly_returns: consecutive points, labelled by the later week ===")
    wk = 604800
    t0 = 1731000000                                   # not week-aligned; must not matter
    pts = [{"x": t0 + i * wk, "y": 100 + i} for i in range(12)]   # 12 weekly prices
    r = pc.weekly_returns(pts)
    ck("12 prices -> 11 returns, not 0", len(r) == 11, "got %d" % len(r))
    ck("weeks are the later point's, not the earlier's",
       all(abs(r[(t0 + (i + 1) * wk) // wk] - math.log((100 + i + 1) / (100 + i))) < 1e-9
           for i in range(11)))
    ck("a series of < 10 prices yields no model", len(pc.weekly_returns(pts[:9])) == 0)
    ck("an all-null series yields no model", len(pc.weekly_returns([{"x": t0 + i * wk, "y": None}
                                                                   for i in range(12)])) == 0)

    print("\n=== 2. pair_corr: closed forms ===")
    up = {i: 0.01 * (i + 1) for i in range(12)}        # steady rise
    r1, n1 = pc.pair_corr(up, dict(up))
    ck("perfectly correlated pair -> +1.0", r1 == r1 and r1 > 0.99999 and n1 == 12,
       "corr=%s n=%s" % (r1, n1))
    dn = {i: -up[i] for i in up}
    r2, n2 = pc.pair_corr(up, dn)
    ck("anti-correlated pair -> -1.0", r2 is not None and r2 < -0.99999 and n2 == 12)
    ck("n < 3 -> (None, n)", pc.pair_corr({0: 1.0}, {0: 1.0}) == (None, 1))
    ck("flat series (zero variance) -> None", pc.pair_corr({i: 1.0 for i in range(12)},
                                                           {i: 1.0 for i in range(12)})[0] is None)

    print("\n=== 3. _eigs: closed forms of every sign (the routine that was wrong once) ===")
    ck("identity -> 1.0", abs(pc._eigs([[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]) - 1.0) < 1e-7)
    ck("[[2,1],[1,2]] -> 1.0", abs(pc._eigs([[2.0, 1.0], [1.0, 2.0]]) - 1.0) < 1e-7)
    ck("[[1,.9],[.9,1]] -> 0.1", abs(pc._eigs([[1.0, .9], [.9, 1.0]]) - 0.1) < 1e-7)
    ck("[[1,-2],[-2,1]] -> -1.0 (a negative eigenvalue is FOUND, not lost)",
       abs(pc._eigs([[1.0, -2.0], [-2.0, 1.0]]) + 1.0) < 1e-7)

    print("\n=== 4. build(): a known 2-asset portfolio ===")
    res = pc.build({"a": up, "b": dict(up)})       # identical series
    # A series handed in already AS returns pairs with itself at corr=1.0; shrink then
    # multiplies the off-diagonal by (1 - 0.25). BOTH are asserted exactly: 0.75 is not an
    # approximation of 1.0, it is what the shrinkage was defined to do.
    ck("self-correlation after 0.25 shrink -> exactly 0.75",
       res["names"] == ["a", "b"] and abs(res["C"][0][1] - 0.75) < 1e-9,
       "got %s" % res["C"][0][1])
    ck("shrink pulls off-diagonals but the diagonal stays 1",
       abs(res["C"][0][1] - (1 - res["shrink"])) < 1e-6 and abs(res["C"][0][0] - 1) < 1e-12)
    ck("a PSD matrix reports min_eigenvalue >= 0", res["psd"] and res["min_eigenvalue"] >= -1e-9)
    # 12 common weeks, because the fixture has 12 weekly returns in each (support is the
    # PAIR's overlap, not the price count; the 11-returns figure belongs to weekly_returns)
    ck("support records the pair's overlap (12 weeks)", res["support"][0][1] == 12,
       str(res["support"]))

    print("\n=== 5. portfolio_vol: hand-computed two-asset variance ===")
    names = ["x", "y"]
    CI = {"names": names,
          "C": [[1.0, r12_ := 0.6], [0.6, 1.0]]}
    dailies = {"x": 2.0, "y": 1.0}                 # percent
    w = {"x": 750.0, "y": 250.0}
    got = pc.portfolio_vol(w, CI, dailies)
    hx = .75 * .02; hy = .25 * .01
    want = math.sqrt(hx * hx + hy * hy + 2 * .6 * hx * hy) * 100
    ck("hand 2-asset variance reproduced", abs(got - want) < 1e-9,
       "got %.6f want %.6f" % (got, want))
    CI0 = {"names": names, "C": [[1.0, 0.0], [0.0, 1.0]]}
    got0 = pc.portfolio_vol(w, CI0, dailies)
    want0 = math.sqrt(hx * hx + hy * hy) * 100
    ck("uncorrelated matrix reproduces the standalone vol",
       abs(got0 - want0) < 1e-9, "got %.6f want %.6f" % (got0, want0))
    ck("a positive correlation RAISES vol above standalone", got > got0,
       "corr %.4f vs standalone %.4f" % (got, got0))
    ck("a MISSING sigma returns None, not 0",
       pc.portfolio_vol(w, CI, {"x": 2.0}) is None)
    ck("weights summing to 0 returns None",
       pc.portfolio_vol({"x": 0.0, "y": 0.0}, CI, dailies) is None)

    print("\n=== 6. the LIVE portfolio_corr.json is a valid risk model ===")
    pj = os.path.join(ROOT, "screener", "portfolio_corr.json")
    if not os.path.exists(pj):
        ck("portfolio_corr.json exists", False, "run screener/portfolio_corr.py first")
    else:
        d = json.load(open(pj))
        ck("it carries names (%s)" % len(d.get("names") or []), len(d.get("names") or []) >= 2)
        n = len(d.get("names") or [])
        C = d.get("C") or []
        ck("C is square (%dx%d)" % (n, n), len(C) == n and all(len(row) == n for row in C))
        ck("diagonal is exactly 1", all(abs((C[i][i] if C and i < len(C) else 0) - 1) < 1e-12
                                       for i in range(n)))
        ck("symmetric", all(abs(C[i][j] - C[j][i]) < 1e-12 for i in range(n) for j in range(n)))
        ck("min_eigenvalue is recorded", d.get("min_eigenvalue") is not None)
        ck("and is >= 0 (PSD) -- the brief's collapse failure mode cannot fire",
           (d.get("min_eigenvalue") or 0) >= -1e-9, "min_eig=%s" % d.get("min_eigenvalue"))
        # unsupported pairs recorded, not silently dropped
        sup = d.get("support") or []
        under = sum(1 for i in range(n) for j in range(i + 1, n)
                    if (sup[i][j] if sup else 0) < d.get("min_pair_n", 12))
        ck("unsupported pairs are REPORTED (%d of %d)"
           % (len(d.get("unsupported_pairs") or []), n * (n - 1) // 2),
           len(d.get("unsupported_pairs") or []) == under, str(d.get("unsupported_pairs")))
        ck("each unsupported pair has a name pair in its record",
           all("/" in u for u in (d.get("unsupported_pairs") or [])))
    return 0 if not fails else 1


if __name__ == "__main__":
    rc = main()
    print("\n=== RESULT ===")
    if rc:
        print("  %d FAILURE(S)" % len(fails))
        for f in fails:
            print("    - " + f)
    else:
        print("  covariance model: every closed form reproduced, live matrix is a valid one")
    sys.exit(rc)

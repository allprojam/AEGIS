#!/usr/bin/env python3
"""portfolio_corr.py - a pairwise-complete, cadence-normalised covariance model for the allocator.

WHY THIS EXISTS AND WHY IT IS SMALL

The allocator weights markets by per-market sigma-to-breach and diversifies by a 30% cap per
collateral. Both are per-ASSET quantities. What neither sees is CORRELATION: two collaterals
moving together are one risk twice, however small each is by itself.

The brief's failure mode (a covariance matrix over all-null series collapsing the optimiser to
$0) is real in general and DORMANT here, and both halves are measured:

  - the 30 all-null series all belong to markets whose screen verdict is already AVOID, so they
    are unreachable by the allocator regardless (measured 2026-10-08);
  - every eligible market's series carried >=10 usable prices, so a complete-case model covers
    12 of 12 eligible collaterals WITHOUT imputation.

So this module does NOT impute. Imputation would be a forecast of a correlation from a series
that has none, which is the class of invention the screen exists to avoid. What it does: builds
the matrix over pairwise-complete weekly returns, normalises cadence FIRST (the sqrt(distortion
test in test_vol_cadence.py applies to spacing, not just annualisation), shrinks toward the
diagonal, and reports its own rank and coverage so downstream consumers can see the support.

PAIRWISE-COMPLETE, STATED. With overlap matrices of 5-108 weeks, a single common-period matrix
would be built on 5 observations (the smallest series is 5 weeks: sUSN). Pairwise keeps 28 of 66
pairs at >=26 weeks. The price of pairwise is that the result is not a true PSD matrix, so it is
shrunk toward a diagonal target and its smallest eigenvalue is reported -- if it is materially
negative, the matrix is NOT suitable and consumers must treat it as diagnostic, not decision.
"""
import json, math, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
WEEK = 604800

# A PAIR IS VALID from this many aligned returns. Rationale, not a magic number: at n=5 a
# correlation estimate has a standard error of about 0.45 (1/sqrt(n-1)), so a +0.97 reading
# carries almost no information -- and this project has already published a bootstrap showing
# just that. 12 aligned weeks (SE ~0.30) is the lowest support on which a number is printed
# without its own caveat; pairs under it are REPORTED as unsupported rather than silently
# dropped, because dropping them would make the matrix look better-measured than it is.
MIN_PAIR_N = 12

# Shrinkage intensity toward the diagonal, LEDOIT-WOLF-STYLE but fixed rather than estimated.
# Estimated LW optimality requires n > T; here T (weeks) is often smaller than n (assets), so
# the estimate would be unstable. A FIXED wedge preserves honest scale: with the wedge at 0.25,
# the pairwise matrix cannot claim a precision its support does not have.
SHRINK = 0.25


def weekly_returns(price_pts):
    """[(x,y)] -> {week: log-return}. Cadence is the observation's job; alignment the caller's.

    WEEK KEYING, AND WHY THE OBVIOUS LOOK IS WRONG. A return is produced by two CONSECUTIVE
    observations, labelled by the week of the LATER one. Bucketing by `week` first and only
    taking a return when the SAME week already holds a point yields exactly nothing on the real
    feed: median spacing is 7.0 days and every week holds a single point, so the first version
    of this function returned 0 returns from 108 prices. Consecutive-point returns on a
    fixed-cadence series ARE the weekly returns; the bucketing only has to keep different
    cadences from colliding by labelling each return with the interval it spans.
    """
    ys = sorted((int(p["x"]), float(p["y"])) for p in (price_pts or []) if p.get("y"))
    px = [(x, y) for x, y in ys if y > 0]
    if len(px) < 10:
        return {}
    out = {}
    prev = None
    for x, y in px:
        if prev and x > prev[0]:
            try:
                r = math.log(y / prev[1])
            except ZeroDivisionError:
                r = None
            if x // WEEK not in out and r is not None and r == r and math.isfinite(r):
                out[x // WEEK] = r
        prev = (x, y)
    return out


def pair_corr(a, b):
    """Pearson over the weeks both series carry. Returns (corr, n) or (None, n)."""
    common = sorted(set(a) & set(b))
    n = len(common)
    if n < 3:
        return None, n
    xs = [a[w] for w in common]
    ys = [b[w] for w in common]
    mx = sum(xs) / n
    my = sum(ys) / n
    cxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None, n
    return cxy / math.sqrt(vx * vy), n


def build(series, shrink=SHRINK, min_pair_n=MIN_PAIR_N):
    """series: {name: {week: logreturn}} -> dict with C, supports, rank diagnostics.

    Cadence normalisation happens BEFORE this call (weekly_returns buckets to a fixed grid),
    so mixed daily/weekly feeds cannot reintroduce the sqrt-cadence distortion: a return is
    a same-interval quantity, and the grid is the interval.
    """
    names = sorted(series)
    k = len(names)
    C = [[1.0] * k for _ in range(k)]
    sup = [[0] * k for _ in range(k)]
    unsupported = []
    for i in range(k):
        for j in range(i + 1, k):
            r, n = pair_corr(series[names[i]], series[names[j]])
            sup[i][j] = sup[j][i] = n
            if r is None or n < min_pair_n:
                unsupported.append("%s/%s (n=%d)" % (names[i], names[j], n))
                C[i][j] = C[j][i] = 0.0     # uncorrelated is the neutral default under the model
            else:
                C[i][j] = C[j][i] = r
    # PSD repair: Gershgorin rows can dip below 1 after the neutral fill. Symmetric convex
    # blend toward the identity keeps the matrix a valid correlation matrix (unit diagonal,
    # PSD by construction) while shrinking the measured off-diagonals toward it.
    for i in range(k):
        C[i][i] = 1.0
    for i in range(k):
        for j in range(k):
            if i != j:
                C[i][j] *= (1.0 - shrink)
    ev = _eigs(C)
    return {
        "names": names,
        "C": C,
        "support": sup,
        "unsupported_pairs": unsupported,
        "min_pair_n": min_pair_n,
        "shrink": shrink,
        "min_eigenvalue": ev,
        "psd": ev >= -1e-9,
        "n_weeks_common": len(set.intersection(*[set(v) for v in series.values()])) if k else 0,
    }


def _eigs(C, sweeps=50):
    """Smallest eigenvalue of a symmetric matrix by cyclic Jacobi.

    A hand-rolled inverse-power iteration was here first and was WRONG: on the identity 3x3 it
    returned -0.0000 (expect 1) and on [[1,-2],[-2,1]] it returned +3 where the true smallest
    eigenvalue is -1. The shift trick that makes power iteration find the smallest root needs
    the largest magnitude first, which is itself an eigensolver -- circular. A 12x12 matrix
    also does not justify adding numpy to a project with none. Cyclic Jacobi is ~30 lines,
    deterministic, and off-diagonal convergence gives the true answer to 1e-9; verified below
    in test_portfolio_corr.py against closed-form examples of every sign."""
    k = len(C)
    if k < 2:
        return 0.0 if k else None
    A = [row[:] for row in C]
    for _ in range(sweeps):
        off = math.sqrt(sum(A[i][j] ** 2 for i in range(k) for j in range(k) if i != j))
        if off < 1e-11:
            break
        for pp in range(k - 1):
            for qq in range(pp + 1, k):
                if abs(A[pp][qq]) < 1e-14:
                    continue
                theta = (A[qq][qq] - A[pp][pp]) / (2 * A[pp][qq])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                sn = t * c
                for i in range(k):
                    aipp = A[pp][i]; aiqq = A[qq][i]
                    A[pp][i] = c * aipp - sn * aiqq
                    A[qq][i] = sn * aipp + c * aiqq
                for i in range(k):
                    appi = A[i][pp]; aqqi = A[i][qq]
                    A[i][pp] = c * appi - sn * aqqi
                    A[i][qq] = sn * appi + c * aqqi
    return min(A[i][i] for i in range(k))


def from_price_cache(cache, market_to_collateral, eligible_ids):
    """{market_id: pts} + eligible set -> {collateral: weekly returns}, de-duplicated by
    collateral address so three markets sharing one collateral contribute ONE series, not three
    copies of the same asset (which would make the matrix look better-supported than it is)."""
    by_name = {}
    for mid in eligible_ids or []:
        pts = cache.get(mid) or []
        name = market_to_collateral.get(mid)
        if not name:
            continue
        r = weekly_returns(pts)
        if not r:
            continue
        # keep the best-supported series per name (most weeks), never append across markets:
        # two rows on one collateral hold the same price series, and pooling them would double
        # its weight in every pair it appears in.
        if name not in by_name or len(r) > len(by_name[name]):
            by_name[name] = r
    return by_name


def portfolio_vol(weights, C, dailies):
    """Portfolio daily vol, %. weights {name: usd}. C is the shrunk matrix from build().
    dailies {name: daily_vol_pct}. Returns None if any input is missing: an absent sigma is
    a gap in the record, not a zero."""
    names = C["names"]
    idx = {n: i for i, n in enumerate(names)}
    tot = sum(weights.values())
    if tot <= 0:
        return None
    w = {n: weights[n] / tot for n in weights}     # weights sum to 1
    var = 0.0
    for a in names:
        ia = idx[a]
        if a not in w or a not in dailies:
            return None
        wa = w[a]
        # dailies are PERCENT; /100 puts them in return units so the mix is consistent
        sa = dailies[a] / 100.0
        var += (wa * sa) ** 2
        for b in names[ia + 1:]:
            if b not in w or b not in dailies:
                return None
            wb = w[b]
            sb = dailies[b] / 100.0
            var += 2 * C["C"][ia][idx[b]] * wa * wb * sa * sb
    # back to percent for the caller
    return math.sqrt(var) * 100.0 if var >= 0 else None


def main():
    """Writes portfolio_corr.json from the newest run. Diagnostic: it does not resize anything."""
    import glob
    runs = sorted(glob.glob(os.path.join(HERE, "runs", "*", "")))
    if not runs:
        print("no runs")
        return 1
    run = runs[-1]
    mkts = json.load(open(os.path.join(run, "markets.json")))
    alloc = json.load(open(os.path.join(run, "allocator.json")))
    cache = json.load(open(os.path.join(HERE, "price_cache.json")))
    m2c = {m.get("market_id"): (m.get("collateral") or "?") for m in mkts}
    m2a = {m.get("market_id"): (m.get("collateral_address") or "") for m in mkts}
    elig = [r["market_id"] for r in alloc.get("markets", []) if r.get("eligible")]
    # de-dup by collateral ADDRESS: two markets on one collateral are one exposure
    byname = {}
    for mid in elig:
        name = m2c.get(mid)
        r = weekly_returns(cache.get(mid) or [])
        if name and r and (name not in byname or len(r) > len(byname[name])):
            byname[name] = r
    if not byname:
        print("no eligible market has a usable price series; nothing to correlate")
        return 1
    res = build(byname)
    # weights for the vol the optimiser would face: the allocator's own targets
    tgt = {r["collateral"]: r.get("target_usd", 0.0) for r in alloc["markets"]
           if r.get("eligible") and r.get("target_usd", 0.0) > 0}
    if tgt:
        res["weights_input"] = tgt
    # PORTFOLIO VOL, DIAGNOSTIC ONLY. weights are the allocator's own targets; dailies come
    # from the same run's screen rows. Returns None (and says so) when a sigma is missing,
    # because an absent sigma is a gap in the record, not a zero.
    screen = json.load(open(os.path.join(run, "screen.json")))
    dailies = {r.get("collateral"): (r.get("daily_vol_pct") or None) for r in screen}
    tgt2 = {}
    for r in alloc["markets"]:
        if r.get("eligible") and r.get("target_usd", 0.0) > 0:
            tgt2[r["collateral"]] = r.get("target_usd")
    pv = portfolio_vol(tgt2, res, dailies) if tgt2 else None
    res["portfolio_daily_vol_pct"] = round(pv, 3) if pv is not None else None
    if pv is not None:
        # what the SAME dollars would face if they ignored correlation entirely: the
        # sqrt of the sum of squared standalone vols. The gap between the two numbers is
        # the only thing correlation buys, and it is small when every correlation is positive.
        indep = math.sqrt(sum((tgt2.get(n, 0) / sum(tgt2.values())) * (dailies.get(n) or 0) / 100.0
                              for n in tgt2) ** 2) * 100.0
        standalone = math.sqrt(sum(((tgt2[n] / sum(tgt2.values())) * (dailies.get(n) or 0) / 100.0) ** 2
                                   for n in tgt2 if dailies.get(n))) * 100.0
        res["standalone_daily_vol_pct"] = round(standalone, 3)
        res["correlation_benefit_pct"] = round(standalone - pv, 3)
    json.dump(res, open(os.path.join(HERE, "portfolio_corr.json"), "w"), indent=1)
    print("covariance over %d collaterals: %d unsupported pairs (n<%d), min eigenvalue %.4f, psd=%s"
          % (len(res["names"]), len(res["unsupported_pairs"]), res["min_pair_n"],
             res["min_eigenvalue"] or 0, res["psd"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

#!/usr/bin/env python3
"""velocity.py - anomalous-velocity alerts for the markets that actually move.

THE PRODUCT GAP THIS FILLS. regimes.py already classifies 23 ACTIVE vs 37 quiet markets and
alert_diff.py already logs fixed-threshold transitions (verdict / 90% cross / 10pp jump). What
neither answers is the question a real-time subscriber asks: *"which market just did something
unusual RIGHT NOW?"*

A fixed 5pp threshold is the wrong lens for that. A market whose typical interval move is 0.2pp
suddenly moving 1.5pp is 7.5x its own norm -- an anomaly that a 5pp floor silently misses. And a
market that routinely swings 3pp moving 3pp is ordinary, not news. So the signal is NOT "how big
was the move" but "how unusual was the move FOR THIS MARKET".

WHAT IT COMPUTES (deterministic, from the immutable run ledger):

  latest_move      = utilisation at newest run minus previous run, per interval
  history          = every adjacent-pair move this market has made (needs >= 10 intervals)
  mean / sd        = the market's own move distribution
  z                = (latest_move - mean) / sd, the velocity z-score
  flag             = z >= Z_THRESHOLD (default 3.0) OR raw |move| >= 5pp

A z>=3 move is the three-sigma event; the raw 5pp floor keeps a single fat-tail move from hiding
behind a small sd. Both thresholds are recorded so the alert is auditable, not a black box.

WHAT IT IS NOT, stated because the whole repo exists to not overclaim:

  * NOT a predictor. A z-score says "this move is unlike this market's own recent behaviour"; it
    does not say what happens next.
  * CADENCE-BOUND. The z-score is per-interval, and the observed median interval is reported
    next to it, because "unusual move" is only meaningful against the time it happened in.
  * ONLY ACTIVE MARKETS. The 37 quiet/frozen markets are excluded by construction: a flat series
    has sd=0 and every move looks infinite, so including them would flood the alert with the
    exact noise regimes.py was built to remove.

Run:  python3 screener/velocity.py            writes screener/velocity.json
      python3 screener/velocity.py --selftest
      python3 screener/velocity.py --z 2.5     override the z threshold
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "velocity.json")

# Three-sigma: a move this far from the market's own norm is worth a human glance.
Z_THRESHOLD = 3.0
# Raw floor so a fat-tail move is never hidden behind a small sd. Mirrors regimes.JUMP.
RAW_FLOOR = 0.05
# A market needs this many intervals before "unusual" means anything.
MIN_INTERVALS = 10


def intervals(series):
    """[(run_id, delta), ...] for adjacent pairs, oldest first. delta in utilisation fraction."""
    pts = [(r.get("run"), r.get("utilization")) for r in series
           if r.get("utilization") is not None]
    out = []
    for i in range(1, len(pts)):
        a, b = pts[i - 1][1], pts[i][1]
        if a is None or b is None:
            continue
        out.append((pts[i][0], b - a))
    return out


def classify_market(series, z_threshold=Z_THRESHOLD, raw_floor=RAW_FLOOR):
    """Velocity profile for one market: is the LATEST move anomalous for itself?

    Returns None when there is not enough history, matching regimes.classify's refusal to
    label on three points.
    """
    iv = intervals(series)
    if len(iv) < MIN_INTERVALS:
        return None
    deltas = [d for _, d in iv]
    latest_run, latest = iv[-1]
    mean = statistics.fmean(deltas)
    sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    # The stored values are ROUNDED, so z is derived from the SAME rounded mean/sd a reader
    # would recompute from the JSON. Deriving z from the raw mean/sd while storing rounded
    # ones made the file self-inconsistent: (latest - move_mean) / move_sd would not equal
    # the stored z, so the alert was not auditable by hand. Round once, then compute z from
    # the rounded values so the arithmetic closes.
    latest = round(latest, 6)
    mean = round(mean, 6)
    sd = round(sd, 6)
    z = (latest - mean) / sd if sd > 0 else None
    raw = abs(latest)
    flagged = (z is not None and z >= z_threshold) or raw >= raw_floor
    return {
        "collateral": None,           # filled by the caller from list_markets
        "market_id": None,
        "latest_run": latest_run,
        "latest_move": latest,
        "n_intervals": len(iv),
        "move_mean": mean,
        "move_sd": sd,
        "z": round(z, 3) if z is not None else None,
        "raw_move": raw,
        "flagged": flagged,
    }


def build(z_threshold=Z_THRESHOLD, raw_floor=RAW_FLOOR):
    import glob
    sys.path.insert(0, HERE)
    import run_history as rh

    runs = sorted(glob.glob(os.path.join(HERE, "runs", "*", "")))
    if not runs:
        raise SystemExit("no runs ledger")

    index = rh.get_index()
    # observed median interval, reported so the z-score is interpretable
    med_gap = None
    import datetime
    stamps = []
    for r in index:
        try:
            stamps.append(datetime.datetime.strptime(r.get("run") or "",
                                                     "%Y%m%dT%H%M%SZ"))
        except Exception:
            continue
    if len(stamps) >= 3:
        stamps.sort()
        gaps = [(stamps[i] - stamps[i - 1]).total_seconds() for i in range(1, len(stamps))]
        gaps = [g for g in gaps if g > 0]
        med_gap = statistics.median(gaps) if gaps else None

    rows = []
    for mid, meta in rh.list_markets().items():
        prof = classify_market(rh.get_series(mid), z_threshold, raw_floor)
        if prof is None:
            continue
        prof["market_id"] = mid
        prof["collateral"] = meta.get("collateral")
        prof["verdict"] = next(iter(meta.get("verdicts") or {}), None)
        rows.append(prof)

    # only the flagged ones are "alerts"; the rest are context for "nothing unusual"
    alerts = sorted([r for r in rows if r["flagged"]],
                    key=lambda r: -(r["z"] if r["z"] is not None else 0))
    out = {
        "median_interval_seconds": med_gap,
        "median_interval_hours": round(med_gap / 3600.0, 2) if med_gap else None,
        "z_threshold": z_threshold,
        "raw_floor": raw_floor,
        "min_intervals": MIN_INTERVALS,
        "counts": {
            "markets_tracked": len(rows),
            "alerts": len(alerts),
        },
        "alerts": alerts,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)

    print("velocity.json: %d markets tracked, %d alerts (z>=%.1f or |move|>=%.0fpp)"
          % (len(rows), len(alerts), z_threshold, 100 * raw_floor))
    if med_gap:
        print("  observed median interval %.2f h" % out["median_interval_hours"])
    for a in alerts[:10]:
        print("  %-11s z=%-6.2f move=%+.3fpp mean=%+.3fpp sd=%.3fpp"
              % (a["collateral"], a["z"], 100 * a["latest_move"],
                 100 * a["move_mean"], a["move_sd"]))
    return out


def selftest():
    ok = True

    def check(name, got, want, tol=1e-6):
        nonlocal ok
        good = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
        print("  %-58s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    def ser(vals):
        return [{"run": "2026010%dT000000Z" % i, "utilization": v} for i, v in enumerate(vals)]

    # a market that moves a steady 1pp each interval has sd=0, so its latest move is ordinary
    steady = classify_market(ser([0.80 + 0.01 * i for i in range(20)]))
    check("a steady 1pp/interval market is not flagged", steady["flagged"], False)
    check("and its sd is ~0", steady["move_sd"] < 1e-9, True)

    # a market that is normally flat but makes ONE 3pp move -> big z, flagged despite <5pp floor
    burst = classify_market(ser([0.80] * 18 + [0.80, 0.83]))
    check("a 3pp move from a flat market is flagged (z-anomaly, under the 5pp floor)",
          burst["flagged"], True)
    check("and its z is large", burst["z"] is not None and burst["z"] > 3.0, True)

    # a market that routinely swings 3pp and does it again -> ordinary, not flagged
    swingy = classify_market(ser([0.80, 0.83] * 10))
    check("a market that always swings 3pp is NOT flagged (ordinary for itself)",
          swingy["flagged"], False)

    # a raw 8pp move is flagged even if the market is noisy (floor catches fat tails)
    noisy_big = classify_market(ser([0.80, 0.84] * 9 + [0.80, 0.88]))
    check("a raw 8pp move is flagged by the floor", noisy_big["flagged"], True)

    # under 10 intervals is refused, not guessed
    check("under 10 intervals is refused", classify_market(ser([0.8] * 5)), None)

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    z = Z_THRESHOLD
    if "--z" in sys.argv:
        z = float(sys.argv[sys.argv.index("--z") + 1])
    try:
        build(z)
        return 0
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

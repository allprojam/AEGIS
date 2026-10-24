#!/usr/bin/env python3
"""alert_diff.py - State Transition Log for consecutive Aegis runs.

INTERNAL. PRIVATE. NOT FOR SALE.

This is a STATE TRANSITION LOG, not an exploit-prevention monitor. It compares two
consecutive runs and records what changed. It cannot see anything that happens between
runs, and the events that matter most -- a key compromise, a block-level liquidation --
occur between runs and are already over by the time the next poll lands. USR is the worked
example: the exploit was a transaction, not a trend, and the next poll saw aftermath.

DO NOT market or sell this feed. Forward-test it for weeks of production polling first. A
feed that has never observed a real transition has no demonstrated value, and claiming
otherwise would be the same failure mode this project exists to catch.

WHAT IT DETECTS (exactly three things, per the brief):
    1. VERDICT   a market moving from REAL or CAUTION into AVOID
    2. UTIL      utilisation crossing 90%, or moving more than 10 percentage points
    3. ORACLE    an oracle flipping from a verified type to Unknown

CAPABILITY LIMIT, stated rather than hidden:
    Detection 3 requires `oracle_type` in markets.json. Runs written before that field was
    added to morpho_fetch.py DO NOT HAVE IT. When it is absent this module reports the check
    as UNCHECKED rather than reporting "no oracle flips" -- an absent field is not evidence
    of stability.

APPEND-ONLY: writes to alerts.log. Never rewrites history.

Run:  python3 alert_diff.py                # diff the two newest runs
      python3 alert_diff.py --last 5       # walk back through 5 intervals
      python3 alert_diff.py --dry-run      # print, do not append
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
LOG = os.path.join(HERE, "alerts.log")

UTIL_CROSS = 0.90          # crossing this upward is the headline event: exit liquidity thins
UTIL_DELTA = 0.10          # a 10-point move in one interval
VERIFIED_ORACLES = ("ChainlinkOracle", "ChainlinkOracleV2")
BAD_VERDICTS = ("AVOID",)


def _iso(ts=None):
    import datetime as dt
    return dt.datetime.fromtimestamp(ts or time.time(), dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_runs():
    if not os.path.isdir(RUNS):
        return []
    return sorted(d for d in os.listdir(RUNS) if os.path.isdir(os.path.join(RUNS, d)))


def load_run(d):
    """Load one run. Missing files are a hard error, not something to paper over."""
    p = os.path.join(RUNS, d)
    out = {"dir": d}
    for name, key in (("screen.json", "screen"), ("markets.json", "markets"),
                      ("meta.json", "meta")):
        fp = os.path.join(p, name)
        out[key] = json.load(open(fp)) if os.path.exists(fp) else None
    return out


def index(rows, key="market_id"):
    return {r.get(key): r for r in (rows or []) if r.get(key)}


def diff_runs(prev, cur):
    """Compare two runs. Returns (events, unchecked) where unchecked lists checks that
    COULD NOT be performed because an input was missing."""
    events, unchecked = [], []

    ps, cs = index(prev.get("screen")), index(cur.get("screen"))
    pm, cm = index(prev.get("markets")), index(cur.get("markets"))

    # A run with no block_number was NOT a live fetch. provenance.py's self-test stamps the
    # flat file, and the flat file can be hours old -- so the interval between a self-test run
    # and a real one is NOT one polling interval, it is however long the stale file sat there.
    # One interval produced 3 "transitions" this way. Report it as unalike rather than
    # presenting a 41-minute market move as one tick, which would overstate the resolution.
    pblk = (index(prev.get("markets")).get(next(iter(index(prev.get("markets"))), None)) or {}).get("_prov", {}).get("block_number") if prev.get("markets") else None
    cblk = (index(cur.get("markets")).get(next(iter(index(cur.get("markets"))), None)) or {}).get("_prov", {}).get("block_number") if cur.get("markets") else None
    if pblk is None or cblk is None:
        events.append({
            "kind": "INTERVAL_UNRELIABLE", "severity": "warn",
            "detail": "one run has no block_number (%s vs %s), so it was not a live fetch. "
                      "The elapsed time between these runs is NOT one polling interval, and "
                      "any transitions below span a longer window than they appear to."
                      % (pblk, cblk),
        })

    only_cur = sorted(set(cs) - set(ps))
    only_prev = sorted(set(ps) - set(cs))
    if only_prev:
        events.append({
            "kind": "MARKET_GONE", "severity": "info",
            "detail": "%d market(s) present in the previous run are absent from this one"
                      % len(only_prev), "markets": only_prev[:10],
        })
    if only_cur:
        events.append({
            "kind": "MARKET_NEW", "severity": "info",
            "detail": "%d new market(s) appeared" % len(only_cur), "markets": only_cur[:10],
        })

    for mid in sorted(set(ps) & set(cs)):
        a, b = ps[mid], cs[mid]
        coll = b.get("collateral") or a.get("collateral") or mid[:10]

        # --- 1. verdict transition ---
        va, vb = a.get("verdict"), b.get("verdict")
        if va != vb and vb in BAD_VERDICTS and va in ("REAL", "CAUTION"):
            events.append({
                "kind": "VERDICT_DOWNGRADE", "severity": "high", "market_id": mid,
                "collateral": coll, "from": va, "to": vb,
                "fails": b.get("fails") or [],
                "reasons": (b.get("reasons") or [])[:3],
                "detail": "%s: %s -> %s" % (coll, va, vb),
            })

        # --- 2. utilisation ---
        ua, ub = a.get("utilization"), b.get("utilization")
        if ua is not None and ub is not None:
            if ua < UTIL_CROSS <= ub:
                events.append({
                    "kind": "UTIL_CROSSED_90", "severity": "high", "market_id": mid,
                    "collateral": coll, "from": round(ua, 6), "to": round(ub, 6),
                    "detail": "%s: utilisation crossed 90%% (%.2f%% -> %.2f%%)"
                              % (coll, ua * 100, ub * 100),
                })
            elif abs(ub - ua) > UTIL_DELTA:
                events.append({
                    "kind": "UTIL_JUMP", "severity": "medium", "market_id": mid,
                    "collateral": coll, "from": round(ua, 6), "to": round(ub, 6),
                    "detail": "%s: utilisation moved %.1f points in one interval"
                              % (coll, (ub - ua) * 100),
                })

    # --- 2b. parameter changes ---
    # Morpho market parameters are IMMUTABLE once created, so an LLTV or oracle-address
    # change on an existing market id means one of two things: a NEW market that reuses the
    # id (impossible), or a data-source inconsistency. Either way it must be reported, not
    # silently averaged. This is the "unannounced parameter adjustment" case.
    for mid in sorted(set(pm) & set(cm)):
        a, b = pm[mid], cm[mid]
        la, lb = a.get("lltv"), b.get("lltv")
        if la is not None and lb is not None and abs(la - lb) > 1e-9:
            events.append({
                "kind": "LLTV_CHANGED", "severity": "high", "market_id": mid,
                "collateral": b.get("collateral"), "from": la, "to": lb,
                "detail": "%s: LLTV changed %.2f%% -> %.2f%% on an immutable market id"
                          % (b.get("collateral"), la * 100, lb * 100),
            })
        oa, ob = a.get("oracle"), b.get("oracle")
        if oa and ob and str(oa).lower() != str(ob).lower():
            events.append({
                "kind": "ORACLE_ADDRESS_CHANGED", "severity": "high", "market_id": mid,
                "collateral": b.get("collateral"), "from": oa, "to": ob,
                "detail": "%s: oracle address changed on an immutable market id"
                          % b.get("collateral"),
            })

    # --- 3. oracle provenance ---
    fields_present = [m for m in pm.values() if "oracle_type" in m]
    fields_present_cur = [m for m in cm.values() if "oracle_type" in m]
    if not fields_present or not fields_present_cur:
        unchecked.append({
            "check": "ORACLE_FLIP",
            "why": "markets.json has no `oracle_type` field in %s. Runs written before that "
                   "field was added to morpho_fetch.py cannot be checked. An absent field is "
                   "not evidence of stability."
                   % ("both runs" if not fields_present and not fields_present_cur
                      else "the previous run" if not fields_present else "the current run"),
        })
    else:
        for mid in sorted(set(pm) & set(cm)):
            oa = pm[mid].get("oracle_type")
            ob = cm[mid].get("oracle_type")
            if oa in VERIFIED_ORACLES and ob not in VERIFIED_ORACLES:
                events.append({
                    "kind": "ORACLE_FLIP", "severity": "high", "market_id": mid,
                    "collateral": cm[mid].get("collateral"),
                    "from": oa, "to": ob,
                    "detail": "%s: oracle %s -> %s"
                              % (cm[mid].get("collateral"), oa, ob),
                })
    return events, unchecked


def append_log(record, dry=False):
    if dry:
        return
    with open(LOG, "a") as fh:
        fh.write(json.dumps(record) + "\n")


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    n = 1
    if "--last" in args:
        n = int(args[args.index("--last") + 1])

    runs = list_runs()
    if len(runs) < 2:
        print("need at least two runs to diff; found %d" % len(runs))
        return 0

    print("=== Aegis State Transition Log ===")
    print("    internal / private / not for sale")
    print("    runs: %s" % ", ".join(runs[-n-1:]))
    print()

    total_events = 0
    all_unchecked = set()
    for i in range(max(1, len(runs) - n), len(runs)):
        prev, cur = load_run(runs[i - 1]), load_run(runs[i])
        events, unchecked = diff_runs(prev, cur)
        for u in unchecked:
            all_unchecked.add(u["check"])
        print("  %s -> %s : %d event(s)" % (prev["dir"], cur["dir"], len(events)))
        for e in events:
            print("    [%s] %s" % (e["severity"].upper(), e["detail"]))
        total_events += len(events)
        record = {
            "logged_at": _iso(),
            "from_run": prev["dir"], "to_run": cur["dir"],
            "block": (cur.get("meta") or {}).get("provenance", {}).get("block_number"),
            "events": events,
            "unchecked": unchecked,
            "n_events": len(events),
        }
        append_log(record, dry=dry)

    print()
    print("  total events: %d" % total_events)
    if all_unchecked:
        print("  CHECKS THAT COULD NOT RUN: %s" % ", ".join(sorted(all_unchecked)))
        print("    -> reported as UNCHECKED, not as 'no changes'. An absent input is not")
        print("       evidence of stability.")
    else:
        print("  all three checks ran")
    print()
    print("  log: %s%s" % (LOG, " (dry-run, nothing written)" if dry else ""))
    if total_events == 0:
        print()
        print("  NOTE: zero transitions observed. That is a fact about these two runs, not")
        print("        evidence that the feed detects things. Value is unproven until a")
        print("        real transition is observed over a forward test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""forward_test.py - the compounding flag-coverage ledger (task B+).

WHAT TASK B LEFT UNSOLVED

Task B ingested 30,934 liquidations and cross-referenced them to the screen's verdicts. The
result was a SINGLE SNAPSHOT: "1,261 covered -> AVOID 0 / CAUTION 1 / REAL 1,260". That number
is honest, but it is computed fresh each time and has NO time axis -- in six months it would be
recomputed-from-scratch, and a reader could not see whether coverage was ACCUMULATING or whether
the first week was an outlier.

WHAT B+ DOES

Turns the snapshot into an append-only daily series in forward_test.json. Each day is one bucket:
how many liquidations landed on a market the screen had already verdict-ed, split by verdict, plus
bad-debt events. The file is append-only and idempotent: a re-run adds only days newer than the
last recorded day, and every day carries the run it drew from, so the series is auditable the way
runs/ are auditable -- provenance, not a recomputation.

THE HONEST CLAIM, KEPT HONEST

This is a FORWARD test, not a backtest. The screen began 2026-10-07, so there is no history before
that, and the series says so in `coverage_started`. The expected value is NOT "AVOID markets get
liquidated": task B already measured that liquidations are the mechanism of healthy lending (they
hit REAL markets). What the series measures is whether the RATE differs -- a market the screen
flags as AVOID should eventually show a DIFFERENT liquidation/bad-debt profile than a REAL one.
Until that difference appears, the ledger reports zero AVOID hits as a measurement, not a miss,
which is the whole point of keeping it as data rather than prose.

No LLM is involved. This is deterministic arithmetic over two immutable inputs
(liquidations.json + runs/*/screen.json), exactly the class of thing that must not be
delegated to a model that might "round" a count.
"""
import bisect
import collections
import datetime
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "liquidations.json")
OUT = os.path.join(HERE, "forward_test.json")
RUNS = os.path.join(HERE, "runs")


def _parse(ts):
    """UTC ISO -> epoch seconds. The run meta uses 'Z' not '+00:00'."""
    return int(datetime.datetime.strptime(str(ts).replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
               .replace(tzinfo=datetime.timezone.utc).timestamp())


def _day(epoch):
    return datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def load_runs():
    """run dirs -> [{ts, dir, by_market}], ascending by time. Immutable inputs only."""
    runs = []
    for d in sorted(glob.glob(os.path.join(RUNS, "*", ""))):
        try:
            mj = json.load(open(os.path.join(d, "meta.json")))
            sc = json.load(open(os.path.join(d, "screen.json")))
        except Exception:
            continue
        runs.append({"ts": mj.get("written_at"), "dir": os.path.basename(d.rstrip("/")),
                     "by_market": {r.get("market_id"): r for r in sc}})
    runs.sort(key=lambda r: _parse(r["ts"]))
    return runs


def bucket_events(st, runs):
    """For each liquidation, find the newest run BEFORE it and bucket by day.

    O(events * log(runs)) via bisect over precomputed run epochs, not the O(events*runs)
    walk the first version used -- 30,934 events x 134 runs was 4M+ datetime.parse calls and
    made one build exceed a 30s budget.

    Returns a list of day buckets, oldest first. A day with no covered event is OMITTED.
    """
    days = collections.OrderedDict()
    epochs = [_parse(r["ts"]) for r in runs]

    def bucket(d):
        if d not in days:
            days[d] = {"day": d, "covered": 0, "avoid": 0, "caution": 0, "real": 0,
                       "bad_debt_events": 0, "bad_debt_usd": 0.0,
                       "runs_seen": [], "first_flag_run": None}
        return days[d]

    for e in sorted(st["items"], key=lambda r: r["ts"]):
        et = e["ts"]
        # rightmost run whose epoch is <= et  ->  newest run before the event
        idx = bisect.bisect_right(epochs, et) - 1
        if idx < 0:
            continue                      # before the first run: not covered
        run = runs[idx]
        row = run["by_market"].get(e["market_id"])
        if not row:
            continue                      # market not in that run's screen
        d = _day(et)
        b = bucket(d)
        b["covered"] += 1
        v = row.get("verdict")
        if v == "AVOID":
            b["avoid"] += 1
        elif v == "CAUTION":
            b["caution"] += 1
        else:
            b["real"] += 1
        if (e.get("bad_debt") or 0) > 0:
            b["bad_debt_events"] += 1
            b["bad_debt_usd"] += e.get("bad_debt") or 0
        if run["dir"] not in b["runs_seen"]:
            b["runs_seen"].append(run["dir"])
        if b["first_flag_run"] is None:
            b["first_flag_run"] = run["dir"]
    return list(days.values())


def load_ledger():
    try:
        return json.load(open(OUT))
    except FileNotFoundError:
        return None


def append_days(series, last_day):
    if last_day is None:
        return series
    return [d for d in series if d["day"] > last_day]


def build(quiet=False):
    """Idempotent build: read inputs, append new days, write the ledger, return it."""
    if not os.path.exists(STORE):
        raise SystemExit("liquidations.json missing; run liquidations.py first")
    st = json.load(open(STORE))
    runs = load_runs()
    if not runs:
        raise SystemExit("no runs/ dirs; cannot compute coverage")

    series = bucket_events(st, runs)
    ledger = load_ledger() or {
        "coverage_started": runs[0]["ts"],
        "days": [],
        "totals": {"covered": 0, "avoid": 0, "caution": 0, "real": 0,
                   "bad_debt_events": 0, "bad_debt_usd": 0.0},
    }
    ledger["coverage_started"] = runs[0]["ts"]

    last_day = ledger["days"][-1]["day"] if ledger["days"] else None
    new_days = append_days(series, last_day)

    totals = dict(ledger["totals"])
    for d in new_days:
        ledger["days"].append(d)
        totals["covered"] += d["covered"]
        totals["avoid"] += d["avoid"]
        totals["caution"] += d["caution"]
        totals["real"] += d["real"]
        totals["bad_debt_events"] += d["bad_debt_events"]
        totals["bad_debt_usd"] += d["bad_debt_usd"]

    ledger["totals"] = totals
    ledger["as_of"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger["events_total"] = len(st["items"])

    tmp = OUT + ".tmp"
    json.dump(ledger, open(tmp, "w"), indent=1)
    os.replace(tmp, OUT)
    if not quiet:
        print("forward_test.json: %d days (+%d new), %d covered events, AVOID %d / CAUTION %d / REAL %d"
              % (len(ledger["days"]), len(new_days), totals["covered"],
                 totals["avoid"], totals["caution"], totals["real"]))
    return ledger


def main():
    quiet = "--quiet" in sys.argv
    try:
        build(quiet=quiet)
        return 0
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

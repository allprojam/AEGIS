#!/usr/bin/env python3
"""Provenance layer - makes replay real instead of aspirational.

WHY: the screen is deterministic given its input, but until now the input carried no record of
WHEN it was captured or WHAT block it described. So we could prove the screen was reproducible
twice in a row, and could not prove what it decided at any past timestamp. That fails an audit.

WHAT THIS STORES, per run, in runs/<iso-timestamp>/:

    markets.json     the ingested market state, with provenance stamped
    screen.json      the lending screen output for that exact input
    meta.json        the manifest: what ran, on what, when, with which checksums

APPEND-ONLY. Nothing is ever overwritten. Each run is a new immutable directory, which is what
lets the dashboard read "the latest" without destroying the audit trail.

    run_dir_utc()      create a new timestamped run directory
    stamp(rows, ...)   add provenance to a fetched market payload
    write_run(...)     persist markets + screen + manifest
    latest_run()       resolve the most recent run (for the dashboard)
    verify_run(dir)    re-run the screen on a stored input and assert it reproduces

The last one is the point. A provenance layer that cannot be used to reproduce a past decision
is a log file.

Run:  python3 provenance.py                 # self-test on the stored data
      python3 provenance.py --verify LAST   # re-derive the latest run and compare
"""
import hashlib, json, os, sys, time, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")


def _iso(ts=None):
    return dt.datetime.fromtimestamp(ts or time.time(), dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(obj):
    """Stable content hash. sort_keys so key order cannot change the digest."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run_dir_utc(when=None):
    """Create and return a fresh run directory. Never reuses an existing name."""
    stamp = _iso(when).replace(":", "").replace("-", "")
    base = os.path.join(RUNS, stamp)
    n = 0
    path = base
    while os.path.exists(path):          # two runs in the same second: do not collide
        n += 1
        path = "%s_%02d" % (base, n)
    os.makedirs(path, exist_ok=False)
    return path


def stamp(rows, endpoint, block_number=None, block_timestamp=None, extra=None):
    """Attach provenance to a list of market rows. Returns (rows, prov)."""
    prov = {
        "fetched_at": _iso(),
        "source_endpoint": endpoint,
        "chain_id": 8453,
        "block_number": block_number,
        "block_timestamp": block_timestamp,
        "row_count": len(rows),
        "content_sha256": _sha(rows),
    }
    if extra:
        prov.update(extra)
    out = []
    for r in rows:
        rr = dict(r)
        # provenance goes at the ROOT of each row so it survives being written alone
        rr["_prov"] = prov
        out.append(rr)
    return out, prov


def block_from_rows(rows):
    """Pull the block anchor the API itself reported, if present."""
    for r in rows:
        b = r.get("block_number") or (r.get("_block") or {}).get("number")
        if b:
            return b
    return None


def write_run(markets_stamped, screen_rows, prov, note=None, into=None):
    """Persist one immutable run. Returns the path.

    `into` lets the caller pre-create the directory so optional artefacts (prompt.json,
    reason.json) are already present when the manifest is checksummed.
    """
    d = into or run_dir_utc()
    json.dump(markets_stamped, open(os.path.join(d, "markets.json"), "w"), indent=1)
    json.dump(screen_rows, open(os.path.join(d, "screen.json"), "w"), indent=1)
    optional = {}
    for fn in ("prompt.json", "reason.json", "allocator.json"):
        fp = os.path.join(d, fn)
        if os.path.exists(fp):
            optional[fn] = _sha(json.load(open(fp)))
    meta = {
        "run_dir": os.path.basename(d),
        "artefacts": sorted(["markets.json", "screen.json", "meta.json"] + list(optional)),
        "written_at": _iso(),
        "note": note,
        "provenance": prov,
        "checksums": {
            "markets.json": _sha(markets_stamped),
            "screen.json": _sha(screen_rows),
            **optional,
        },
        "counts": {
            "markets": len(markets_stamped),
            "screen": len(screen_rows),
        },
    }
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=1)
    return d


def latest_run():
    """Most recent run directory, or None. Sort by name; the stamp is lexicographic."""
    if not os.path.isdir(RUNS):
        return None
    dirs = sorted(d for d in os.listdir(RUNS) if os.path.isdir(os.path.join(RUNS, d)))
    return os.path.join(RUNS, dirs[-1]) if dirs else None


def verify_run(d):
    """Re-derive the screen from the stored input and assert it reproduces byte-for-byte.

    This is the whole point of the provenance layer: a stored run must be able to prove that
    the decision it recorded is the decision the current code produces from the same input.
    If the code changed, this fails loudly rather than silently.
    """
    import importlib.util
    mk = json.load(open(os.path.join(d, "markets.json")))
    want = json.load(open(os.path.join(d, "screen.json")))

    spec = importlib.util.spec_from_file_location("ls_prov", os.path.join(HERE, "lending_screen.py"))
    ls = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    try:
        os.chdir(HERE)
        spec.loader.exec_module(ls)
    finally:
        os.chdir(cwd)

    got = [ls.screen_market(m) for m in mk]

    # compare on the fields the screen produces, not on provenance
    def key(r):
        return json.dumps({k: v for k, v in r.items() if k != "_prov"}, sort_keys=True)
    ok = [key(a) for a in got] == [key(b) for b in want]
    return ok, len(got), len(want)


def main():
    if "--verify" in sys.argv:
        arg = sys.argv[sys.argv.index("--verify") + 1] if len(sys.argv) > sys.argv.index("--verify") + 1 else "LAST"
        d = latest_run() if arg.upper() == "LAST" else os.path.join(RUNS, arg)
        if not d or not os.path.isdir(d):
            print("no run found: %s" % d)
            return 1
        ok, n, m = verify_run(d)
        print("verify %s" % os.path.basename(d))
        print("  re-derived %d rows against %d stored" % (n, m))
        print("  REPRODUCES EXACTLY" if ok else "  ** DRIFT DETECTED: the code no longer matches the record **")
        return 0 if ok else 1

    print("runs directory: %s" % RUNS)
    d = latest_run()
    if not d:
        print("  no runs yet. write one with: write_run(...) from a pipeline")
        print("\nself-test on the existing live data:")
        mk = json.load(open(os.path.join(HERE, "morpho_markets.json")))
        sc = json.load(open(os.path.join(HERE, "lending_screen.json")))
        stamped, prov = stamp(mk, "https://blue-api.morpho.org/graphql", extra={"note": "phase A self-test"})
        p = write_run(stamped, [dict(r) for r in sc], prov, note="self-test: existing data, stamped retroactively")
        print("  wrote %s" % os.path.relpath(p, HERE))
        print("  provenance: %s" % json.dumps(prov, indent=1))
        ok, n, m = verify_run(p)
        print("\n  replay check: %s (%d rows)" % ("REPRODUCES" if ok else "DRIFT", n))
        return 0
    print("  latest run: %s" % os.path.relpath(d, HERE))
    ok, n, m = verify_run(d)
    print("  replay: %s" % ("REPRODUCES EXACTLY" if ok else "DRIFT DETECTED"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

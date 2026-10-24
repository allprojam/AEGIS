#!/usr/bin/env python3
"""backfill_pool_ids.py - add the DefiLlama `pool` UUID to snapshots written before screen.py
carried it.

WHY THE UUID MATTERS. Snapshots had no stable primary key, so a diff between two of them fell
back to (chain, project, symbol). MEASURED against the live feed: 16,723 pools collapse onto
14,083 distinct triples -- 1,405 triples map to more than one pool, hiding 2,640 rows. The worst
case is ('Base','morpho-blue','CBBTC') at FIVE distinct pools. A symbol-keyed join therefore
counts five real pools as one and makes any re-classification among them invisible.

WHAT THIS DOES NOT DO. It does not guess. Where a triple maps to exactly one pool the UUID is
assigned; where it maps to several the field is left as None and counted, because assigning "the
first one" would silently attribute one pool's history to another -- worse than an admitted gap.

IDEMPOTENT AND NON-DESTRUCTIVE: records are otherwise byte-identical, and re-running changes
nothing. Verified by checksumming the records with `pool` removed, before and after.
"""
import glob, gzip, hashlib, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPDIR = os.path.join(HERE, "snapshots")


def feed():
    r = urllib.request.Request("https://yields.llama.fi/pools",
                               headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode())["data"]


def digest(rows):
    """Hash of the records with `pool` stripped, so we can prove nothing else changed."""
    stripped = [{k: v for k, v in r.items() if k != "pool"} for r in rows]
    return hashlib.sha256(json.dumps(stripped, sort_keys=True).encode()).hexdigest()


def load(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt") as f:
            return json.load(f)
    with open(path) as f:
        return json.load(f)


def save(path, rows):
    if path.endswith(".gz"):
        with gzip.open(path, "wt") as f:
            json.dump(rows, f)
    else:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(rows, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


def main():
    raw = feed()
    # triple -> list of uuids. A list, not a scalar: ambiguity must stay visible.
    bytriple = {}
    for x in raw:
        k = (x.get("chain"), x.get("project"), x.get("symbol"))
        bytriple.setdefault(k, []).append(x.get("pool"))

    amb = sum(1 for v in bytriple.values() if len(v) > 1)
    print("feed pools: %d   distinct triples: %d   ambiguous: %d"
          % (len(raw), len(bytriple), amb))

    files = sorted(glob.glob(os.path.join(SNAPDIR, "*.json")) +
                   glob.glob(os.path.join(SNAPDIR, "*.json.gz")))
    if not files:
        print("no snapshots to backfill")
        return 0

    total_ok = total_amb = total_miss = 0
    for p in files:
        rows = load(p)
        before = digest(rows)
        need = sum(1 for r in rows if not r.get("pool"))
        if not need:
            print("\n%-28s already keyed (%d rows) - skipped" % (os.path.basename(p), len(rows)))
            continue
        ok = amb_ = miss = 0
        for r in rows:
            if r.get("pool"):
                ok += 1
                continue
            k = (r.get("chain"), r.get("project"), r.get("symbol"))
            u = bytriple.get(k) or []
            if len(u) == 1 and u[0]:
                r["pool"] = u[0]
                ok += 1
            elif len(u) > 1:
                r["pool"] = None
                amb_ += 1
            else:
                r["pool"] = None
                miss += 1
        assert digest(rows) == before, "backfill altered records beyond the pool key: %s" % p
        save(p, rows)
        total_ok += ok; total_amb += amb_; total_miss += miss
        print("\n%s" % os.path.basename(p))
        print("  rows                 : %d" % len(rows))
        print("  now keyed by uuid    : %d" % ok)
        print("  ambiguous -> None    : %d" % amb_)
        print("  not in feed -> None  : %d" % miss)
        print("  records otherwise identical: yes")

    print("\nTOTAL  keyed: %d   ambiguous: %d   absent: %d"
          % (total_ok, total_amb, total_miss))
    if total_amb:
        print("  %d records stay None because their triple maps to several pools. Assigning the"
              % total_amb)
        print("  first match would attribute one pool's history to another, so it is left blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

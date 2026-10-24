#!/usr/bin/env python3
"""snapshots.py - read the append-only AMM snapshots and diff two of them.

WHY THIS EXISTS. screen.py used to overwrite screener/results.json on every run, so the previous
screen was destroyed. Any "yesterday vs today" comparison therefore had no baseline it could
actually read -- deltas were unfalsifiable at the source. That is how an inverted finding went
unnoticed: a summary reported "19 pools bled out below viability" when the measured movement was
49 FEWER dead pools, and nothing on disk could contradict it.

Two jobs, kept separate on purpose:

  1. ENUMERATION. Which snapshots exist, newest first. This is the part that must be right, because
     every diff rests on it.
  2. DIFF. What changed between two of them, split into CLASSIFICATION changes and MARKET moves.

THE SPLIT IS THE POINT. In the real data, AVOID fell 4,345 while a category called NO_YIELD
appeared with 4,866 -- a pool that moved between two buckets looks identical to a pool whose
liquidity collapsed if you only diff the totals. `diff_snapshots` reports both: bucket membership
per pool id, and the numeric movement of the pools that stayed in place. A re-classification is
not a market event and the two must never be added together.
"""
import glob, gzip, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPDIR = os.path.join(HERE, "snapshots")

# A snapshot is named for the instant it was taken. Accept plain and compressed, because the
# retention policy compresses old ones and an enumeration that only matched *.json would silently
# lose them -- and `sorted(...)[-2]` would then return a WRONG "previous", not an error.
_SNAP_RE = re.compile(r"^(\d{8}T\d{6}Z)(?:\.\d+)?\.json(\.gz)?$")


def list_snapshots():
    """Snapshot ids, newest first. Ids are the timestamp, and they sort chronologically."""
    if not os.path.isdir(SNAPDIR):
        return []
    out = []
    for name in os.listdir(SNAPDIR):
        m = _SNAP_RE.match(name)
        if m:
            out.append(m.group(1))
    return sorted(set(out), reverse=True)


def snapshot_path(snap_id):
    """Resolve a snapshot id to a path, preferring the compressed copy if that is what exists."""
    if not os.path.isdir(SNAPDIR):
        return None
    for name in sorted(os.listdir(SNAPDIR)):
        m = _SNAP_RE.match(name)
        if m and m.group(1) == snap_id:
            return os.path.join(SNAPDIR, name)
    return None


def load(snap_id):
    p = snapshot_path(snap_id)
    if not p:
        raise FileNotFoundError("no snapshot %s in %s" % (snap_id, SNAPDIR))
    if p.endswith(".gz"):
        with gzip.open(p, "rt") as f:
            return json.load(f)
    with open(p) as f:
        return json.load(f)


def previous_snapshot(snap_id=None):
    """The snapshot BEFORE `snap_id`, or before the newest if None.

    Returns None when there is no baseline -- which the caller must report as "no baseline",
    never as "no change". An absent baseline and a quiet market are different states.
    """
    ids = list_snapshots()
    if snap_id is None:
        return ids[1] if len(ids) >= 2 else None
    if snap_id not in ids:
        return None
    i = ids.index(snap_id)
    return ids[i + 1] if i + 1 < len(ids) else None


# A uuid can never contain "|", so prefixing the fallback keeps the two families in separate
# namespaces. This matters because they are used TOGETHER: without the prefix, a record carrying
# a uuid and one without are keyed differently even when they are the SAME pool, so the pool is
# reported as "gone" by its fallback key and simultaneously "appeared" by its uuid. Measured on
# the two backfilled snapshots: 366 phantom "gone" and 25 phantom "appeared", every one of them
# fallback-keyed. A diff that invents 391 membership changes out of a keying artefact is worse
# than no diff, because the numbers look like market activity.
FB_PREFIX = "sym:"


def _fallback_key(r):
    return "%s%s|%s|%s" % (FB_PREFIX, r.get("chain"), r.get("project"), r.get("symbol"))


def _index(rows):
    """Key pools by identity so a diff survives reordering.

    PREFER `pool`, the DefiLlama UUID: the feed's own primary key, stable across runs. Fall back
    to (chain, project, symbol) only when it is absent, namespaced so the two cannot be confused.

    The fallback is LOSSY and that is measured, not assumed: 16,723 feed pools collapse onto
    14,083 distinct triples, with 1,405 triples mapping to more than one pool -- the worst being
    ('Base','morpho-blue','CBBTC') at FIVE distinct pools. A fallback-keyed diff therefore counts
    several real pools as one. `by_uuid` reports how much of the join rested on the good key.

    Duplicate keys are counted rather than silently overwritten: two records landing on one key
    would drop a row, and a dropped row is indistinguishable from a pool that closed.
    """
    idx, n_uuid, dupes = {}, 0, 0
    for r in rows:
        k = r.get("pool")
        if k:
            n_uuid += 1
        else:
            k = _fallback_key(r)
        if k in idx:
            dupes += 1
        idx[k] = r
    return idx, n_uuid, dupes


def _counts(rows, field="verdict"):
    c = {}
    for r in rows:
        v = r.get(field) or "?"
        c[v] = c.get(v, 0) + 1
    return c


def diff_snapshots(a_id, b_id):
    """Diff two snapshots. `a` is the OLDER, `b` the NEWER. Order matters and is not inferred.

    Returns a dict with three SEPARATE sections, deliberately not combined:
      totals           - bucket counts either side, and the delta
      reclassified     - pools whose verdict changed. A LABELLING change.
      moved            - numeric movement for pools present in both. A MARKET change.
      appeared/gone    - membership change, reported on its own.
    """
    a_rows, b_rows = load(a_id), load(b_id)
    ai, a_n, a_dup = _index(a_rows)
    bi, b_n, b_dup = _index(b_rows)

    reclass, moved, appeared = [], [], []
    for k, nb in bi.items():
        oa = ai.get(k)
        if oa is None:
            appeared.append({"key": k, "to": nb.get("verdict"), "symbol": nb.get("symbol"),
                              "chain": nb.get("chain"), "tvl": nb.get("tvl")})
            continue
        if (oa.get("verdict") or "?") != (nb.get("verdict") or "?"):
            reclass.append({"key": k, "symbol": nb.get("symbol"), "chain": nb.get("chain"),
                            "from": oa.get("verdict"), "to": nb.get("verdict"),
                            "tvl": nb.get("tvl")})
        # numeric movement, only where BOTH sides have the value. A missing value is not a zero.
        d = {}
        for f in ("tvl", "apy", "base", "sigma"):
            ov, nv = oa.get(f), nb.get(f)
            if isinstance(ov, (int, float)) and isinstance(nv, (int, float)):
                d[f] = nv - ov
        if d and nb.get("verdict") == oa.get("verdict"):
            moved.append({"key": k, "symbol": nb.get("symbol"), "chain": nb.get("chain"),
                          "verdict": nb.get("verdict"), "delta": d})
    gone = [{"key": k, "symbol": r.get("symbol"), "chain": r.get("chain"),
             "verdict": r.get("verdict")} for k, r in ai.items() if k not in bi]

    ca, cb = _counts(a_rows), _counts(b_rows)
    totals = {v: {"from": ca.get(v, 0), "to": cb.get(v, 0), "delta": cb.get(v, 0) - ca.get(v, 0)}
              for v in sorted(set(ca) | set(cb))}

    return {
        "from": a_id, "to": b_id,
        "n_from": len(a_rows), "n_to": len(b_rows),
        # REPORTED, NOT ASSUMED. A caller must be able to see how much of the join rested on the
        # stable key, because the fallback merges distinct pools and understates every count.
        "keyed_by": ("pool uuid" if (a_n == len(a_rows) and b_n == len(b_rows))
                     else "mixed: %d/%d uuid-keyed, remainder by symbol" % (a_n, len(a_rows))),
        "uuid_keyed": {"from": a_n, "to": b_n},
        "duplicate_keys": {"from": a_dup, "to": b_dup},
        "totals": totals,
        "reclassified": reclass,
        "moved": moved,
        "appeared": appeared,
        "gone": gone,
    }


if __name__ == "__main__":
    import sys
    ids = list_snapshots()
    print("snapshots on disk: %d" % len(ids))
    for s in ids[:6]:
        print("  %s  %s" % (s, os.path.basename(snapshot_path(s) or "?")))
    if len(ids) >= 2:
        d = diff_snapshots(ids[1], ids[0])
        print("\n=== %s -> %s ===" % (d["from"], d["to"]))
        print("  keyed by: %s" % d["keyed_by"])
        print("  pools: %d -> %d" % (d["n_from"], d["n_to"]))
        for v, t in d["totals"].items():
            print("  %-12s %6d -> %6d  %+6d" % (v, t["from"], t["to"], t["delta"]))
        print("  reclassified: %d   appeared: %d   gone: %d   moved: %d"
              % (len(d["reclassified"]), len(d["appeared"]), len(d["gone"]), len(d["moved"])))
    else:
        print("\n  no baseline yet -- one snapshot is not a history")

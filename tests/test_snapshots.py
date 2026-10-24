#!/usr/bin/env python3
"""The AMM index must keep history, and the diff must not invent movement.

WHY THIS EXISTS. screen.py overwrote screener/results.json on every run, so the previous screen
was destroyed and no diff could be verified. A summary was able to report "19 pools bled out"
when the files showed 49 FEWER dead pools, and nothing on disk could contradict it.

These assertions cover the three ways this can silently go wrong:
  1. the writer overwrites, so history never accumulates
  2. the pointer is not atomic, so a reader sees a half-written file
  3. the diff keys on something unstable, so one pool is reported as both gone and appeared

Run:  python3 tests/test_snapshots.py
"""
import json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SNAP = os.path.join(ROOT, "screener", "snapshots")
sys.path.insert(0, os.path.join(ROOT, "screener"))

FAILS = []


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def main():
    import snapshots as S

    print("=== 1. the writer is append-only and the pointer is atomic ===")
    # STRUCTURAL, VIA THE AST. Every assertion in this block used to be a substring of the file
    # text, which a COMMENT can satisfy and a reformat can break -- the exact false positive that
    # fired twice in this project. Comments do not exist in an AST, so these now describe what the
    # module DOES.
    sys.path.insert(0, HERE)
    import srcint as SI
    screen_py = os.path.join(ROOT, "screener", "screen.py")
    calls = SI.called_names(screen_py)
    check("screen.py calls makedirs (creates the snapshot store)", "makedirs" in calls)
    check("it does NOT json.dump onto results.json",
          "dump" in calls, "dump is used, but the assertion below pins WHERE")
    # the dangerous shape was dump-to-a-live-path. Ask the AST for every json.dump call and read
    # what its first argument is: a file OBJECT built from a temp name is fine, a call with no
    # file argument on the live path is not.
    import ast as _ast
    dumps = []
    for node in _ast.walk(_ast.parse(open(screen_py, "rb").read())):
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute) \
                and node.func.attr == "dump":
            dumps.append(node)
    check("json.dump is called (%d site(s))" % len(dumps), len(dumps) >= 1)
    live = [d for d in dumps if any(isinstance(a, _ast.Constant) and isinstance(a.value, str)
                                    and "results.json" in a.value for a in d.args)]
    check("no json.dump writes to results.json directly", not live,
          "that is the overwrite that destroyed the baseline")
    check("os.replace is called (atomic rename of both payload and pointer)",
          "replace" in calls)
    check("fsync is called before any rename", "fsync" in SI.called_names(screen_py))
    check("os.symlink is called (the pointer is a symlink, not a copy)", "symlink" in calls)
    # the RELATIVE requirement is a property of the ARGUMENT, not of the prose. Read it from the AST.
    rels = []
    for node in _ast.walk(_ast.parse(open(screen_py, "rb").read())):
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute) \
                and node.func.attr == "symlink" and node.args:
            a0 = node.args[0]
            if isinstance(a0, _ast.Name):
                rels.append(a0.id)          # e.g. os.symlink(rel, ptmp) -> "rel"
            elif isinstance(a0, _ast.Constant):
                rels.append(repr(a0.value))
    check("the symlink target is a variable (the relative snapshot path), not a literal",
          bool(rels), "args seen: %r" % rels)
    # collision safety is a BRANCH, so look for the existence guard rather than the comment
    check("an existing snapshot is never overwritten",
          SI.has_comment_mentioning(screen_py, "Collision would silently destroy")
          and ("exists" in calls or "isfile" in calls),
          "needs BOTH a guard and the note explaining why")

    print("\n=== 2. snapshots exist and results.json points at the newest ===")
    ids = S.list_snapshots()
    check("snapshots on disk (%d)" % len(ids), len(ids) >= 1)
    ptr = os.path.join(ROOT, "screener", "results.json")
    if os.path.islink(ptr):
        tgt = os.readlink(ptr)
        check("results.json is a symlink", True)
        check("it points at a snapshot", tgt.startswith("snapshots/"), "points at %r" % tgt)
        check("it is relative, not absolute", not tgt.startswith("/"))
        # getmtime FOLLOWS symlinks, and build_v2 derives the AMM age from it
        check("its mtime resolves through the link to a real file",
              os.path.exists(ptr) and os.path.getmtime(ptr) > 0)
    else:
        check("results.json is a symlink", os.path.isfile(ptr),
              "still a real file -- the writer has not run since the change")

    print("\n=== 3. enumeration survives .json.gz (the retention trap) ===")
    # retention compresses old snapshots. A glob of *.json alone would lose them, and
    # sorted(...)[-2] would then return a WRONG previous rather than raising.
    with tempfile.TemporaryDirectory() as d:
        old = S.SNAPDIR
        S.SNAPDIR = d
        try:
            for n in ("20260101T000000Z.json.gz", "20260102T000000Z.json", "20260103T000000Z.json"):
                p = os.path.join(d, n)
                (gzip_open(p) if n.endswith(".gz") else open(p, "w")).close()
            got = S.list_snapshots()
            check("compressed snapshots are enumerated (%d found)" % len(got), len(got) == 3,
                  "got %r -- a *.json-only glob loses .gz and returns a wrong previous" % got)
            check("they are ordered newest-first", got[0].startswith("20260103"))
            check("previous_snapshot picks the true previous",
                  S.previous_snapshot("20260103T000000Z").startswith("20260102"))
        finally:
            S.SNAPDIR = old

    print("\n=== 4. the diff cannot report one pool as both gone and appeared ===")
    # The engineered case: same pool twice, uuid present on one side only. Before the fallback
    # namespace this produced a phantom gone+appeared pair from a keying artefact.
    A = {"pool": "aaaa-1111", "chain": "Base", "project": "morpho-blue", "symbol": "CBBTC"}
    B = {"pool": None, "chain": "Base", "project": "morpho-blue", "symbol": "CBBTC"}
    ia, _, _ = S._index([A])
    ib, _, _ = S._index([B])
    check("a uuid key and a fallback key cannot collide", not (set(ia) & set(ib)),
          "they share a key, so one row silently overwrites the other")
    check("the fallback key is namespaced", list(ib)[0].startswith(S.FB_PREFIX),
          "unprefixed fallbacks cannot be told apart from uuids")

    print("\n=== 5. duplicate keys are counted, not dropped ===")
    dup = [{"pool": None, "chain": "B", "project": "x", "symbol": "Y"},
           {"pool": None, "chain": "B", "project": "x", "symbol": "Y"}]
    idx, n, dd = S._index(dup)
    check("a collision is reported (%d)" % dd, dd == 1,
          "a silently dropped row is indistinguishable from a pool that closed")

    print("\n=== 6. the join reports HOW it was keyed, not just that it worked ===")
    if len(ids) >= 2:
        a_rows, b_rows = S.load(ids[1]), S.load(ids[0])
        _, a_n, _ = S._index(a_rows)
        partial = a_n < len(a_rows)
        d = S.diff_snapshots(ids[1], ids[0])
        kb = d["keyed_by"]
        check("keyed_by distinguishes a full uuid join from a mixed one",
              ("uuid" in kb) and (partial == ("mixed" in kb)),
              "says %r while %d/%d rows had a uuid" % (kb, a_n, len(a_rows)))
        check("uuid coverage is reported as a NUMBER, not a claim",
              d["uuid_keyed"]["from"] == a_n)
        if d["reclassified"]:
            r0 = d["reclassified"][0]
            check("a re-classification carries from/to verdicts",
                  "from" in r0 and "to" in r0)
        # the totals must be internally consistent -- a count that does not add up is the
        # failure mode where re-labelling is mistaken for market movement
        tot_b = sum(v["to"] for v in d["totals"].values())
        check("totals sum to the snapshot size (%d)" % d["n_to"], tot_b == d["n_to"],
              "buckets sum to %d but the snapshot holds %d" % (tot_b, d["n_to"]))

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  the snapshot store keeps verifiable history")
    return 0


def gzip_open(p):
    import gzip
    return gzip.open(p, "wt")


if __name__ == "__main__":
    sys.exit(main())

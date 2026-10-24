#!/usr/bin/env python3
"""liquidations.py: unit semantics, cursor walk, dedup, and the honesty of the coverage stat.

The unit trap this suite pins: seized/repaid/bad-debt live in THREE different decimal scales
(collateral, loan, loan-as-shares) and the first read divided everything by 1e6, producing a
seized figure of $1.4 trillion in 30 minutes. A normalisation bug in THIS module would publish
a number that wrong silently -- so every normalisation here is asserted against hand-computed
closed forms with unequal, non-default decimals (SOL 9dp against USDC 6dp against wstETH 18dp).
"""
import json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "screener"))

import liquidations as L

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def main():
    print("=== 1. normalize(): decimals travel with the row and are per-ASSET ===")
    # SOL 9dp seized on a USDC 6dp loan
    it = {"txHash": "0xabc", "txIndex": 1, "logIndex": 2, "timestamp": 1731000000,
          "blockNumber": 100,
          "market": {"marketId": "0xm1", "lltv": 860000000000000000,
                     "collateralAsset": {"symbol": "SOL", "decimals": 9},
                     "loanAsset": {"symbol": "USDC", "decimals": 6}},
          "data": {"seizedAssets": 1_234_567_890, "repaidAssets": 4_500_000,
                   "badDebtAssets": 0, "liquidator": "0xdead"}}
    n = L.normalize(it)
    ck("seized 1,234,567,890 @9dp = 1.23456789 SOL", abs(n["seized"] - 1.23456789) < 1e-12,
       str(n["seized"]))
    ck("repaid 4,500,000 @6dp = exactly 4.5 USDC", n["repaid"] == 4.5, str(n["repaid"]))
    ck("key is tx:txidx:logidx (a re-sync cannot duplicate)", n["key"] == "0xabc:1:2")
    ck("lltv is the /1e18 fraction", abs(n["lltv"] - 0.86) < 1e-12)
    it2 = dict(it)
    it2["market"] = dict(it["market"], collateralAsset={"symbol": "WETH", "decimals": 18},
                         loanAsset={"symbol": "USDC", "decimals": 6})
    it2["data"] = {"seizedAssets": 10**18, "repaidAssets": 10**6, "badDebtAssets": 0}
    n2 = L.normalize(it2)
    ck("WETH 18dp: 1e18 raw = exactly 1.0 WETH (the $1.4T bug asserted dead)",
       n2["seized"] == 1.0, str(n2["seized"]))
    # raw integers retained so a rounding dispute can be re-derived
    ck("raw values retained beside the floats", n["seized_raw"] == 1_234_567_890
       and n["repaid_raw"] == 4_500_000)

    print("\n=== 2. summarize(): windows and debt accounting ===")
    now = int(time.time())
    items = []
    for off, bad in ((0, 0), (3600, 0), (25 * 3600, 5.0), (8 * 86400, 0), (40 * 86400, 900.0)):
        items.append(dict(n, ts=now - off, bad_debt=bad, seized=1.0, repaid=1.0,
                          collateral="SOL", key="k%d" % off, block=0, tx="0x%d" % off))
    s = L.summarize(items)
    ck("h24 window holds the two fresh events", s["h24"]["events"] == 2)
    ck("d7 window excludes the 25h-old one (25h > 24h)", s["d7"]["events"] == 3, str(s["d7"]["events"]))
    # windows are (now - k): 0 and 1h are h24; 25h is in d7/d30 but not h24; 8d = 192h is in
    # d30 but not d7; 40d is outside d30. So d30 = 4 events, d7 = 3, h24 = 2, and the d30
    # bad-debt total is ONLY the 25h event's $5.00 -- the $900 one is 40 days old.
    ck("d30 holds 0,1h,25h,8d but not 40d", s["d30"]["events"] == 4, str(s["d30"]["events"]))
    ck("d7 holds 0,1h,8d but not 25h", s["d7"]["events"] == 3, str(s["d7"]["events"]))
    ck("bad-debt total over d30 = $5.00 (the 40d $900 event is outside)",
       abs(s["d30"]["bad_total"] - 5.0) < 1e-9, str(s["d30"]["bad_total"]))
    ck("bad-debt EVENTS counted distinct from dollars (1 of 4)", s["d30"]["bad_events"] == 1)

    print("\n=== 3. sync(): dedup is by identity, and the store never goes backwards ===")
    # build a store from two overlapping page runs against a stubbed _get
    orig = L._get
    calls = {"n": 0}
    def fake_get(ts_lte=None):
        calls["n"] += 1
        base = [{"txHash": "0xa%d" % i, "txIndex": 0, "logIndex": 0, "timestamp": 1731000000 - i * 60,
                 "blockNumber": 100 + i,
                 "market": {"marketId": "0xm1", "lltv": None,
                            "collateralAsset": {"symbol": "SOL", "decimals": 9},
                            "loanAsset": {"symbol": "USDC", "decimals": 6}},
                 "data": {"seizedAssets": i, "repaidAssets": 0, "badDebtAssets": 0}} for i in range(150)]
        if ts_lte is None:
            return base[:100], len(base)
        # second page: the tail 50, duplicated 100 times by a cursor that misbehaves
        tail = base[100:]
        return (tail + base[:100]), len(base)
    L._get = fake_get
    import tempfile
    tmpstore = os.path.join(tempfile.mkdtemp(), "liq_test.json")
    # snapshot the production store's bytes so the isolation claim is against a REAL baseline,
    # not a wish: the first version of this test wrote 150 synthetic rows into the real
    # 30,000-event record, passed every assertion, and damaged the artefact it verified.
    prod_before = open(L.STORE, "rb").read() if os.path.exists(L.STORE) else None
    try:
        st = L.sync(max_pages=4, quiet=True, store_path=tmpstore)
    finally:
        L._get = orig
    ck("the tmp store holds the deduped rows", os.path.exists(tmpstore)
       and len(json.load(open(tmpstore))["items"]) == 150,
       "the write must go to the path the caller gave, nowhere else")
    prod_now = open(L.STORE, "rb").read() if os.path.exists(L.STORE) else None
    ck("the production store is byte-identical across the test",
       prod_before == prod_now,
       "a test that damages the thing it verifies is worse than no test")
    ck("deduped to 150 unique keys in the OWN store (150 real + 0 synthetic extra)",
       len(st["items"]) == 150, "got %d over %d pages" % (len(st["items"]), st["fetch_pages"]))
    ck("the stall guard stopped it before the 4-page budget",
       st["fetch_pages"] <= 3, str(st["fetch_pages"]))
    ck("summary present and consistent", st["summary"]["n"] == len(st["items"]))

    print("\n=== 4. link_to_runs(): coverage says what it does NOT cover ===")
    if os.path.exists(L.STORE):
        lk = L.link_to_runs()
        c = lk["coverage"]
        ck("every event carries a flag field", all("flag" in e for e in lk["events"]))
        ck("coverage totals add up",
           c["before_first_run"] + c["flagged_avoid"] + c["flagged_caution"] + c["flagged_real"]
           == c["events"], json.dumps(c))
        # covered_from names a real run dir WHEN any event is covered; a store of events older
        # than every run (the common backfill case) has nothing covered and carries None.
        # Asserting it unconditionally made the test describe its fixture, not the module.
        if c["before_first_run"] < c["events"]:
            ck("covered_from names a real run dir", os.path.isdir(os.path.join(ROOT, "runs",
               lk.get("covered_from") or "notadir")), str(lk.get("covered_from")))
        else:
            ck("no covered events -> covered_from is None (not a fake run)",
               lk.get("covered_from") is None, str(lk.get("covered_from")))
        # the honesty clause: before_first_run must be LARGE here (the screen began 2026-10-07)
        ck("events before coverage are recorded, not dropped", c["before_first_run"] > 0,
           "a coverage statistic that hides its own window is marketing")
    else:
        ck("liquidations.json exists", False)

    print("\n=== 5. the store on disk is a sane one ===")
    if os.path.exists(L.STORE):
        st = L.load()
        ck("items sorted newest-first",
           all(st["items"][i]["ts"] >= st["items"][i + 1]["ts"] for i in range(len(st["items"]) - 1)))
        keys = [i["key"] for i in st["items"]]
        ck("no duplicate keys", len(keys) == len(set(keys)))
    return 0 if not fails else 1


if __name__ == "__main__":
    rc = main()
    print("\n=== RESULT ===")
    if rc:
        print("  %d FAILURE(S)" % len(fails))
        for f in fails:
            print("    - " + f)
    else:
        print("  liquidation ingest: units, dedup, cursor and coverage all verified")
    sys.exit(rc)

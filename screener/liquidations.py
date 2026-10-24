#!/usr/bin/env python3
"""liquidations.py - ingest Morpho Blue liquidations from the official API, Base only.

THE PRIZE, STATED HONESTLY

badDebt exists NOW in the GraphQL feed but every prediction claim has been blocked on not knowing
WHEN bad debt happens (the brief: "badDebt timing is not in the API"). Task B's answer, verified on
the live API today:

  MarketTransaction.type_in: ["Liquidation"]   <- Liquidation is a FIRST-CLASS type
  countTotal on Base: 32,321 all-time, ~2,380 in the last 30 days
  page of 100 covers ~30 minutes in a burst, ~6h in a quiet spell

So the ingest IS task B, and the part nobody has is the CROSS-REFERENCE: for each liquidation, what
did this project's screen say about that market BEFORE it happened? The screen has run since 2026-10-07,
so historical validation is impossible -- what accumulates from today forward is the flag-coverage
statistic, and this module computes it from the run ledger at read time, not at sync time.

UNIT SEMANTICS (verified against live rows, and the easiest thing to get silently wrong):
  seizedAssets  is in the COLLATERAL asset's decimals (WETH 18dp, SOL 9dp)
  repaidAssets  is in the LOAN asset's decimals (USDC 6dp) -- the debt actually extinguished
  repaidShares  is loan units as SHARES, not assets; never sum it with repaidAssets
  badDebtAssets is in the LOAN asset's decimals; >0 means the market ate a real loss
An earlier read divided every field by 1e6 and produced "$1.4T seized in 30 minutes"; that is the
error classes this module must forever make impossible, hence the decimals travel WITH the row.

RATE LIMITS (the project's measured experience: throttles on concurrency, serial + delay works):
serial pages of 100, 1.2s sleep, exponential backoff on 429, resume by timestamp_lte so every run
is resumable and incremental by construction.
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://blue-api.morpho.org/graphql"
CHAIN_ID = 8453                # Base
PAGE = 100
SLEEP = 1.2                    # serial on purpose; concurrency is what got 600/600 HTTP errors
HDRS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
STORE = os.path.join(HERE, "liquidations.json")

# The screen's own verdicts, so a liquidation can be labelled by what we said beforehand.
VERDICTS = ("REAL", "CAUTION", "AVOID")

QUERY = """query($g: Int) {
  marketTransactions(first: %(page)d, where: {type_in: [Liquidation], chainId_in: [%(chain)d],
                      timestamp_lte: $g},
                     orderBy: Timestamp, orderDirection: Desc) {
    pageInfo { countTotal }
    items { txHash txIndex logIndex timestamp blockNumber
      market { marketId lltv
               collateralAsset { symbol decimals address }
               loanAsset { symbol decimals } }
      data { ... on MarketTransactionLiquidationData { seizedAssets repaidAssets badDebtAssets liquidator } } } } }""" % {
    "page": PAGE, "chain": CHAIN_ID}


def _gql(payload, timeout=45):
    body = json.dumps(payload).encode()
    r = urllib.request.Request(API, data=body, headers=dict(HDRS))
    j = json.loads(urllib.request.urlopen(r, timeout=timeout).read())
    if j.get("errors"):
        raise RuntimeError("GraphQL: %s" % json.dumps(j["errors"])[:220])
    return j.get("data") or {}


def _get(ts_lte=None):
    """One page, newest first. ts_lte bounds it: pages walk backwards through history."""
    v = {"g": ts_lte} if ts_lte is not None else {}
    d = _gql({"query": QUERY, "variables": v})
    mts = d.get("marketTransactions") or {}
    return mts.get("items") or [], (mts.get("pageInfo") or {}).get("countTotal")


def normalize(it):
    """API row -> the flat, unit-annotated row the dashboard and the linker consume.
    Every unit-ambiguous number carries its exponent; a reader should never have to guess."""
    mk = it.get("market") or {}
    ca = mk.get("collateralAsset") or {}
    la = mk.get("loanAsset") or {}
    d = it.get("data") or {}
    cdec = int(ca.get("decimals") or 0)
    ldec = int(la.get("decimals") or 0)
    sei = int(d.get("seizedAssets") or 0)
    rep = int(d.get("repaidAssets") or 0)
    bad = int(d.get("badDebtAssets") or 0)
    return {
        "key": "%s:%s:%s" % (it.get("txHash"), it.get("txIndex"), it.get("logIndex")),
        "ts": int(it.get("timestamp") or 0),
        "block": int(it.get("blockNumber") or 0),
        "market_id": mk.get("marketId"),
        "collateral": ca.get("symbol"),
        "collateral_decimals": cdec,
        "loan": la.get("symbol"),
        "loan_decimals": ldec,
        # raw integers PLUS the human form, both, because a raw bigint without its decimals is
        # exactly how "$1.4T seized" got published internally before
        "seized_raw": sei, "seized": sei / (10 ** cdec) if cdec else None,
        "repaid_raw": rep, "repaid": rep / (10 ** ldec) if ldec else None,
        "bad_debt_raw": bad, "bad_debt": bad / (10 ** ldec) if ldec else None,
        "lltv": (int(mk.get("lltv")) / 10 ** 18) if mk.get("lltv") is not None else None,
        "liquidator": d.get("liquidator"),
        "tx": it.get("txHash"),
    }


def summarize(items):
    """The dashboard's numbers. All four windows are computed, so the page shows its own coverage."""
    import collections
    now = int(time.time())
    s = {"n": len(items)}
    for k, label in ((86400, "h24"), (7 * 86400, "d7"), (30 * 86400, "d30")):
        w = [i for i in items if now - i["ts"] <= k]
        s[label] = {
            "events": len(w),
            "seized": sum(i["seized"] or 0 for i in w),
            "repaid": sum(i["repaid"] or 0 for i in w),
            "bad_events": sum(1 for i in w if (i["bad_debt"] or 0) > 0),
            "bad_total": sum(i["bad_debt"] or 0 for i in w if (i["bad_debt"] or 0) > 0),
            "by_collateral": dict(collections.Counter(i["collateral"] for i in w)),
        }
    s["oldest_ts"] = min((i["ts"] for i in items), default=None)
    s["newest_ts"] = max((i["ts"] for i in items), default=None)
    return s


def load(path=None):
    try:
        return json.load(open(path or STORE))
    except FileNotFoundError:
        return None


def sync(max_pages=400, quiet=False, store_path=None):
    """Walk history back to either the oldest stored event or max_pages, whichever comes first.
    Append-and-dedup by (tx, txIndex, logIndex): a re-sync can never duplicate or delete. Returns
    the store dict.

    store_path: WHERE THE RESULT IS WRITTEN. Default None means the production store. This
    exists because the first test run of this module wrote 150 synthetic rows into the real
    30,784-event record and the suite then PASSED while corrupting the artefact it was testing --
    a test that damages the thing it verifies is worse than no test. A test of this module passes
    its own path; production code calls it with none.
    """
    # NO GLOBAL REBINDING. The first version toggled the module-global STORE around load(), which
    # left the final write holding whichever value was in scope at THAT moment -- the test's store
    # loaded fine, then the restore put the production path back, and the atomic write at the end
    # wrote 150 synthetic rows over the real 28,000-event record. The path now travels as a
    # parameter the whole way through; a shared global is simply not used for writes.
    _dest = store_path or STORE
    st = load(_dest) or {"synced_at": None, "items": []}
    have = {i["key"] for i in st["items"]}
    all_items = list(st["items"])
    newest_ts = max((i["ts"] for i in st["items"]), default=None)

    pages = 0
    ts_lte = None                      # None = start from NOW
    _prev_oldest = None
    _same = 0
    while pages < max_pages:
        for attempt in range(4):
            try:
                its, total = _get(ts_lte)
                break
            except (urllib.error.HTTPError, RuntimeError) as e:
                wait = 2.0 * (attempt + 1)
                if not quiet:
                    print("  [liq] page failed (%s); retrying in %.0fs" % (str(e)[:60], wait), flush=True)
                time.sleep(wait)
        else:
            its, total = [], None
        if not its:
            break
        new = 0
        # skip the overlap: desc order, the tail of this page may already be stored
        for i in its:
            r = normalize(i)
            if r["key"] in have:
                continue
            have.add(r["key"])
            all_items.append(r)
            new += 1
        pages += 1
        oldest = its[-1].get("timestamp")
        if not quiet:
            print("  [liq] page %3d: +%d (total %d, reached %s)"
                  % (pages, new, len(all_items),
                     time.strftime("%Y-%m-%d %H:%M", time.gmtime(oldest))), flush=True)
        if newest_ts is None or oldest is None:
            pass
        if oldest is None:
            break
        if oldest <= 1:
            break                      # corrupt row; do not loop forever on it
        # STALL GUARD. A page of all-duplicate rows advances the cursor by its OLDEST timestamp,
        # which is correct -- unless the API ignores timestamp_lte and serves the newest page
        # again. The first build sat at "page 30: +0, reached 15:35" for 20 pages: ts_lte was
        # NOT changing because oldest was NOT changing. Detect it: if this page's oldest equals
        # the previous page's oldest, step BACKWARD past it with an explicit -1 and, if that
        # still returns the same rows, stop rather than burn the remainder of max_pages.
        if oldest == _prev_oldest:
            _same += 1
            if _same >= 2:
                if not quiet:
                    print("  [liq] cursor stalled at %s; stopping"
                          % time.strftime("%Y-%m-%d %H:%M", time.gmtime(oldest)), flush=True)
                break
        else:
            _same = 0
        _prev_oldest = oldest
        ts_lte = int(oldest) - 1
        time.sleep(SLEEP)
    all_items.sort(key=lambda r: -r["ts"])
    st = {"synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "chain_id": CHAIN_ID, "fetch_pages": pages, "items": all_items,
          "summary": summarize(all_items)}
    # atomic-ish write: a half-written store must not become the record
    tmp = _dest + ".tmp"
    json.dump(st, open(tmp, "w"))
    os.replace(tmp, _dest)
    return st


def link_to_runs(st=None):
    """For each liquidation: the newest run BEFORE it, and that run's verdict for the market.

    THE STATISTIC THE PRODUCT SELLS. A liquidation that happens on a market the screen called
    AVOID an hour earlier is a flag that WORKED; one on a REAL market is a miss. Both are
    recorded, because a hit-rate nobody can audit is marketing, not measurement. Runs began
    2026-10-07, so events before that carry flag: null -- the honest column says so rather than
    implying coverage it does not have.
    """
    import glob
    st = st or load()
    if not st:
        return None
    runs = []
    for d in sorted(glob.glob(os.path.join(HERE, "runs", "*", ""))):
        try:
            mj = json.load(open(os.path.join(d, "meta.json")))
            sc = json.load(open(os.path.join(d, "screen.json")))
        except Exception:
            continue
        runs.append({"ts": mj.get("written_at"), "dir": os.path.basename(d.rstrip("/")),
                     "by_market": {r.get("market_id"): r for r in sc}})
    def parse(ts):
        import datetime
        return int(datetime.datetime.strptime(ts.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                   .replace(tzinfo=datetime.timezone.utc).timestamp())
    out = []
    for i in sorted(st["items"], key=lambda r: -r["ts"]):
        flag = None
        # NEWEST run before the event, not the oldest. The prior form iterated `runs` ascending
        # and broke at the FIRST run with ts<=event -- which is the OLDEST verdict, so a market
        # that moved CAUTION->REAL since the event got the stale verdict. forward_test.py found
        # this: it reported 4 CAUTION to link_to_runs' 1, and the difference was the stale walk.
        for run in reversed(runs):
            try:
                if parse(run["ts"]) <= i["ts"]:
                    row = run["by_market"].get(i["market_id"])
                    if row:
                        flag = {"run": run["dir"], "verdict": row.get("verdict"),
                                "fails": row.get("fails") or [], "hours_before":
                                round((i["ts"] - parse(run["ts"])) / 3600.0, 1)}
                    break
            except Exception:
                continue
        a = dict(i)
        a["flag"] = flag
        out.append(a)
    cov = {"events": len(out),
           "before_first_run": sum(1 for x in out if x["flag"] is None),
           "flagged_avoid": sum(1 for x in out if x["flag"] and x["flag"]["verdict"] == "AVOID"),
           "flagged_caution": sum(1 for x in out if x["flag"] and x["flag"]["verdict"] == "CAUTION"),
           "flagged_real": sum(1 for x in out if x["flag"] and x["flag"]["verdict"] == "REAL")}
    first = [x for x in out if x["flag"]]
    return {"events": out, "coverage": cov,
            "covered_from": min((x["flag"]["run"] for x in first), default=None)}


def main():
    args = sys.argv[1:]
    pages = 400
    if "--pages" in args:
        pages = int(args[args.index("--pages") + 1])
    incremental = "--incremental" in args
    quiet = "--quiet" in args
    if incremental:
        pages = min(pages, 8)          # an incremental tick takes a bounded number of pages
    st = sync(max_pages=pages, quiet=quiet)
    s = st["summary"]
    print("liquidations.json: %d events, synced_at %s" % (s["n"], st["synced_at"]))
    for w in ("h24", "d7", "d30"):
        x = s[w]
        print("  %-4s %5d events  seized %14.4f  repaid %12.4f  bad-debt events %3d ($%.2f)"
              % (w, x["events"], x["seized"] or 0, x["repaid"] or 0, x["bad_events"], x["bad_total"] or 0))
    lk = link_to_runs(st)
    if lk:
        c = lk["coverage"]
        print("  flag coverage: %d events since coverage began: AVOID %d, CAUTION %d, REAL %d"
              % (c["events"] - c["before_first_run"], c["flagged_avoid"],
                 c["flagged_caution"], c["flagged_real"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

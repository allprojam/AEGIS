#!/usr/bin/env python3
"""run_history.py - read-only access to the immutable run ledger.

One module, three consumers: the JSON API, the MCP tools, and the dashboard's "what changed"
section. They must not each re-derive the same thing from runs/ -- that is how the two-renderer
drift happened before.

WHAT THIS READS: runs/<iso>/{screen,markets,meta,allocator}.json and alerts.log. Nothing here
writes, and nothing here touches the network. The ledger is the product; this is a lens on it.

THE GAP THIS CLOSES. 36 immutable, replay-verified runs had accumulated with no interface to
them. The dashboard showed only the newest, the transition log showed only deltas, and nobody
could ask "what has this market's utilisation done over time". The dataset was write-only.

    get_index()             -> [{run, block, written_at, verdicts, n_markets}, ...]
    get_run(run_id)         -> one run's artefacts
    get_series(market_id)   -> [{run, block, utilization, lltv, verdict, ...}, ...]
    get_changes()           -> parsed alerts.log, newest first
    list_markets()          -> market_id -> {collateral, lltv, runs_seen}
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
ALERTS = os.path.join(HERE, "alerts.log")

_RUN_RE = re.compile(r"^\d{8}T\d{6}Z$")


def _run_dirs():
    if not os.path.isdir(RUNS):
        return []
    return sorted(d for d in os.listdir(RUNS)
                  if _RUN_RE.match(d) and os.path.isdir(os.path.join(RUNS, d)))


def _load(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def _meta(run_id):
    m = _load(os.path.join(RUNS, run_id, "meta.json"))
    return m if isinstance(m, dict) else {}


def _verdicts(rows):
    out = {}
    for r in rows or []:
        v = r.get("verdict")
        if v:
            out[v] = out.get(v, 0) + 1
    return out


def get_index(limit=None, newest_first=True):
    """One line per run. Reads meta.json and screen.json only, so it stays cheap."""
    out = []
    for d in _run_dirs():
        meta = _meta(d)
        prov = meta.get("provenance") or {}
        scr = _load(os.path.join(RUNS, d, "screen.json")) or []
        out.append({
            "run": d,
            "block": prov.get("block_number"),
            "ingested_at": prov.get("fetched_at"),
            "written_at": meta.get("written_at"),
            "n_markets": len(scr),
            "verdicts": _verdicts(scr),
            "artefacts": meta.get("artefacts") or [],
        })
    if newest_first:
        out = list(reversed(out))
    return out[:limit] if limit else out


def get_run(run_id):
    """Everything for one run. Returns None if the run is unknown or malformed."""
    if not _RUN_RE.match(str(run_id or "")):
        return None
    d = os.path.join(RUNS, run_id)
    if not os.path.isdir(d):
        return None
    out = {"run": run_id}
    for n, k in (("meta.json", "meta"), ("screen.json", "screen"),
                 ("markets.json", "markets"), ("allocator.json", "allocator")):
        p = os.path.join(d, n)
        if os.path.exists(p):
            out[k] = _load(p)
    # never return a run with no screen: an empty shell would look like a valid answer
    if not out.get("screen"):
        return None
    return out


def list_markets():
    """market_id -> identity, for discovery. Reads every run, so callers should cache."""
    seen = {}
    for d in _run_dirs():
        for r in (_load(os.path.join(RUNS, d, "screen.json")) or []):
            mid = r.get("market_id")
            if not mid:
                continue
            e = seen.setdefault(mid, {"market_id": mid, "collateral": r.get("collateral"),
                                      "lltv": r.get("lltv"), "runs_seen": 0,
                                      "verdicts": {}})
            e["runs_seen"] += 1
            v = r.get("verdict")
            if v:
                e["verdicts"][v] = e["verdicts"].get(v, 0) + 1
    return seen


def resolve_market(q):
    """A market_id, a collateral symbol, or a prefix -> matching market_id(s).

    Accepts what a human or an agent would actually paste. Returns a LIST so an ambiguous
    symbol (several markets share one collateral) is reported as ambiguous rather than
    silently picking one -- guessing would attach real numbers to the wrong market.
    """
    q = str(q or "").strip()
    if not q:
        return []
    markets = list_markets()
    if q in markets:
        return [q]
    ql = q.lower()
    if ql.startswith("0x"):
        return [m for m in markets if m.startswith(ql)]
    return [m for m, e in markets.items()
            if str(e.get("collateral") or "").lower() == ql]


def get_series(market_id, fields=None):
    """One market across every run it appears in. This is the dataset, made queryable."""
    fields = fields or ("utilization", "lltv", "net_apy", "tvl_usd", "liquidity_usd",
                        "sigma_to_breach", "bad_debt_usd", "realized_bad_debt_usd")
    pts = []
    for d in _run_dirs():
        meta = _meta(d)
        for r in (_load(os.path.join(RUNS, d, "screen.json")) or []):
            if r.get("market_id") != market_id:
                continue
            pt = {"run": d,
                  "block": (meta.get("provenance") or {}).get("block_number"),
                  "ingested_at": (meta.get("provenance") or {}).get("fetched_at"),
                  "verdict": r.get("verdict"),
                  "fails": r.get("fails") or []}
            for f in fields:
                pt[f] = r.get(f)
            pts.append(pt)
            break
    return pts


def get_changes(limit=None):
    """alerts.log parsed, newest first. Append-only, so this is the full history."""
    if not os.path.exists(ALERTS):
        return []
    out = []
    for line in open(ALERTS):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue          # a malformed line must not hide the rest of the log
    out = list(reversed(out))
    return out[:limit] if limit else out


def _market_row(run_id, market_id):
    """The stored market row for one id in one run. Used to enrich an event with the venue,
    the contract addresses and the block it was observed at."""
    if not market_id:
        return None
    try:
        rows = _load(os.path.join(RUNS, run_id, "markets.json")) or []
    except Exception:
        return None
    for r in rows:
        if r.get("market_id") == market_id:
            return r
    return None


# Basescan accepts any Base address (token, pool or contract) on /address/.
BASESCAN = "https://basescan.org/address/%s"
# Morpho's app addresses a market by its bytes32 id.
MORPHO_MARKET = "https://app.morpho.org/base/market/%s"


def enrich_event(rec, e):
    """Attach everything we hold about one transition.

    The raw log records WHAT changed and the numbers either side. That is enough to act on and
    not enough to investigate: it does not say which venue the market belongs to, what the
    position was worth, or where to look on-chain. This joins it to the run's stored market row
    so every transition carries its venue, its contract addresses, its size, and links.

    Everything added here is either something already recorded in the run, or a URL DERIVED from
    a recorded address. Nothing is inferred, and a missing field stays missing rather than
    becoming a plausible default.
    """
    out = dict(e)
    run_id = rec.get("to_run")
    mid = e.get("market_id")
    out["run"] = run_id
    out["prev_run"] = rec.get("from_run")
    out["block"] = rec.get("block")
    out["logged_at"] = rec.get("logged_at")
    out["venue"] = "Morpho Blue"
    out["chain"] = "Base"
    out["explorer"] = None
    out["market_url"] = MORPHO_MARKET % mid if mid else None

    m = _market_row(run_id, mid) or {}
    if m:
        out["collateral_address"] = m.get("collateral_address")
        out["loan"] = m.get("loan")
        out["oracle"] = m.get("oracle")
        out["oracle_type"] = m.get("oracle_type")
        out["lltv"] = m.get("lltv")
        out["borrow_usd"] = m.get("borrow_usd")
        out["liquidity_usd"] = m.get("liquidity_usd")
        out["tvl_usd"] = m.get("tvl_usd")
        out["collateral_usd"] = m.get("collateral_usd")
        # Basescan the contract the reader would actually inspect: the collateral token, since
        # a market id is a Morpho-internal key and not an address.
        ca = m.get("collateral_address")
        if ca:
            out["explorer"] = BASESCAN % ca
    # enrich from the screen row too: it carries liquidity and warnings the market row may not
    for sr in (_load(os.path.join(RUNS, run_id, "screen.json")) or []):
        if sr.get("market_id") == mid:
            out["verdict"] = sr.get("verdict")
            out["fails"] = sr.get("fails") or []
            out["reasons"] = sr.get("reasons") or []
            if out.get("liquidity_usd") is None:
                out["liquidity_usd"] = sr.get("liquidity_usd")
            break
    return out


def get_events(limit=None, enrich=True):
    """Every transition, newest first, optionally enriched with venue and links."""
    out = []
    for rec in get_changes(limit=limit):
        for e in (rec.get("events") or []):
            out.append(enrich_event(rec, e) if enrich else e)
    return out


# How far back a "could not run" record is allowed to colour the CURRENT banner. The transition
# log polls every 15 minutes, so 4 records is about an hour of blindness.
UNCHECKED_RECENT = 4


def get_unchecked(recent=None):
    """Checks that COULD NOT run, split into CURRENT and HISTORICAL.

    Reported separately because 'no events found' and 'the detector was blind' are different
    states. Collapsing them would present an unchecked window as a clean one -- the exact
    failure the transition log was built to avoid.

    WHY THE SPLIT. This function used to dedupe by check name across the WHOLE append-only log,
    so a gap that ended hours ago still printed as a live warning forever. Measured: ORACLE_FLIP
    was flagged by 7 records all written in ONE backfill at 2026-10-07T20:25:51Z, from runs whose
    markets.json predated the `oracle_type` field. Every one of the 56 records logged the next day
    reported unchecked=0 -- the check was running and finding nothing. The page nonetheless told
    the reader "1 check(s) could not run: ORACLE_FLIP".

    That is a stale warning, and a warning that is always on is a warning that gets ignored -- the
    same failure as a permanently-tripped parity tripwire. But suppressing it entirely would be
    the opposite error: silence from a detector that never ran is not stability. So BOTH are
    returned, current first, and each says which it is.

    `recent` bounds how many of the newest records count as current. It is a parameter rather
    than a constant so a caller can widen it, and so a test can pin the boundary.
    """
    n = UNCHECKED_RECENT if recent is None else recent
    changes = get_changes()          # newest first
    cur, hist = {}, {}
    for i, rec in enumerate(changes):
        for u in (rec.get("unchecked") or []):
            k = u.get("check") or "?"
            bucket = cur if i < n else hist
            # newest record wins, so a reason from today replaces one from yesterday
            bucket.setdefault(k, {"check": k, "why": u.get("why"),
                                  "records_ago": i, "to_run": rec.get("to_run")})
    # a check that is CURRENT must not also be reported as historical
    for k in cur:
        hist.pop(k, None)
    for v in cur.values():
        v["state"] = "current"
    for v in hist.values():
        v["state"] = "historical"
    return [cur[k] for k in sorted(cur)] + [hist[k] for k in sorted(hist)]


if __name__ == "__main__":
    idx = get_index()
    print("runs: %d" % len(idx))
    for e in idx[:3]:
        print("  %s  block=%s  verdicts=%s" % (e["run"], e["block"], e["verdicts"]))
    mk = list_markets()
    print("markets tracked: %d" % len(mk))
    ch = get_changes()
    print("transition log: %d intervals, %d events"
          % (len(ch), sum(r.get("n_events") or 0 for r in ch)))
    for u in get_unchecked():
        print("  UNCHECKED: %s" % u["check"])

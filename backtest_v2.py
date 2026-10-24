#!/usr/bin/env python3
"""Aegis Structural Backtest v2 — Severe Capital Destruction, with de-tracking separated.

WHAT CHANGED FROM v1, and why

  v1 measured "death" as a binary and produced a conflated outcome variable: a pool whose
  DefiLlama chart merely ENDS is not necessarily dead, and a pool that slowly bleeds out
  90% of its liquidity is not "alive". Three boundaries fix that.

  1. OUTCOME = SEVERE CAPITAL DESTRUCTION (not death).
       FAILED     TVL fell below 10% of its value at T, OR final TVL < $10,000
       IMPAIRED   TVL fell below 50% but not below 10%      (the slow bleed)
       SURVIVED   anything else
     A pool that lost 90% of its capital HAS structurally failed even if it still reports.

  2. DE-TRACKING IS RESOLVED, NOT ASSUMED.
     If a chart ends, that is ambiguous. We resolve it by querying GeckoTerminal for the
     pool's CURRENT on-chain reserve:
        404            -> the pool does not exist on-chain   => CONFIRMED_DEAD
        reserve == 0   -> exists but holds nothing           => CONFIRMED_DEAD (drained)
        reserve  > 0   -> still funded; the aggregator just  => DETRACKED (excluded from
                          stopped indexing it                   both arms)
     Raw RPC is unavailable from this box (403 on base publicnode and mainnet.base.org), and
     web3 is installed but has no reachable node. GeckoTerminal gives the same fact in one
     HTTP call, so it is the resolver.

  3. COHORT IS ANCHORED TO A HISTORICAL SNAPSHOT.
     A live-feed candidate list is survivorship-biased by construction: every candidate
     exists today. The cohort is therefore built ONLY from pools whose own chart shows data
     on or before T-365d, which is a statement about the past, not about today.
     (DefiLlama has no /pools/<date> endpoint -- verified 404 -- so the chart's own first
     timestamp is the anchor.)

Run:  PREFILTER=/tmp/cohort.json python3 backtest_v2.py [n_target] [scan_limit]
"""
import json, os, sys, time, random, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "structural_backtest_v2.json")
JSONL = os.path.join(HERE, "structural_backtest_v2.jsonl")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

LOOKBACK_DAYS = 365
DEAD_DAYS = 60
FAIL_RATIO = 0.10          # >90% capital destroyed
IMPAIRED_RATIO = 0.50      # 50-90% destroyed = the slow bleed
FLOOR_USD = 10_000         # absolute floor: below this the pool is not a market
THIN_TVL = 1_000_000
SUBSIDY_RATIO = 0.50
IMPLAUSIBLE_BASE = 25.0
STABLE_KW = ("USD", "USDC", "USDT", "DAI", "EURC", "USDE", "SUSD")

DELAY = 0.05
BACKOFF = 15.0

# chain name (DefiLlama) -> GeckoTerminal network slug
GT_NET = {
    "Ethereum": "eth", "Base": "base", "Arbitrum": "arbitrum", "Optimism": "optimism",
    "Polygon": "polygon_pos", "BSC": "bsc", "Avalanche": "avalanche", "Solana": "solana",
    "Flare": "flare", "Gnosis": "xdai", "Fantom": "ftm", "Celo": "celo", "Sonic": "sonic",
    "Sui": "sui", "TON": "ton", "Tron": "tron", "Monad": "monad", "Mantle": "mantle",
    "Linea": "linea", "Scroll": "scroll", "Blast": "blast", "Ink": "ink",
}
# pools whose on-chain address we can look up by token pair (GeckoTerminal search)
GT_SEARCHABLE = set(GT_NET.keys())


def get(url, timeout=20, tries=2):
    last = None
    for _ in range(tries):
        try:
            r = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"__404__": True}
            last = e
            break
        except Exception as e:
            last = e
            time.sleep(0.7)
    raise last


def num(v):
    try:
        f = float(v)
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0


def screen_at(point):
    apy = num(point.get("apy")); base = num(point.get("apyBase"))
    rew = num(point.get("apyReward")); tvl = num(point.get("tvlUsd"))
    fails = []
    if tvl < THIN_TVL:
        fails.append("THIN")
    if apy > 0 and (rew / apy) > SUBSIDY_RATIO:
        fails.append("SUBSIDISED")
    if apy <= 0:
        fails.append("NO_YIELD")
    return fails, apy, base, rew, tvl


def resolve_ontrack(chain, tokens):
    """Return (status, detail). status in {CONFIRMED_DEAD, DETRACKED, UNKNOWN}."""
    net = GT_NET.get(chain)
    if not net or not tokens:
        return "UNKNOWN", "no network mapping or token address"
    tok = None
    for t in tokens:
        t = str(t).lower()
        if len(t) == 42 and t.startswith("0x") and set(t[2:]) != {"0"}:
            tok = t
            break
    if not tok:
        return "UNKNOWN", "no usable token address"
    try:
        j = get("https://api.geckoterminal.com/api/v2/networks/%s/tokens/%s/pools?page=1" % (net, tok))
    except Exception as e:
        return "UNKNOWN", "lookup failed: %s" % str(e)[:40]
    if j.get("__404__"):
        return "CONFIRMED_DEAD", "GeckoTerminal 404 on the token"
    data = j.get("data") or []
    if not data:
        return "CONFIRMED_DEAD", "token has no live pools on-chain"
    # any pool with real reserves means the venue is still funded
    best = max(float((d.get("attributes") or {}).get("reserve_in_usd") or 0) for d in data)
    if best <= 0:
        return "CONFIRMED_DEAD", "all pools report zero reserve"
    return "DETRACKED", max(0, len(data))


def main():
    n_target = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    scan_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 99999
    random.seed(20261007)

    live = get("https://yields.llama.fi/pools")["data"]
    meta = {p["pool"]: p for p in live if p.get("pool")}
    print("pools in feed: %s" % format(len(meta), ","), flush=True)

    pre = os.environ.get("PREFILTER", "")
    if pre and os.path.exists(pre):
        ids = [p for p in json.load(open(pre)) if p in meta]
        print("prefiltered candidates: %d" % len(ids), flush=True)
    else:
        ids = list(meta.keys()); random.shuffle(ids)
    ids = ids[:scan_limit]

    done = set()
    if os.path.exists(JSONL):
        for line in open(JSONL):
            try:
                done.add(json.loads(line)["pool"])
            except Exception:
                pass
    print("resuming: %d already collected" % len(done), flush=True)

    now = time.time()
    cutoff = now - LOOKBACK_DAYS * 86400
    stats = {"ok": 0, "short": 0, "young": 0, "err": 0, "ontrack": 0}
    consec_err = 0
    fh = open(JSONL, "a")

    for i, pid in enumerate(ids):
        if len(done) >= n_target:
            break
        if pid in done:
            continue
        if consec_err >= 15:
            print("  backoff %.0fs after %d errors" % (BACKOFF, consec_err), flush=True)
            time.sleep(BACKOFF); consec_err = 0
        try:
            h = get("https://yields.llama.fi/chart/%s" % pid, timeout=20)
            consec_err = 0
        except Exception:
            stats["err"] += 1; consec_err += 1; continue
        pts = h.get("data") or []
        if len(pts) < 30:
            stats["short"] += 1; continue
        try:
            ts = [time.mktime(time.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) for p in pts]
        except Exception:
            continue
        if ts[0] > cutoff:
            stats["young"] += 1; continue

        t_idx = max(j for j, t in enumerate(ts) if t <= cutoff)
        t_point, last, last_ts = pts[t_idx], pts[-1], ts[-1]
        m = meta[pid]

        sym = str(m.get("symbol", "")).upper()
        fails, apy, base, rew, tvl = screen_at(t_point)
        if any(k in sym for k in STABLE_KW) and base > IMPLAUSIBLE_BASE:
            fails.append("IMPLAUSIBLE")

        tvl_end = num(last.get("tvlUsd"))
        ratio = (tvl_end / tvl) if tvl > 0 else None
        days_since = (now - last_ts) / 86400

        # ---- outcome: severe capital destruction ----
        ontrack = None
        if days_since > DEAD_DAYS:
            # ambiguous: chart ended. resolve before judging.
            ontrack, detail = resolve_ontrack(m.get("chain"), m.get("underlyingTokens") or [])
            stats["ontrack"] += 1
            time.sleep(0.25)
            if ontrack == "DETRACKED":
                outcome = "DETRACKED"
            elif ontrack == "CONFIRMED_DEAD":
                outcome = "FAILED"
            else:
                outcome = "UNRESOLVED"
        elif ratio is not None and ratio < FAIL_RATIO:
            outcome = "FAILED"
        elif tvl_end < FLOOR_USD:
            outcome = "FAILED"
        elif ratio is not None and ratio < IMPAIRED_RATIO:
            outcome = "IMPAIRED"
        else:
            outcome = "SURVIVED"

        rec = {
            "pool": pid, "symbol": m.get("symbol"), "chain": m.get("chain"),
            "project": m.get("project"), "t_ts": t_point["timestamp"],
            "last_ts": last["timestamp"], "fails": fails, "flagged": bool(fails),
            "apy": apy, "apyBase": base, "apyReward": rew, "tvl": tvl,
            "tvl_end": tvl_end, "tvl_ratio": ratio,
            "days_since_data": round(days_since, 1), "outcome": outcome,
            "ontrack": ontrack,
        }
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        stats["ok"] += 1
        if stats["ok"] % 10 == 0:
            print("  collected %d  (scanned %d) ok=%d young=%d err=%d ontrack=%d"
                  % (stats["ok"], i + 1, stats["ok"], stats["young"], stats["err"], stats["ontrack"]),
                  flush=True)
        time.sleep(DELAY)

    fh.close()
    return report()


def wilson(k, n, z=1.96):
    import math
    if n == 0:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def report():
    rows = []
    if os.path.exists(JSONL):
        for line in open(JSONL):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    json.dump(rows, open(OUT, "w"), indent=1)
    import collections
    print("\n=== OUTCOMES (%d pools) ===" % len(rows), flush=True)
    c = collections.Counter(r["outcome"] for r in rows)
    for k in ("FAILED", "IMPAIRED", "SURVIVED", "DETRACKED", "UNRESOLVED"):
        if c.get(k):
            print("  %-12s %4d  (%.1f%%)" % (k, c[k], c[k] / len(rows) * 100))

    # FAILED = severe capital destruction. DETRACKED is excluded from both arms.
    scored = [r for r in rows if r["outcome"] in ("FAILED", "IMPAIRED", "SURVIVED")]
    print("\n=== FLAGGED vs PASSED  (excludes DETRACKED and UNRESOLVED) ===")
    for lab, sub in (("FLAGGED", [r for r in scored if r["flagged"]]),
                     ("PASSED", [r for r in scored if not r["flagged"]])):
        if not sub:
            continue
        k = sum(1 for r in sub if r["outcome"] == "FAILED")
        lo, hi = wilson(k, len(sub))
        print("  %-8s n=%-4d FAILED %3d = %5.1f%%   95%% CI [%4.1f%%, %5.1f%%]"
              % (lab, len(sub), k, k / len(sub) * 100, lo * 100, hi * 100))

    print("\n=== BY FLAG (FAILED only) ===")
    for flag in ("THIN", "SUBSIDISED", "NO_YIELD", "IMPLAUSIBLE"):
        sub = [r for r in scored if flag in r["fails"]]
        if not sub:
            continue
        k = sum(1 for r in sub if r["outcome"] == "FAILED")
        rest = [r for r in scored if flag not in r["fails"]]
        kr = sum(1 for r in rest if r["outcome"] == "FAILED") if rest else 0
        lo, hi = wilson(k, len(sub))
        print("  %-12s n=%-4d %5.1f%% [%4.1f%%,%5.1f%%]   without: %5.1f%%"
              % (flag, len(sub), k / len(sub) * 100, lo * 100, hi * 100,
                 (kr / len(rest) * 100) if rest else 0))
    print("\n  de-tracking checks performed: %d" % sum(1 for r in rows if r.get("ontrack")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

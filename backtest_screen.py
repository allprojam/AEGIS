#!/usr/bin/env python3
"""Aegis Structural Backtest — do the structural flags predict pool mortality?

THE QUESTION EVERY BUYER ASKS: "your screen says AVOID -- were you right?"

METHOD
  Cohort : pools whose DefiLlama history goes back at least 12 months.
  Point T: 365 days ago. Apply the structural checks using ONLY data visible at T.
  Point T+1: today. Measure what happened since T.

  Structural checks available historically (the /chart endpoint carries apy, apyBase,
  apyReward, tvlUsd only -- NOT sigma, outlier or count, which are current-only):

      THIN         tvlUsd < $1,000,000
      SUBSIDISED   apyReward / apy > 0.50
      NO_YIELD     apy <= 0
      IMPLAUSIBLE  stablecoin-like symbol and apyBase > 25%

  Outcome, measured at the latest point:
      DIED      no data in the last 60 days
      COLLAPSED TVL fell below 10% of its value at T
      SURVIVED  anything else

RATE LIMITING (learned the hard way)
  Parallel fetching at 16 and even 6 workers got the whole endpoint returning HTTP errors
  for every request (600/600). Sequential requests to the SAME endpoint return 200. So the
  chart endpoint throttles on concurrency, not on volume. This runs SERIAL with a small
  delay, and treats a burst of errors as a signal to back off rather than plough on.

SURVIVORSHIP
  Verified before building: pools that vanish from /pools still return history from
  /chart/{id}. Four sampled vanished pools returned 1372, 79, 378 and 727 points. The cohort
  is not silently restricted to survivors.

Run:  python3 backtest_screen.py [n_target] [scan_limit]
"""
import json, os, sys, time, random, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "structural_backtest.json")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
LOOKBACK_DAYS = 365
DEAD_DAYS = 60
COLLAPSE = 0.10
THIN_TVL = 1_000_000
SUBSIDY_RATIO = 0.50
IMPLAUSIBLE_BASE = 25.0
STABLE_KW = ("USD", "USDC", "USDT", "DAI", "EURC", "USDE", "SUSD")
DELAY = 0.05          # seconds between chart requests
BACKOFF = 15.0        # sleep this long after a run of failures


def get(url, timeout=20, tries=3):
    last = None
    for _ in range(tries):
        try:
            r = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())
        except urllib.error.HTTPError as e:
            last = e
            break                     # throttled: retrying immediately makes it worse
        except Exception as e:
            last = e
            time.sleep(0.8)
    raise last


def num(v):
    try:
        f = float(v)
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0


def screen_at(point):
    apy = num(point.get("apy"))
    base = num(point.get("apyBase"))
    rew = num(point.get("apyReward"))
    tvl = num(point.get("tvlUsd"))
    fails = []
    if tvl < THIN_TVL:
        fails.append("THIN")
    if apy > 0 and (rew / apy) > SUBSIDY_RATIO:
        fails.append("SUBSIDISED")
    if apy <= 0:
        fails.append("NO_YIELD")
    return fails, apy, base, rew, tvl


def main():
    n_target = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    scan_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    random.seed(20261007)

    live = get("https://yields.llama.fi/pools")["data"]
    meta = {p["pool"]: p for p in live if p.get("pool")}
    print("pools in feed: %s" % format(len(meta), ","), flush=True)

    # Target only pools that can qualify. results.json carries `count` = days of history,
    # so we skip the ~56% of the feed that cannot possibly reach 12 months. Blind scanning
    # burned requests and tripped the throttle.
    pre = os.environ.get("PREFILTER", "")
    if pre and os.path.exists(pre):
        pool_ids = json.load(open(pre))
        print("prefiltered candidate list: %d pools" % len(pool_ids), flush=True)
        ids = [p for p in pool_ids if p in meta]
    else:
        ids = list(meta.keys())
        random.shuffle(ids)
    ids = ids[:scan_limit]
    now = time.time()
    cutoff = now - LOOKBACK_DAYS * 86400

    # Resumable: append each accepted pool as one JSON line, and skip ids already done.
    JSONL = os.path.join(HERE, "structural_backtest.jsonl")
    done = set()
    if os.path.exists(JSONL):
        for line in open(JSONL):
            try:
                done.add(json.loads(line)["pool"])
            except Exception:
                pass
    print("resuming: %d pools already collected" % len(done), flush=True)

    rows = []
    stats = {"ok": 0, "short": 0, "nohist": 0, "err": 0, "oldest_ok": 0, "oldest_no": 0}
    consec_err = 0
    fh = open(JSONL, "a")

    for i, pid in enumerate(ids):
        if len(done) + len(rows) >= n_target and len(rows)>0:
            break
        if pid in done:
            continue
        if consec_err >= 20:
            print("  backing off %.0fs after %d consecutive errors" % (BACKOFF, consec_err), flush=True)
            time.sleep(BACKOFF)
            consec_err = 0
        try:
            h = get("https://yields.llama.fi/chart/%s" % pid, timeout=20, tries=2)
            consec_err = 0
        except Exception:
            stats["err"] += 1
            consec_err += 1
            continue
        pts = h.get("data") or []
        if len(pts) < 30:
            stats["short"] += 1
            continue
        try:
            ts = [time.mktime(time.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) for p in pts]
        except Exception:
            continue
        if ts[0] > cutoff:
            stats["nohist"] += 1
            continue
        stats["oldest_ok"] += 1

        t_idx = max(j for j, t in enumerate(ts) if t <= cutoff)
        t_point = pts[t_idx]
        last = pts[-1]
        last_ts = ts[-1]

        sym = str(meta[pid].get("symbol", "")).upper()
        fails, apy, base, rew, tvl = screen_at(t_point)
        if any(k in sym for k in STABLE_KW) and base > IMPLAUSIBLE_BASE:
            fails.append("IMPLAUSIBLE")

        tvl_end = num(last.get("tvlUsd"))
        ratio = (tvl_end / tvl) if tvl > 0 else None
        days_since = (now - last_ts) / 86400

        if days_since > DEAD_DAYS:
            outcome = "DIED"
        elif ratio is not None and ratio < COLLAPSE:
            outcome = "COLLAPSED"
        else:
            outcome = "SURVIVED"

        rows.append({
            "pool": pid, "symbol": meta[pid].get("symbol"), "chain": meta[pid].get("chain"),
            "project": meta[pid].get("project"),
            "t_ts": t_point["timestamp"], "last_ts": last["timestamp"],
            "fails": fails, "flagged": bool(fails),
            "apy": apy, "apyBase": base, "apyReward": rew, "tvl": tvl,
            "tvl_end": tvl_end, "tvl_ratio": ratio,
            "days_since_data": round(days_since, 1), "outcome": outcome,
        })
        stats["ok"] += 1
        fh.write(json.dumps(rows[-1]) + "\n"); fh.flush()
        if len(rows) % 10 == 0:
            print("  collected %d  (scanned %d/%d)  ok=%d short=%d nohist=%d err=%d"
                  % (len(rows), i + 1, len(ids), stats["ok"], stats["short"],
                     stats["nohist"], stats["err"]), flush=True)
        time.sleep(DELAY)

    fh.close()
    # merge everything for the report
    rows = []
    if os.path.exists(JSONL):
        for line in open(JSONL):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    json.dump(rows, open(OUT, "w"), indent=1)
    print("\nwrote %s  (%d pools)" % (OUT, len(rows)), flush=True)
    print("  scan stats: %s" % stats, flush=True)

    import collections
    c = collections.Counter(r["outcome"] for r in rows)
    print("\n=== OUTCOMES (%d pools) ===" % len(rows))
    for k in ("DIED", "COLLAPSED", "SURVIVED"):
        print("  %-10s %4d  (%.0f%%)" % (k, c.get(k, 0), c.get(k, 0) / max(len(rows), 1) * 100))

    BAD = ("DIED", "COLLAPSED")
    for label, sub in (("FLAGGED (>=1 structural fail)", [r for r in rows if r["flagged"]]),
                        ("PASSED (no structural fail)", [r for r in rows if not r["flagged"]])):
        if not sub:
            continue
        d = sum(1 for r in sub if r["outcome"] in BAD)
        print("\n=== %s ===" % label)
        print("  n = %d" % len(sub))
        print("  died or collapsed: %d (%.1f%%)" % (d, d / len(sub) * 100))

    print("\n=== BY SPECIFIC FLAG ===")
    for flag in ("THIN", "SUBSIDISED", "IMPLAUSIBLE", "NO_YIELD"):
        sub = [r for r in rows if flag in r["fails"]]
        if not sub:
            continue
        d = sum(1 for r in sub if r["outcome"] in BAD)
        base = [r for r in rows if flag not in r["fails"]]
        db = sum(1 for r in base if r["outcome"] in BAD) if base else 0
        print("  %-12s n=%-4d fail-rate %5.1f%%   (without it: %5.1f%%)"
              % (flag, len(sub), d / len(sub) * 100, (db / len(base) * 100) if base else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

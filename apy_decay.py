#!/usr/bin/env python3
"""APY decay — did the yield actually exist?

The screen is a YIELD screen, not a liquidity predictor. The question that matters is not
"did the pool survive" but "did the advertised yield actually pay".

For each pool already in the cohort:
    advertised  = apy at T (12 months ago)
    realized    = mean apy over the 365 days following T
    retention   = realized / advertised

A pool advertising 40% that realized 4% retained 10% of its promise. That is the slow bleed
the TVL view only sees indirectly.

Reads the cohort from structural_backtest_v2.jsonl, fetches each chart once, writes
apy_decay.json. Resumable via apy_decay.jsonl.

Run:  python3 apy_decay.py
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
COHORT = os.path.join(HERE, "structural_backtest_v2.jsonl")
OUT = os.path.join(HERE, "apy_decay.json")
JSONL = os.path.join(HERE, "apy_decay.jsonl")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
LOOKBACK_DAYS = 365
DELAY = 0.06
BACKOFF = 15.0


def get(url, timeout=20):
    r = urllib.request.Request(url, headers=UA)
    try:
        return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"__404__": True}
        raise


def num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def main():
    if not os.path.exists(COHORT):
        raise SystemExit("cohort missing: %s" % COHORT)
    cohort = []
    for line in open(COHORT):
        try:
            cohort.append(json.loads(line))
        except Exception:
            pass
    print("cohort: %d pools" % len(cohort), flush=True)

    done = set()
    if os.path.exists(JSONL):
        for line in open(JSONL):
            try:
                done.add(json.loads(line)["pool"])
            except Exception:
                pass
    print("resuming: %d already done" % len(done), flush=True)

    now = time.time()
    cutoff = now - LOOKBACK_DAYS * 86400
    fh = open(JSONL, "a")
    new = 0
    consec = 0

    for rec in cohort:
        pid = rec["pool"]
        if pid in done:
            continue
        if consec >= 15:
            print("  backoff %.0fs" % BACKOFF, flush=True)
            time.sleep(BACKOFF); consec = 0
        try:
            h = get("https://yields.llama.fi/chart/%s" % pid)
            consec = 0
        except Exception:
            consec += 1
            continue
        pts = h.get("data") or []
        if len(pts) < 30:
            continue
        try:
            ts = [time.mktime(time.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) for p in pts]
        except Exception:
            continue
        if ts[0] > cutoff:
            continue
        t_idx = max(j for j, t in enumerate(ts) if t <= cutoff)

        adv = num(pts[t_idx].get("apy"))
        adv_base = num(pts[t_idx].get("apyBase"))
        adv_rew = num(pts[t_idx].get("apyReward"))
        # realized over the following 365 days (from T to the end of the window)
        window = [num(p.get("apy")) for p in pts[t_idx:] if num(p.get("apy")) is not None]
        if not window:
            continue
        realized = sum(window) / len(window)
        # how many of those days paid anything at all
        paying = sum(1 for x in window if x > 0)

        fh.write(json.dumps({
            "pool": pid, "symbol": rec.get("symbol"), "chain": rec.get("chain"),
            "project": rec.get("project"), "fails": rec.get("fails") or [],
            "flagged": rec.get("flagged"), "outcome": rec.get("outcome"),
            "advertised": adv, "adv_base": adv_base, "adv_reward": adv_rew,
            "realized": realized, "days": len(window), "paying_days": paying,
            "retention": (realized / adv) if (adv and adv > 0) else None,
        }) + "\n")
        fh.flush()
        new += 1
        if new % 10 == 0:
            print("  done %d" % new, flush=True)
        time.sleep(DELAY)
    fh.close()

    rows = []
    for line in open(JSONL):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    json.dump(rows, open(OUT, "w"), indent=1)
    print("\nwrote %s (%d pools)" % (OUT, len(rows)), flush=True)

    import statistics
    def stats(sub, label):
        if not sub:
            return
        ret = [r["retention"] for r in sub if r["retention"] is not None]
        adv = [r["advertised"] for r in sub if r["advertised"] is not None]
        rz = [r["realized"] for r in sub if r["realized"] is not None]
        print("  %-22s n=%-4d median advertised %6.2f%%  realized %6.2f%%  retention %5.1f%%"
              % (label, len(sub), statistics.median(adv) if adv else 0,
                 statistics.median(rz) if rz else 0,
                 (statistics.median(ret) * 100) if ret else 0))

    print("\n=== YIELD RETENTION ===")
    stats(rows, "all")
    stats([r for r in rows if r["flagged"]], "FLAGGED")
    stats([r for r in rows if not r["flagged"]], "PASSED")
    print()
    for flag in ("SUBSIDISED", "THIN", "NO_YIELD", "IMPLAUSIBLE"):
        stats([r for r in rows if flag in (r["fails"] or [])], flag)

    print("\n=== HIGH-YIELD COHORT (advertised > 8%%) ===")
    hy = [r for r in rows if (r["advertised"] or 0) > 8]
    stats(hy, "advertised >8%%")
    print("  %-22s n=%d" % ("  of which realized <2%%", sum(1 for r in hy if (r["realized"] or 0) < 2)))
    print("  %-22s n=%d" % ("  of which realized > advertised", sum(1 for r in hy if (r["realized"] or 0) > (r["advertised"] or 0))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

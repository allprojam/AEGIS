"""
Aegis Yield Screener — separates REAL yield from SUBSIDISED yield.

THE FIVE CHECKS (each one earned from a measured failure this session):
  1. outlier flag      -> the 24.04% Uniswap pool I nearly used (apy7d was 9.15%)
  2. reward share      -> SparkDEX WFLR-USDt0: 33.84% = 12.56 base + 21.28 reward (63% emissions)
  3. spot vs 7d        -> a spot rate double the 7-day average is a spike, not a rate
  4. TVL floor         -> APS/USDt0 was $85,163; you cannot exit a real position there
  5. turnover          -> USDT/USDC v4 showed 6x/day which was TWO days = 100% of volume

Output is a VERDICT, not a prediction. This tool never places an order.
"""
import json, urllib.request, sys

# ---- thresholds: each documented with the failure that set it ----
MIN_TVL          = 1_000_000   # $1M: below this your exit moves the price
MAX_REWARD_SHARE = 0.50        # >50% of APY from emissions = subsidised
MIN_SPOT_RATIO   = 0.60        # spot APY must be >=60% of 7d average
MIN_TURNOVER     = 0.01        # <1% daily turnover = dead pool
MIN_DAYS_TRACKED = 30
MAX_STABLE_BASE  = 25.0   # stablecoin pool above this = credit risk, not fees          # Llama's 'count' = days of history

def num(v):
    """Coerce a feed value to float. The feed is JSON and DefiLlama has been seen to
    return numerics as strings ('5.5', '2') -- audit_core.js already handled this with
    Number() and mcp_server.py with float(), but screen.py compared them raw and
    crashed with TypeError. Same input, two behaviours: a parity bug."""
    if isinstance(v, bool): return 0.0
    try:
        f = float(v)
        return f if f == f else 0.0        # reject NaN
    except (TypeError, ValueError):
        return 0.0

def screen(p: dict) -> dict:
    """Apply the six checks. Returns verdict + every reason."""
    reasons, fails = [], []

    apy      = num(p.get("apy"))
    base     = num(p.get("apyBase"))
    rew      = num(p.get("apyReward"))
    apy7     = None if p.get("apyBase7d") is None else num(p.get("apyBase7d"))
    tvl      = num(p.get("tvlUsd"))
    v7       = num(p.get("volumeUsd7d"))
    outlier  = p.get("outlier")
    count    = num(p.get("count"))
    sigma    = p.get("sigma")
    il7      = p.get("il7d")

    # 1. outlier flag
    if outlier is True:
        fails.append("OUTLIER")
        reasons.append(f"flagged outlier; spot {apy:.2f}% vs 7d-base {apy7 if apy7 is not None else 'n/a'}")

    # 2. reward share (emissions)
    if apy > 0:
        share = rew / apy
        if share > MAX_REWARD_SHARE:
            fails.append("SUBSIDISED")
            reasons.append(f"{share*100:.0f}% of yield is emissions ({rew:.2f} of {apy:.2f}%) — ends when incentives do")

    # 3. spot vs 7d
    if apy7 is not None and apy7 > 0 and base > 0:
        ratio = base / apy7
        if ratio < MIN_SPOT_RATIO:
            fails.append("SPIKE")
            reasons.append(f"spot base {base:.2f}% is only {ratio*100:.0f}% of the 7d base {apy7:.2f}%")

    # 4. TVL floor
    if tvl < MIN_TVL:
        fails.append("THIN")
        reasons.append(f"TVL ${tvl:,.0f} — below ${MIN_TVL:,}; exit moves the price")

    # 5. turnover — ONLY if volume data exists.
    # 62% of pools have no volumeUsd7d. A missing field is not evidence of a
    # dead pool; it is absence of data. Flagging it caused 10,453 false DEADs.
    turn = None
    if v7 and tvl > 0:
        turn = (v7/7)/tvl
        if turn < MIN_TURNOVER:
            fails.append("DEAD")
            reasons.append(f"daily turnover {turn*100:.2f}% of TVL — fees barely accrue")
    elif not v7 and tvl > 0:
        reasons.append("volume data unavailable — turnover unverified")

    # 6. PLAUSIBILITY — a stable/synthetic USD pool above 25% organic is not
    # a lending rate, it is credit or leverage risk in disguise. Found by
    # testing: "concrete/CTCOLBUSD1" at 101.65% base passed every other check.
    sym=str(p.get("symbol","")).upper()
    stableish = p.get("stablecoin") is True or any(k in sym for k in ("USD","USDC","USDT","DAI","EURC"))
    if stableish and base > MAX_STABLE_BASE:
        fails.append("IMPLAUSIBLE")
        reasons.append(f"{base:.1f}% organic on a stable asset is too high for a fee rate; "
                       f"suggests credit, leverage or illiquid exposure")

    # history
    if count < MIN_DAYS_TRACKED:
        fails.append("NEW")
        reasons.append(f"only {count} days of history — no basis for the 7d or 30d checks")

    # 7. NO YIELD — a pool paying zero is not a yield opportunity, whatever else it is.
    # Found by testing: 590 of 1,891 pools labelled REAL had apy == 0 (31%), including a
    # $3.7B wstETH pool. Technically "organic" (zero emissions) but there is no yield to
    # underwrite. Calling that REAL misleads the reader, so it gets its own verdict.
    if apy <= 0:
        fails.append("NO_YIELD")
        reasons.append(f"pays {apy:.2f}% — no yield to underwrite, whatever its other merits")

    # verdict
    if "NO_YIELD" in fails:
        verdict = "NO_YIELD"
    elif not fails:
        verdict = "REAL"
    elif set(fails) <= {"NEW"}:
        verdict = "PROMISING"
    elif "SUBSIDISED" in fails and len(fails) <= 2:
        verdict = "MIXED"
    else:
        verdict = "AVOID"

    return dict(verdict=verdict, fails=fails, reasons=reasons,
                apy=apy, base=base, rew=rew, apy7=apy7, tvl=tvl,
                turnover=turn, sigma=sigma, il7d=il7,
                # THE FEED'S OWN PRIMARY KEY. Carried so two snapshots can be joined on
                # something stable. Without it the diff falls back to (chain, project, symbol),
                # which silently COLLAPSES two distinct pools sharing a ticker -- two real pools
                # counted as one, and a re-classification between them invisible. DefiLlama
                # already publishes `pool`; dropping it was the mistake.
                pool=p.get("pool"),
                chain=p.get("chain"), project=p.get("project"),
                symbol=p.get("symbol"), count=count,
                reward_share=(rew/apy if apy else 0))

def fetch(url):
    r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read().decode())

if __name__ == "__main__":
    d = fetch("https://yields.llama.fi/pools")["data"]
    print(f"scanning {len(d):,} pools\n")
    res = [screen(p) for p in d]
    from collections import Counter
    print("=== VERDICTS ===")
    for v,c in Counter(r["verdict"] for r in res).most_common():
        print(f"  {v:<10} {c:>6,}")
    print("\n=== FAILURE REASONS ===")
    fl=Counter(f for r in res for f in r["fails"])
    for f,c in fl.most_common():
        print(f"  {f:<12} {c:>6,}")
    # ---- APPEND-ONLY SNAPSHOT + ATOMIC POINTER ----
    #
    # This used to be `json.dump(res, open("screener/results.json","w"))`. Every run OVERWROTE the
    # previous screen, so a "yesterday vs today" comparison had no baseline to read -- the file it
    # would have compared against no longer existed. Deltas were therefore unfalsifiable, which is
    # how an inverted finding ("19 pools bled out" when 49 FEWER pools were dead) went unnoticed.
    #
    # Two things are fixed, and they are separate:
    #
    #  1. APPEND-ONLY. The payload is written once to snapshots/<ts>.json and never rewritten.
    #     history/ is the same idea for lending; this brings the AMM half in line.
    #  2. ATOMIC POINTER. results.json becomes a RELATIVE symlink to the newest snapshot, swapped
    #     with os.replace on a temp NAME. `json.dump` to a live path has a window where a reader
    #     sees a half-written file; a rename has none. A reader either opens the old snapshot or
    #     the new one, both complete.
    #
    # RELATIVE, NOT ABSOLUTE. os.path.getmtime() FOLLOWS symlinks and build_v2.py derives the AMM
    # age from results.json's mtime. A relative link resolves against the link's own directory, so
    # the link stays valid if the tree is moved or bind-mounted, and getmtime still reaches the
    # snapshot. An absolute link would silently pin a path.
    import os as _os, datetime as _dt
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _snapdir = _os.path.join(_here, "snapshots")
    _os.makedirs(_snapdir, exist_ok=True)
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rel = _os.path.join("snapshots", ts + ".json")
    final = _os.path.join(_here, rel)

    # Collision would silently destroy a snapshot. The 6-hour timer makes it near-impossible, but
    # a manual re-run inside the same second is ordinary, so refuse rather than overwrite.
    if _os.path.exists(final):
        _n = 1
        while _os.path.exists(_os.path.join(_here, "snapshots",
                                            "%s.%d.json" % (ts, _n))):
            _n += 1
        rel = _os.path.join("snapshots", "%s.%d.json" % (ts, _n))
        final = _os.path.join(_here, rel)
        print(f"NOTE: a snapshot already existed for {ts}; wrote {rel} instead of overwriting")

    # write the payload to a temp name in the SAME directory, then rename. Same-filesystem rename
    # is atomic; a temp in /tmp could land on another device and degrade to a copy.
    tmp = final + ".tmp"
    with open(tmp, "w") as f:
        json.dump(res, f)
        f.flush()
        _os.fsync(f.fileno())          # durability: a crash must not leave a truncated snapshot
    _os.replace(tmp, final)

    ptr = _os.path.join(_here, "results.json")
    ptmp = ptr + ".tmp"
    # remove a stale temp POINTER if one was left by an interrupted run. os.path.lexists, not
    # exists: a broken symlink answers False to exists() and would be left behind for ever.
    if _os.path.lexists(ptmp):
        _os.unlink(ptmp)
    _os.symlink(rel, ptmp)
    _os.replace(ptmp, ptr)             # atomic: readers see old or new, never a half-written file

    print(f"\nsaved {len(res):,} screened pools")
    print(f"  snapshot (append-only): {rel}")
    print(f"  results.json -> {rel}")

#!/usr/bin/env python3
"""dex_pools.py - DEX pool fee/volume feed, closing the vault venue gap.

WHY THIS EXISTS. Aegis's venues.json indexes 2,641 lending pools and zero DEX pools. But the
vault deploys borrowed USDC into Aerodrome (a DEX), not a lending market. The whitelist therefore
had a blind spot: the exact place the vault deploys was invisible to its gatekeeper.

This answers the question the lending feed cannot: which DEX pool earns the most fees, and is it
a REAL venue.

DATA SOURCE. GeckoTerminal public pool feed (/networks/base/pools). Per pool it carries:
    name            -> "AERO / cbBTC 0.6%" (fee tier is IN the name)
    address, dex_id, volume_usd.h24, reserve_in_usd
No fee field, so fee is DERIVED as volume * tier. That is an LP swap-fee estimate, not yield.

RATE LIMIT. Free tier ~30 req/min. Fetch is bounded + cached, so queries do not re-hit network.

Run:  python3 dex_pools.py            write dex_pools.json
      python3 dex_pools.py --selftest
"""
import json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dex_pools.json")
CACHE = os.path.join(HERE, "dex_pools_cache.json")
BASE_URL = "https://api.geckoterminal.com/api/v2/networks/base/pools"

MAX_PAGES = 3
CACHE_TTL = 300
MIN_VOLUME_24H = 1_000.0
TARGET_DEXES = {"aerodrome", "aerodrome-v1", "aerodrome-slipstream",
                "uniswap-v3", "uniswap-v4"}


def _ua():
    return {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _parse_tier(name):
    m = re.search(r"([0-9.]+)\s*%", name or "")
    return float(m.group(1)) / 100.0 if m else None


def fetch_pools(max_pages=MAX_PAGES):
    if os.path.exists(CACHE):
        try:
            d = json.load(open(CACHE))
            if time.time() - d.get("_fetched", 0) < CACHE_TTL:
                return d.get("pools", [])
        except Exception:
            pass
    pools = []
    for page in range(1, max_pages + 1):
        req = urllib.request.Request("%s?page=%d" % (BASE_URL, page), headers=_ua())
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        except Exception as e:
            print("dex_pools: page %d fetch failed (%s)" % (page, e), file=sys.stderr)
            break
        batch = d.get("data", []) or []
        if not batch:
            break
        pools.extend(batch)
        time.sleep(1.1)
    json.dump({"_fetched": time.time(), "pools": pools}, open(CACHE, "w"))
    return pools


def _num(v):
    try:
        f = float(v)
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0


def build(pools):
    rows = []
    for p in pools:
        a = p.get("attributes", {}) or {}
        name = a.get("name", "")
        tier = _parse_tier(name)
        vol = _num((a.get("volume_usd") or {}).get("h24"))
        if tier is None or vol < MIN_VOLUME_24H:
            continue
        rel = p.get("relationships", {}) or {}
        dex_id = ((rel.get("dex") or {}).get("data") or {}).get("id")
        rows.append({
            "name": name, "address": a.get("address"), "dex_id": dex_id,
            "fee_tier": tier, "volume_24h_usd": vol, "fee_24h_usd": vol * tier,
            "reserve_usd": _num(a.get("reserve_in_usd")),
            "target_dex": bool(dex_id and dex_id in TARGET_DEXES),
        })
    rows.sort(key=lambda r: -r["fee_24h_usd"])
    return rows


def write(rows):
    out = {
        "source": "geckoterminal /networks/base/pools",
        "fetched_at": time.time(),
        "note": "fee_24h_usd = 24h volume * fee tier; an LP swap-fee estimate, not depositor yield",
        "count": len(rows),
        "top_fee_pool": rows[0] if rows else None,
        "pools": rows,
    }
    json.dump(out, open(OUT, "w"), indent=1)
    return out


def load():
    if os.path.exists(OUT):
        return json.load(open(OUT))
    return None


def selftest():
    ok = True
    def check(name, got, want):
        nonlocal ok
        good = got == want
        print("  %-58s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False
    check("0.6% tier parses", _parse_tier("AERO / cbBTC 0.6%"), 0.006)
    check("0.01% tier parses", _parse_tier("xdp / USDC 0.01%"), 0.0001)
    check("1% tier parses", _parse_tier("BRETT / WETH 1%"), 0.01)
    check("no tier -> None", _parse_tier("AERO / USDC"), None)
    fake = [{"attributes": {"name": "A / B 0.6%", "volume_usd": {"h24": "10000"}},
             "relationships": {"dex": {"data": {"id": "aerodrome"}}}},
            {"attributes": {"name": "C / D 0.3%", "volume_usd": {"h24": "10000"}},
             "relationships": {"dex": {"data": {"id": "uniswap-v3"}}}}]
    rows = build(fake)
    check("0.6% pool ranked first", rows[0]["name"], "A / B 0.6%")
    check("0.6% fee = 10000*0.006", round(rows[0]["fee_24h_usd"], 2), 60.0)
    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    rows = build(fetch_pools())
    out = write(rows)
    print("dex pools ranked by 24h fee: %d" % out["count"])
    for r in out["pools"][:10]:
        print("  %-30s %12s vol  %9s fees  %5.2f%%" % (
            r["name"][:30], format(r["volume_24h_usd"], ",.0f"),
            format(r["fee_24h_usd"], ",.0f"), r["fee_tier"] * 100))

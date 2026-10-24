#!/usr/bin/env python3
"""morpho_fetch.py - read-only Morpho Blue market ingestion (Base, USDC-denominated).

SCHEMA NOTE: field names were verified against the live API, not taken from a spec.
The prompt that commissioned this used `uniqueKey`, `lltv` as a percent, and `rewardApy`.
None of those exist. What is real:

    marketId                      (not uniqueKey)
    lltv                          BigInt, divide by 1e18 to get a fraction
    state.netSupplyApy            ALREADY nets rewards against organic; no separate rewardApy
    state.supplyApy               organic
    badDebt { usd }               current cumulative, NOT historical
    realizedBadDebt { usd }       current cumulative, NOT historical
    warnings { type level }       Morpho's own risk flags - consumed, not re-derived

Everything here is READ-ONLY. No keys, no signing, no transactions.

Run:  python3 morpho_fetch.py            # writes morpho_markets.json
"""
import json, os, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "morpho_markets.json")
API = "https://blue-api.morpho.org/graphql"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

CHAIN_BASE = 8453
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WAD = 10 ** 18

QUERY = """
query Markets($chain: [Int!], $loan: [String!], $n: Int!) {
  markets(first: $n, where: {chainId_in: $chain, loanAssetAddress_in: $loan},
          orderBy: SupplyAssetsUsd, orderDirection: Desc) {
    items {
      marketId
      lltv
      oracle { address type }
      collateralAsset { symbol address }
      loanAsset { symbol address }
      warnings { type level }
      badDebt { usd underlying }
      realizedBadDebt { usd underlying }
      state {
        supplyAssetsUsd borrowAssetsUsd collateralAssetsUsd liquidityAssetsUsd
        utilization supplyApy netSupplyApy borrowApy
        blockNumber timestamp
      }
    }
  }
}
"""

HISTORY_QUERY = """
query Hist($chain: Int!, $id: String!) {
  marketById(chainId: $chain, marketId: $id) {
    marketId lltv
    collateralAsset { symbol price { usd } historicalPriceUsd { x y } }
    historicalState {
      utilization { x y }
      supplyApy { x y }
      netSupplyApy { x y }
      liquidityAssetsUsd { x y }
      collateralAssetsUsd { x y }
    }
  }
}
"""


def gql(query, variables, timeout=30):
    body = json.dumps({"query": query, "variables": variables}).encode()
    r = urllib.request.Request(API, data=body, headers=dict(UA, **{"Content-Type": "application/json"}))
    try:
        j = json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError("GraphQL HTTP %s: %s" % (e.code, e.read().decode()[:300]))
    if j.get("errors"):
        raise RuntimeError("GraphQL errors: %s" % json.dumps(j["errors"])[:300])
    return j.get("data") or {}


def fetch_markets(n=100):
    d = gql(QUERY, {"chain": [CHAIN_BASE], "loan": [USDC_BASE], "n": n})
    return ((d.get("markets") or {}).get("items")) or []


def fetch_history(market_id):
    d = gql(HISTORY_QUERY, {"chain": CHAIN_BASE, "id": market_id})
    return d.get("marketById")


def num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def normalize(m):
    """Morpho market -> the flat shape the screen consumes. All unit conversions live here."""
    st = m.get("state") or {}
    ca = m.get("collateralAsset") or {}
    lltv_raw = m.get("lltv")
    lltv = (int(lltv_raw) / WAD) if lltv_raw is not None else None

    net_apy = num(st.get("netSupplyApy"))
    org_apy = num(st.get("supplyApy"))
    util = num(st.get("utilization"))

    # the screen works in PERCENT; Morpho returns FRACTIONS. Convert once, here.
    apy_pct = (net_apy * 100.0) if net_apy is not None else 0.0
    org_pct = (org_apy * 100.0) if org_apy is not None else 0.0

    warns = m.get("warnings") or []
    red = [w.get("type") for w in warns if str(w.get("level", "")).upper() == "RED"]
    yellow = [w.get("type") for w in warns if str(w.get("level", "")).upper() == "YELLOW"]

    return {
        "market_id": m.get("marketId"),
        # provenance anchor: the block the DATA describes, not the block when we asked
        "block_number": st.get("blockNumber"),
        "block_timestamp": st.get("timestamp"),
        "collateral": ca.get("symbol"),
        "collateral_address": ca.get("address"),
        "loan": (m.get("loanAsset") or {}).get("symbol"),
        "oracle": (m.get("oracle") or {}).get("address"),
        "oracle_type": (m.get("oracle") or {}).get("type"),
        "lltv": lltv,
        "tvl_usd": num(st.get("supplyAssetsUsd")) or 0.0,
        "borrow_usd": num(st.get("borrowAssetsUsd")) or 0.0,
        "liquidity_usd": num(st.get("liquidityAssetsUsd")) or 0.0,
        "collateral_usd": num(st.get("collateralAssetsUsd")) or 0.0,
        "utilization": util,
        "supply_apy": org_pct,
        "net_apy": apy_pct,
        "bad_debt_usd": num((m.get("badDebt") or {}).get("usd")) or 0.0,
        "realized_bad_debt_usd": num((m.get("realizedBadDebt") or {}).get("usd")) or 0.0,
        "warnings_red": red,
        "warnings_yellow": yellow,
    }


def main():
    n = 100
    if "--top" in sys.argv:
        n = int(sys.argv[sys.argv.index("--top") + 1])
    print("fetching Morpho Blue USDC markets on Base (chain %d)..." % CHAIN_BASE, flush=True)
    raw = fetch_markets(n)
    print("  %d markets returned" % len(raw), flush=True)
    rows = [normalize(m) for m in raw]

    # every ingest is stamped. provenance at the root of each row so it survives isolation.
    try:
        import provenance
        blk = provenance.block_from_rows(rows)
        stamped, prov = provenance.stamp(rows, API, block_number=blk)
        rows = stamped
        print("  provenance: block %s, %d rows, sha %s"
              % (blk, prov["row_count"], prov["content_sha256"][:12]), flush=True)
    except Exception as e:
        print("  [provenance not stamped: %s]" % str(e)[:60], flush=True)

    json.dump(rows, open(OUT, "w"), indent=1)
    print("wrote %s" % OUT, flush=True)
    return rows


if __name__ == "__main__":
    rows = main()
    print("\n%-12s %8s %9s %8s %9s %11s" % ("collateral", "LLTV", "TVL$M", "util", "netAPY", "badDebt$"))
    for r in rows[:25]:
        print("%-12s %8s %9.1f %8s %8.2f%% %11s" % (
            str(r["collateral"])[:11],
            ("%.1f%%" % (r["lltv"] * 100)) if r["lltv"] is not None else "?",
            r["tvl_usd"] / 1e6,
            ("%.1f%%" % (r["utilization"] * 100)) if r["utilization"] is not None else "?",
            r["net_apy"],
            "{:,}".format(int(r["bad_debt_usd"])),
        ))

#!/usr/bin/env python3
"""Pool -> explorer link resolution.

REALITY CHECK (measured):
  DefiLlama's 'pool' field is a UUID (e.g. 6f00d46b-...), NOT a contract address.
  -> it gives an exact defillama.com/yields/pool/<uuid> link, which is correct and stable.
  underlyingTokens[] DOES contain real contract addresses.

  GeckoTerminal URLs accept chain SLUGS, not DefiLlama chain names:
    'eth' worked; 'ethereum' 404'd for a token page. Mapping is required, not guessed.
  DexScreener/GeckoTerminal token pages need a contract address, not a pool uuid.

MISLABELLING FIXED HERE. These links were rendered as pills labelled "GT" and "DS", which
reads as "the GeckoTerminal/DexScreener page for THIS pool". They are not. They open the page
for the UNDERLYING TOKEN, because DefiLlama publishes no pool address anywhere:

  * `pool` is a UUID (6f00d46b-...), not an address.
  * `/chart/<uuid>` returns only apy/tvl history -- verified: no address field at any point.
  * underlyingTokens[] holds real contract addresses, which is what these URLs carry.

A DexScreener path of the form /<chain>/<address> is documented as a PAIR page, so putting a
token address in the pair slot is the specific mislabel: it either misses the intended pool or
lands on a token page under a label that promised a pair. GeckoTerminal resolves its
/tokens/<addr> form correctly, and that page does show the pools the token trades in.

The labels now say which surface each link opens. Resolving a true per-pool address would need
one GeckoTerminal API call per pool at build time (~3,400 calls), which is not worth it for a
static audit page -- and DefiLlama cannot supply it at all.
"""
GT_CHAIN = {
 "Ethereum":"eth", "Base":"base", "Arbitrum":"arbitrum", "Optimism":"optimism",
 "Polygon":"polygon_pos", "BSC":"bsc", "Avalanche":"avalanche", "Solana":"solana",
 "Flare":"flare", "Songbird":"songbird", "Gnosis":"xdai", "Fantom":"ftm",
 "Celo":"celo", "Sonic":"sonic", "Sui":"sui", "Aptos":"aptos", "TON":"ton",
 "Tron":"tron", "Bitcoin":"bitcoin", "Monad":"monad", "Plume Mainnet":"plume",
 "Hyperliquid":"hyperevm", "Ink":"ink", "Soneium":"soneium", "World Chain":"world-chain",
 "Mantle":"mantle", "Linea":"linea", "Scroll":"scroll", "zkSync Era":"zksync",
 "Blast":"blast", "Manta":"manta-pacific", "Aurora":"aurora", "Cronos":"cronos",
 "Kaia":"kaia", "Astar":"astar", "Moonbeam":"moonbeam", "Plasma":"plasma",
}
DEXSCREENER_CHAIN = {
 "Ethereum":"ethereum","Base":"base","Arbitrum":"arbitrum","Optimism":"optimism",
 "Polygon":"polygon","BSC":"bsc","Avalanche":"avalanche","Solana":"solana",
 "Flare":"flare","Gnosis":"gnosischain","Fantom":"fantom","Celo":"celo",
 "Sonic":"sonic","Sui":"sui","TON":"ton","Tron":"tron","Monad":"monad",
 "Hyperliquid":"hyperevm","Ink":"ink","Mantle":"mantle","Linea":"linea",
}

def defillama_link(pool_uuid):
    if not pool_uuid: return None
    return f"https://defillama.com/yields/pool/{pool_uuid}"

NULL_ADDRS = {"0x" + "0"*40, "0x0000000000000000000000000000000000000000", ""}

def _ok_addr(a):
    """Reject null/zero addresses — staked-ETH pools (STETH, WBETH, WEETH) publish
    0x000...000 as the underlying token, which would produce a broken explorer link."""
    if not a: return False
    a=str(a).strip().lower()
    if a in NULL_ADDRS: return False
    if a == "0x" + "0"*40: return False
    if set(a.replace("0x","")) == {"0"}: return False
    return len(a)==42 and a.startswith("0x")

def geckoterminal_token(chain, token_addr):
    """GeckoTerminal TOKEN page. Resolves correctly; shows the pools the token trades in."""
    slug = GT_CHAIN.get(chain)
    if not slug or not _ok_addr(token_addr): return None
    return f"https://www.geckoterminal.com/{slug}/tokens/{token_addr}"

def geckoterminal_pool_by_tokens(chain, tokens):
    """GT cannot address a pool by uuid; token page is the reliable target."""
    if not tokens: return None
    for t in tokens:
        if _ok_addr(t): return geckoterminal_token(chain, t)
    return None

def dexscreener_token(chain, token_addr):
    """DexScreener path built from a TOKEN address.

    NOTE: DexScreener's /<chain>/<address> form is a PAIR page. This function puts a token
    address in that slot, so the label must not claim it opens the pool. Kept because the
    link is still useful -- DexScreener redirects a known token to its page -- but it is
    rendered as "DS token" and carries a title saying so.
    """
    slug = DEXSCREENER_CHAIN.get(chain)
    if not slug or not _ok_addr(token_addr): return None
    return f"https://dexscreener.com/{slug}/{token_addr}"

def dexscreener_search(symbol):
    if not symbol: return None
    from urllib.parse import quote
    return f"https://dexscreener.com/search?q={quote(str(symbol))}"

def link_set(rec):
    """Link set for one screened pool record (needs pool/underlyingTokens merged in).

    ONLY DefiLlama. The GeckoTerminal and DexScreener links were removed on request, and they
    were never what they looked like anyway: DefiLlama publishes no pool address, so both
    resolved to the *underlying token* rather than the pool, and every label needed a title
    explaining that. Two links that need a disclaimer to not mislead are not worth three
    columns of noise -- and they cost 736KB (27%) of the inlined JSON blob.

    DefiLlama is the one link that addresses the POOL itself, which is what the row is about.
    The protocol's official site is added at render time from the protocol registry, and is
    per-protocol, so it is not carried per-row here.

    The builders below are kept: `geckoterminal_token` / `dexscreener_token` / `dexscreener_search`
    are still used by mcp_server.py's response shape and by build_report.py, and the GT_CHAIN /
    DEXSCREENER_CHAIN slug maps cost nothing. Deleting them would break those two callers.
    """
    return dict(
        defillama = defillama_link(rec.get("pool")),
    )

if __name__=="__main__":
    import json,urllib.request
    r=urllib.request.Request("https://yields.llama.fi/pools",headers={"User-Agent":"Mozilla/5.0"})
    raw=json.loads(urllib.request.urlopen(r,timeout=30).read().decode())["data"]
    print("=== link generation on real pools ===")
    for x in raw[:3]:
        rec=dict(chain=x.get("chain"),symbol=x.get("symbol"),pool=x.get("pool"),
                 underlyingTokens=x.get("underlyingTokens"))
        print(f"\n  {rec['chain']} / {rec['symbol']}")
        for k,v in link_set(rec).items():
            print(f"    {k:<20} {v}")
    # coverage
    have=sum(1 for x in raw if x.get("underlyingTokens"))
    print(f"\n  pools with a token address for explorer links: {have:,}/{len(raw):,} ({100*have/len(raw):.0f}%)")
    haveu=sum(1 for x in raw if x.get("pool"))
    print(f"  pools with a defillama uuid link:            {haveu:,}/{len(raw):,} ({100*haveu/len(raw):.0f}%)")

# The product: links, paste field, and an MCP with a 402

Three features built and tested.

## 1. Clickable pool links — and a data problem solved

**Problem found immediately:** DefiLlama's `pool` field is a **UUID**, not a contract address.

```
pool: "6f00d46b-8735-49ae-9ced-2a0fccc56ad0"
```

So there is no pool contract address to link to. What is available:

| source | gives | usable for |
|---|---|---|
| `pool` (UUID) | exact DefiLlama page | `defillama.com/yields/pool/<uuid>` |
| `underlyingTokens[]` | **real contract addresses** | GeckoTerminal + DexScreener token pages |

**Chain slugs are not the same as DefiLlama chain names** — I tested this rather than assuming:
`eth` worked, `ethereum` 404'd for a token page. So `links.py` carries an explicit map for 38 chains.

**Bug caught by testing:** staked-ETH pools (STETH, WBETH, WEETH) publish **`0x000...000`** as their
underlying token, which generated a broken GeckoTerminal link. Fixed with a null-address guard; those
pools now fall back to a DexScreener symbol search instead of a dead link.

**Every row now carries:** `DL` (DefiLlama) · `GT` (GeckoTerminal token) · `DS` (DexScreener
token) · `search`. Verified across 81 rows: **81 DL, 71 GT, 67 DS, 81 search** — GT/DS omitted only
where the address is null.

## 2. Paste-a-link field with a client-side auditor

The `<script type="module">` block embeds a **JS port of the six checks** (`audit_core.js`) plus
**3,410 pool records**, so the page audits without a backend.

**Paste handling:**
- a **symbol** (`WETH-USDC`) → looks up the embedded set, returns verdict + every reason
- a **contract address** → explained honestly: *"this static page has no backend, paste the symbol
  or connect the MCP endpoint"*
- a **GeckoTerminal / DexScreener URL** → parses chain and address, same honest message

**The JS port was tested against four cases and matches the Python exactly:**

```
clean pool          -> REAL    [none]
subsidised          -> MIXED   [SUBSIDISED,DEAD]
outlier 24%         -> AVOID   [OUTLIER]       "spot 24.00% vs 7d-base 9.10%"
implausible stable  -> AVOID   [DEAD,IMPLAUSIBLE]
```

**Size:** embedding all 16,830 pools made a **5.8MB** file. Trimmed to REAL/PROMISING/MIXED plus
anything over $1M TVL → **1.09MB**, 3,410 pools.

## 3. MCP server with a 402 paywall

`screener/mcp_server.py` — HTTP JSON-RPC on port 8010.

```
GET  /health     liveness, no auth
GET  /pricing    the 402 terms, no auth
POST /resolve    link | address | symbol -> pool record + links
POST /audit      the six checks -> verdict
POST /purchase   issue a prepaid token (UNSETTLED — demo only)
```

**You were right about the mechanism:** *"agents can view ads lol"* — they can't. **An agent cannot
click a banner, so a paywall is the correct monetisation for an agent-facing API where advertising
works for a human-facing page.**

**Pricing:** **$0.02/audit, 3 free per day** (so an agent can verify the output is real before paying).

### Tested end-to-end, not asserted

```
/health         200  free=3/day  $0.02/audit
/resolve STETH  200  links: defillama, geckoterminal, dexscreener, dexscreener_search

free tier:
  call 1: 200  verdict=REAL   free_used=1
  call 2: 200  verdict=REAL   free_used=2
  call 3: 200  verdict=REAL   free_used=3
  call 4: 402  payment_required

the 402 body:
  {"error":"payment_required","price_usd":0.02,"free_limit":3,
   "how":"POST /purchase (not yet settled)",
   "note":"token store is in-memory; wire x402/Base USDC before charging"}

paid path:
  /purchase -> token, 5 credits
  call 1: 200  credits_left=4
  call 2: 200  credits_left=3
```

**The paywall fires, the free tier works, and the token bypass works.**

## What is honestly NOT done

**The settlement is not real.** `/purchase` issues a token without verifying any payment, and the
token store is **in-memory — it resets on restart.** I labelled it `UNSETTLED — no payment was
verified. Demo only.` in the response itself so nobody mistakes it for live.

**To charge anyone, you need:**
1. **x402** (HTTP 402 native payments, which is exactly this use case) or a Base USDC acceptance step
2. a **persistent store** for tokens and usage
3. a **rate limit that survives restart**

**Also not done:** the address path in the browser tool (needs a backend or RPC), and Gemma-written
verdicts (endpoint is reachable at `100.90.251.75:11434` — two-line change, not yet wired).

## Deployment note — the bug from last time

**The report is now written to `/workspace`,** which is what the preview serves. Last round I served
it only on the VPS at `127.0.0.1:8099` and reported success — it worked, and you couldn't see it.

**Verified this time:**
```
/workspace/index.html   1,089,226 bytes
preview :8000 -> HTTP 200, Content-Length 1089226
  "Audit a pool"     present
  ">DL<" links       present
  "function audit("  present
```

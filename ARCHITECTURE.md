# ARCHITECTURE.md — the system contract

Read this before proposing any change. If your plan contradicts a line here, either the line is
stale (update it with a DECISIONS.md entry) or the plan is wrong. Not both true at once.

**Last verified:** 2026-10-11 · every command and path below was executed or read directly, not
recalled.

---

## What Aegis IS

A deterministic, read-only risk screen for Morpho Blue lending markets on Base (chain 8453),
plus an auditable evaluation pipeline around it. Five phases per cycle:

```
SENSE      read-only Morpho GraphQL fetch
EVALUATE   hermetic seven-check screen, no model
REASON     optional LLM triage, opt-in via --reason, labelled in the run
COMMIT     immutable runs/<utc-isolated>/ directory, checksummed
VERIFY     replay the screen from stored input, must reproduce byte-for-byte
```

## What Aegis is NOT

Not a predictor. Not a trading system. Not a vault. **No signing, no chain writes, no key**
anywhere in the repo. Measured results (2026-10-08) back this:

- flags do not predict loss: n=122, FLAGGED 52.4% vs PASSED 43.8%, overlapping CIs
- liquidations hit REAL-verdict markets by design (1,260 of 1,261 covered events) — they are the
  mechanism of lending, not screen failures
- timing strategies lose to buy-and-hold: corr(asset return, strategy alpha) = −0.996 over 45 runs
- in-range time is anti-correlated with profit at −0.923 — never adopt it as an objective

## Stack

| layer | choice | note |
|---|---|---|
| language | Python 3.12 (`/usr/bin/python3`), stdlib-first | no numpy, no pandas in the core path |
| transport | `urllib.request` serial, 1.2s sleeps | concurrency is what triggered 600/600 HTTP 429s |
| data | flat JSON in `runs/<iso>/`, immutable, checksummed | replayable without any database |
| UI | single generated `report.html` (~3.1MB, zero external requests), 15 tabbed sections | `build_v2.py` renders it; every table is its own `data-section` + tab |
| tests | own runner (`run_tests.sh`), 883 assertions / 34 suites | `pytest` collects 0 of them — do not switch |
| server | `serve_preview.py` on **8099** (gzip static) | tailscale serves it, tailnet-only |
| LLM | Ollama at `http://100.90.251.75:11434`, `gemma3:12b` | see the model table below |

**Zero external frontend requests** is a tested property (`test_export_report.cjs`): no CDN, no
webfonts, no token logos. Do not add any.

## The model: gemma3:12b, and why

`aegis_run.py:26-60` records the measurements. The short version:

| model | budget | resp | thinking | verdict |
|---|---|---|---|---|
| `gemma4:12b` | 2048-4096 | **0** | 5453-8560 | reasons until budget dies; output lands elsewhere |
| `gemma3:12b` | 512 | 432 | 0 | default; 6.7x faster, does not reason |

`gemma4` is **not broken** — an earlier "RETURNS EMPTY STRINGS" note was a wrong diagnosis that
cost a cycle. It *reasons* into the budget and writes chain-of-thought to a **separate
`thinking` field**. If a future prompt needs reasoning, set `AEGIS_NUM_PREDICT=4096` and read the
right field. Env pins: `AEGIS_OLLAMA`, `AEGIS_MODEL`, `AEGIS_NUM_PREDICT`, `AEGIS_MODEL_FALLBACK`.

## Layout, and the ONE rule that protects it

```
aegis/
├── aegis_loop.py        # THE entry point: preflight → run → verify → publish → log
├── aegis_run.py         # one cycle, PROMPT_VERSION + ORCHESTRATOR_INITIATOR
├── provenance.py        # runs/, write_run(), verify_run(); _sha() content hashes
├── allocator.py         # 5 rules, SIMULATION ONLY; 30% collateral cap, 15% reserve
├── lending_screen.py    # the 7 checks + volatility enrichment (sigma_to_breach)
├── morpho_fetch.py      # GraphQL ingest, normalize() owns ALL unit conversions
├── run_history.py / alert_diff.py / publish.py / runway.py / regimes.py
├── portfolio_corr.py    # pairwise-complete covariance diagnostic → screener/portfolio_corr.json
├── liquidations.py      # liquidation ingest → screener/liquidations.json (30,934 events)
├── screener/            # dashboard: build_v2.py, table.js, app.js, venues.py, dex_pools.py
│                        #   dex_pools.py = DEX fee/volume feed → dex_pools.json (GeckoTerminal)
├── tests/               # run_tests.sh runs every test_*.py / test_*.cjs directly
└── runs/<iso>/          # immutable: markets/screen/meta/allocator/orchestrator.json
```

**THE RULE — the one worth more than the rest of this file:**

`_HERE = os.path.dirname(os.path.abspath(__file__))` does **not follow symlinks**. Most screener
modules are symlinks into the root. Invoke through `screener/` and writes land in `screener/` —
splitting the log, forking `runs/`, and breaking `run_history.py` silently. **Invoke root paths
(`python3 aegis_loop.py`), never `screener/aegis_loop.py`.** Measured 2026-10-08: it produced two
log files, a shadow `screener/audits/`, and 12 writer modules with the latent path bug. Fixing it
in all 12 needs `realpath`; it is NOT yet done and is the standing known-debt item.

**Duplication rule:** edit ROOT files, then copy to `screener/`. `build_v2.py` resolves imports
from `screener/` FIRST, and drift has bitten twice (index.html served 8h stale; two stylesheet
systems). `report.html` and `screener/index.html` are checked byte-identical by the suite.

## Ports and services

| service | what |
|---|---|
| `aegis-preview.service` | static gzip server on **8099**, `serve_preview.py` |
| `aegis-forward.timer` | the production cycle every 15 min, `flock`-guarded |
| `aegis-amm.timer` | DefiLlama AMM snapshot → `screener/results.json` |
| tailscale | `https://srv1619135.tailf16ee8.ts.net` → 8099, tailnet only |

`aegis-test.{service,timer}` was cleaned up (2026-10-08). The app-preview `/workspace` is a
DIFFERENT empty directory — publish to both locations separately, never assume one covers the other.

## Invariants the suite pins

1. **Report and `screener/index.html` byte-identical** (`test_no_shadow_tree.py`).
2. **Zero external requests** — no `<img>`, no CDN, no webfonts in report.html.
3. **Replay must reproduce** — `provenance.py --verify <basename>` (NOT `runs/<basename>`; the
   tool prefixes `runs/` itself and the prompt's older form double-prefixes it).
4. **A run records the orchestrator initiator** (version, sha256, full text) in
   `orchestrator.json` + `provenance.orchestrator`, on every run including no-`--reason` ones.
5. **No silent zero.** The suite fails loudly if a suite passes reporting 0 assertions.
6. **Units travel with the data.** `normalize()` converts once; anything dividing by 1e6
   unconditionally produced "$1.4T seized in 30 minutes" and would again.

## Data sources

| source | endpoint | note |
|---|---|---|
| Morpho GraphQL | `https://blue-api.morpho.org/graphql` | POST, JSON; fieldnames differ from any spec: `marketId` (not uniqueKey), `lltv` BigInt÷1e18, `state.netSupplyApy` already nets rewards |
| liquidations | same API, `marketTransactions(type_in:[Liquidation])` | `seizedAssets` in COLLATERAL decimals, `repaidAssets`/`badDebtAssets` in LOAN decimals |
| DefiLlama feeds | yields `/pools`, protocols registry for category joins | 16,684 pools map to venues via slug join |
| Base RPC | publicnode/drpc rotation | **drpc free tier caps getLogs at 100 blocks** — index via API, not via logs |
| price cache | `screener/price_cache.json` | 61 series, 31 all-null (unpublished collaterals: HERMES etc.), refetched every cycle |
| GeckoTerminal | `api.geckoterminal.com/api/v2/networks/base/pools` | DEX pool feed for `dex_pools.py`; free tier ~30 req/min, so fetch is bounded+cached. `fee_24h = volume × fee tier` (parsed from the pool name), an LP-fee estimate not depositor yield |

## The oracle-word warning

"Oracle" in this repo means **price-feed oracle** (a risk INPUT we distrust, e.g. USR's broken
Oracle), never a component we own, and never the LLM. If a plan says "oracle engine" it is
naming the wrong thing — the orchestrator is `aegis_loop.py` and the prompt contract is
`ORCHESTRATOR_INITIATOR` + `triage_prompt()` in `aegis_run.py`.

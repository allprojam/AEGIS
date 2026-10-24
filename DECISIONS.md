# DECISIONS.md — the architecture decision record

Append-only. One line per decision: `DATE | decision | why | status`. New sessions read the top;
locked entries are not re-litigated without a NEW decision that supersedes them explicitly
(that entry says "supersedes yyyy-mm-dd").

| date | decision | rationale | status |
|---|---|---|---|
| 2026-10-08 | **Flat JSON runs, no database** (SQLite/Postgres all declined) | replay verification without a service; `runs/<iso>/` is checksummed, rsync-able, and grep-able. A DB would make provenance a second system. | locked |
| 2026-10-08 | **No numpy/pandas in the core path** | the covariance and vol code are pure-stdlib; replay must work on a bare VPS. Portfolio_corr uses cyclic Jacobi, not an BLAS dep. | locked |
| 2026-10-08 | **`gemma3:12b` selected, `gemma4:12b` NOT broken** | gemma4 *reasons* into the budget and writes CoT to a separate field; earlier "RETURNS EMPTY" note was a wrong diagnosis. gemma3 is 6.7x faster and answers directly. Revisit only with `AEGIS_NUM_PREDICT>=4096` and reading `thinking`. | locked |
| 2026-10-08 | **Serial ingestion, 1.2s sleeps, no concurrency** | measured: 16 or 6 workers → 600/600 HTTP errors; serial + delay → 0. Applies to GraphQL and RPC both. | locked |
| 2026-10-08 | **Zero external frontend requests** | no CDN, no webfonts, no `<img>` logos; tested. The page works on a phone on a tailnet with no internet. | locked |
| 2026-10-08 | **pytest NOT adopted** | `pytest -v` collects 0 files (they are main()-driven, not `def test_`), prints "no tests ran", exits 0 — a green result for zero verification, the exact defect class the project fights. `run_tests.sh` runs each file directly and fails on silent zeros. | locked |
| 2026-10-08 | **Vault stays dead until a measured edge** | Gauntlet USDC Prime charges 0% on $413.9M; can't undercut 0%. "Flags already-stressed markets" ≠ "predicts loss". Phase 2/3 deliberately unbuilt. | locked |
| 2026-10-08 | **Two-table lending section (Morpho vs all-venues)** | no venue-agnostic source for utilisation/LLTV; one merged table would blank 4 columns for 2,581 of 2,641 rows. `test_venues.py` asserts the split. | locked |
| 2026-10-08 | **Addresses truncated in cells, full in tooltip+copy** (dense-table rule) | 182 full 42-char addresses in cells was the "wall of hashes"; data-full + click-to-copy keeps the reference one click away. | locked |
| 2026-10-08 | **Drawers add telemetry, never repeat the row** | the old drawer reprinted all visible columns; now `data-full`/`data-extra`-driven, column-walk fallback. | locked |
| 2026-10-08 | **Covariance model is diagnostic, not a sizing input (yet)** | pairwise-complete (5–108wk support), 0.25 shrinkage, PSD verified. Correlation COST 0.86% on this book; the optimizer pass (C2) is deliberately not built. | unlocked by C2 |
| 2026-10-08 | **Liquidations: publish the negative result** | 1,260/1,261 covered events hit REAL-verdict markets — mechanism, not screen failure. In-page note claims neither prediction nor rescue. | locked |
| 2026-10-08 | **`liquidations.py --incremental` in aegis_loop** (2 pages/tick) | 15-min ticks vs ~100 events/30min burst = current with headroom; failed sync never blocks the cycle. | locked |
| 2026-10-08 | **Morpho API over RPC for liquidations** | drpc free tier caps getLogs at 100 blocks; API gives typed events + decimals. | locked |
| 2026-10-08 | **`test_a11y.py` asserts rendered HTML, not source** | templated CSS + a brace bug = valid Python emitting broken CSS; the first build's `prefers-reduced-motion: 0` proved it. | locked |
| 2026-10-08 | **Root edits + `cp` to screener/ (no symlinks for build files)** | `build_v2.py` resolves imports from screener/ FIRST; drift bit twice (8h-stale index.html; twin design systems). | locked |
| 2026-10-09 | **Three anchor files in root (this one, STATE.md, ARCHITECTURE.md)** | same defect class as the six test errors: a new session re-litigating or re-deriving settled state. STATE is written BEFORE and AFTER work; a dead session is resumable from STATE alone. | locked |
| 2026-10-09 | **B+ forward-test ledger over the snapshot** | task B gave one aggregate coverage number; a 6/12-month claim needs a TIME SERIES. forward_test.json is append-only, idempotent, newest-verdict, and rendered per-day on the dashboard. | locked |
| 2026-10-09 | **Newest verdict before an event, not the oldest** | link_to_runs() iterated ascending and broke at the first run <= event (the OLDEST verdict); forward_test's bisect exposed a 1-vs-4 CAUTION mismatch. Both now use newest-verdict. | locked |
| 2026-10-09 | **Subagents: bounded p-limit pool, parent writes state** | spawnSubagents() fans out at concurrency 3 over one model family; results return to the parent which writes STATE.md once. No framework (CrewAI/LangGraph) — the engine already owns decomposition and the ledger. | locked |
| 2026-10-09 | **gemma3:12b for subagents, not the gemma4 default** | gemma4 reasons into the budget and returns empty response (measured: 3/3 subagents empty); gemma3 returned 3/3 in 4.6s warm. Pass model explicitly. | locked |
| 2026-10-09 | **Client-side dashboard interactivity, never a backend** | watchlist pins + a transitions time slider are pure JS over the already-embedded data, persisted to localStorage. A server/websocket would break the flat-JSON, zero-request, bare-VPS contract for real-time the 15-min batch does not need. | locked |
| 2026-10-09 | **API is the product, dashboard is not the surface** | the value is replay-verified, metered MCP access; a human reading a terminal is not the buyer. The dashboard stays as the demo, not the product. | locked |
| 2026-10-09 | **Anomalous velocity over fixed thresholds** | a 5pp floor misses a flat market's 3pp move and floods a swingy market's routine 3pp. z-score against the market's OWN interval-move history + a raw 5pp floor. z derived from the SAME rounded mean/sd that is stored, so the alert is auditable by hand. | locked |
| 2026-10-09 | **Screener-local modules are invoked via screener/, not root** | the B+ wiring called os.path.join(HERE, "liquidations.py") at ROOT while the files live in screener/, so every tick failed silently under --quiet. Fixed to os.path.join(HERE, "screener", ...). | locked |
| 2026-10-09 | **Salvage the sensor, burn the actuator** | the legacy scripts/aegis/ daemons mixed measurement with execution and their own backtest (backtest_1min_results.csv, 10k rows) showed the actuator losing 67% in a week vs buy-and-hold +3%. Only the read-only sensor math survives: health/leverage/LTV/drawdown-to-liquidation (fee_debt_model_v2, daemon_v6) and price-velocity detection (volatility_guard). The pause/exit/rebalance/flip state machines are discarded. | locked |
| 2026-10-09 | **Clean summary layer, dense drill-down** | the dashboard leads with a 17-column transitions table; that is why it reads as busy next to LiveCoinWatch. Added an "all N markets at a glance" table (collateral · verdict pill · util · supplied · net APY · liquidity) with the heavy fields (LLTV, bad debt, volatility, flags, reasons) in the per-row drawer. Additive-only: forensics tables unchanged. | locked |
| 2026-10-09 | **Summary is the default landing view** | the page opened on a 17-column transitions dump; that is why it read as busy. Extracted the glance table into its own top-level data-section='summary', added a Summary tab (active by default), and programmatically fired it on boot so the landing view is the clean verdict-at-a-glance table alone. Everything still exists behind the Everything tab and jump links; forensics tables unchanged. | locked |
| 2026-10-09 | **Initiator v2: the read-list IS the anchors** | ORCHESTRATOR_INITIATOR (both forms) now names STATE/ARCHITECTURE/DECISIONS in order, so the orchestrator starts from the recorded state instead of re-deriving it | locked |
| 2026-10-11 | **Every table its own section + tab; "Everything" tab removed** | the old page had 4 wrapped sections and ~12 tables sitting unwrapped inside an unclosed `watch` div, so most tables showed on every tab and "Everything" was a wall. Flattened to 15 flat sibling `data-section`s (summary, watch, lending, soty, scan, pools, coverage, stress, regimes, runway, liqs, premortem, rwa, pricing, method), one tab each; Summary is the default landing view. Also fixed the pre-existing unclosed `<div>` in the `_his` block that made `watch` swallow the rest of the page. | locked |
| 2026-10-11 | **DEX fee/volume feed (`dex_pools.py`) closes the vault-venue blind spot** | Aegis indexed 2,641 lending venues and zero DEX pools, yet the vault deploys into Aerodrome. `screener/dex_pools.py` ingests GeckoTerminal Base pools and derives `fee_24h = volume × fee tier` (tier parsed from name), ranked by fee. Wired a `dex` intent into `chat_api.py` so Aegis answers "which pool earns the most fees" deterministically (numbers from JSON, never the LLM). Corrected claim: AERO/cbBTC 0.6% is the top Aerodrome pool (~$65K/day), not the top Base pool (xdp/USDC 2% ~$135K/day). | locked |

## Superseded / corrected decisions

| date | what was corrected | correction |
|---|---|---|
| 2026-10-08 | "gemma4:12b RETURNS EMPTY STRINGS" | wrong diagnosis: it reasons into the budget; CoT lands in `thinking`. gemma3 retained for speed/simplicity, not because gemma4 is broken. |
| 2026-10-08 | "cbZEC occupancy 1.15x the runway, live" | historical — the runway cap now binds every funded position; today no position exceeds 0.60. The in-page note is reworded as the example that made the cap concrete. |
| 2026-10-08 | "30 all-null series block the allocator" | they do not: all 30 belong to AVOID-verdict markets unreachable by the allocator anyway; 15/15 eligible markets have ≥10 usable prices. |
| 2026-10-09 | prompt brief's `--verify runs/<iso>` | double-prefixes; the tool wants a basename. 0/113 → 98/113 with the right form. |

## The six near-misses (why this ledger exists)

Six times a failing assertion nearly forced a fix to WORKING code; the assertion was the bug
every time. Test errors recorded in REPO_STATUS.md: the `&&` false positive, pytest collecting
nothing, the zero-assertion "pass", the `--check` that ran the cycle it gated, the helper
masquerading as a suite (`_jsdom_util.cjs` swept by a `*.cjs` glob → now `test_*.cjs`), and the
prompt's double-prefixed verify path. RULE: when an assertion fails, decide whether CODE or
ASSERTION is wrong BEFORE touching either, and record that call here when it is the assertion.

---

## 2026-10-24 — Publishing Aegis, and hosting the MCP

Four decisions and one correction, recorded because each closed off an option that was
argued for and rejected on evidence.

### D1. Publish under AGPL-3.0, not MIT

**Chosen:** AGPL-3.0. **Rejected:** MIT, and "no license".

The argument for MIT was reach. The argument against is that this repo's value is a
*conclusion* — most high-yield markets fail basic solvency checks — plus the harness that
proves it case by case. AGPL keeps a network service running a modified version obligated to
publish its changes, so the corpus stays attributable rather than quietly re-badged, while
still being forkable.

"No license" was never actually a strategy: without a license the code is **all rights
reserved**, so publishing it would have granted nothing. That was an accident waiting to be
made permanent.

### D2. Host the HTTP MCP, but keep the unit loopback-bound

**Chosen:** write `mcp_http.py`, run it on **127.0.0.1:8051**, expose it deliberately later.
**Rejected:** binding 0.0.0.0 immediately.

`mcp_protocol.py` spoke stdio only. stdio is correct for local use and **cannot be hosted or
rate limited** — there is no request to count. So the transport had to exist before the
limiter could mean anything.

The binding stays loopback because a mistake in a unit file should not mean "the internet can
reach a data endpoint".

### D3. Three rate limits, sliding window, in-process

**Chosen:** per-IP + per-token + global, sliding window, in-process state.
**Rejected:** a single limit; fixed windows; Redis.

One limit is not enough: a per-IP limit alone lets one subscriber behind CGNAT starve
another, and no per-IP limit bounds total load. Sliding rather than fixed because a
fixed-window counter lets a caller send 2× the limit across a boundary.

In-process is honest for one box, one process, one dataset. A restart empties the buckets —
that is a stated limitation, not an oversight, and it is why `StartLimitBurst` is set: a crash
loop would also mean no rate limiting at all.

### D4. `TRUST_PROXY` defaults to 0

**Chosen:** off by default, explicit opt-in.
**Rejected:** reading `X-Forwarded-For` when present.

There is no reverse proxy on this box. Trusting the header by default would let any caller
set their own IP and walk around the per-IP limit — defeating the control while appearing to
implement it. If a proxy is added it must set `TRUST_PROXY=1` **and** the unit must stay
loopback-bound, so the header can only come from that proxy.

### C1. CORRECTION — the auth bypass, and the rule it re-confirms

`tokens.verify()` returns `(ok, payload)`. The first version of `_verify_token` returned that
tuple directly. **`(False, "bad_signature")` is a truthy tuple**, so every non-empty token
was accepted. Measured: no token → 401, valid → 200, **garbage → 200**.

Fixed by unpacking. Retested: bad, forged and truncated tokens all return 401.

This is the seventh instance of the rule already recorded above — *when an assertion fails,
decide whether CODE or ASSERTION is wrong before touching either* — with a twist worth
naming: **a passing test proved nothing here, because the test only used a valid token.** The
bypass surfaced only from testing a token that must fail. Negative tests are not optional for
an auth path.

# STATE.md — the live board

> Orchestrators and humans: read this first. It is written BEFORE work starts (status) and again
> when it ends (results), so a session that dies mid-task can be resumed by reading this file
> alone. Keep it under ~300 tokens of load-bearing content; detail belongs in REPO_STATUS.md and
> DECISIONS.md.

**Updated:** 2026-10-11 UTC · `975 assertions / 39 suites / 0 failures` · parity AGREE · dashboard = 15 tabbed sections ("Everything" removed) · DEX fee feed live (dex_pools.py)

---

## Where this stands: 2026-10-24 — repo published, MCP hostable

| item | state |
|---|---|
| repo history | **1→2 commits**, rebuilt fresh. The old history included `screener/token_secret.key`; it is now in **no** commit. |
| secret | **rotated.** Old key archived to `/root/.aegis-private/` (mode 600). Ledger reset. `tokens.py --selftest` passes. |
| tracked size | 8,845 → **739 files**; `.git` 196MB → **70MB**. `runs/` 276MB → 596KB, `audits/` 20MB → 116KB. |
| clone test | clean clone runs `lending_screen.py` (100 markets) and passes `mcp_protocol.py --selftest` |
| `TRAP_TABLE.md` | written from live data. **12 of 12** highest-APY markets fail. |
| `rate_limit.py` | 12/12 selftest |
| `mcp_http.py` | live-tested: 8 tools, auth 401/200/401, 70 req → 58×200 + 12×429, 2MB → 413 |
| `deploy/aegis-mcp.service` | `systemd-analyze verify` clean. Loopback-bound, auth on. |
| `deploy/firewall.sh` | syntax checked. **NOT YET RUN** — ufw is inactive. |

### Blockers

1. **ufw is inactive.** `deploy/firewall.sh` allows SSH first and only then enables — that
   ordering is the difference between a firewall and a lockout. Do not reorder it.
2. **No reverse proxy installed** (no nginx/caddy/traefik). 8051 is therefore not reachable
   from the internet even if ufw allows it, because the service binds loopback. Opening the
   port is a prerequisite for a proxy, not a substitute for one.
3. **The limiter is in-process.** A restart empties the buckets. Fine for one box; a fleet
   needs a shared store.

### Next

1. `systemctl enable --now aegis-mcp` then confirm `curl 127.0.0.1:8051/health`.
2. Decide on a proxy. If added: set `TRUST_PROXY=1`, keep the unit loopback-bound.
3. Run `deploy/firewall.sh` — **after** verifying you can still SSH in a second session.
4. Publish `TRAP_TABLE.md`. Hosting does not create demand; that post does.

---

## Status: operational — screen + provenance + liquidations + covariance diagnostic + DEX fee feed live

- **Active task:** none between cycles. Next pick listed below.
- **Last milestone:** task B+ complete — forward-test coverage ledger (append-only daily series);
  cross-referenced to run verdicts; ingest wired into `aegis_loop.py` every tick
- **Suite:** 975/39/0 (`sh run_tests.sh`) · parity AGREE · report ≡ screener/index.html
- **Cycle:** `aegis-forward.timer` ACTIVE (15 min) · latest run `runs/20261008T231428Z`,
  replay-verified · 127 run dirs (98/113 old ones verify, 15 predate the volatility fields)

## Completed components

- [x] provenance-stamped runs + replay verification (`runs/<iso>/`, 127 dirs)
- [x] seven-check lending screen + volatility enrichment (`sigma_to_breach`, cadence-normalised)
- [x] allocator: 5 rules, runway cap w≤runway/2, 30% collateral cap, 15% reserve — SIMULATION ONLY
- [x] dashboard: 15 tabbed sections (summary, watch, lending, soty, scan, pools, coverage,
      stress, regimes, runway, liqs, premortem, rwa, pricing, method); "Everything" tab removed;
      every table is its own flat section; zero external
      requests; 34-assertion a11y/display suite; sticky first column, copy-address cells,
      telemetry-only drawers, threshold gauges, card-filter pills
- [x] portfolio covariance diagnostic (pairwise-complete, shrunk, PSD +0.2495; correlation COST
      0.86% on this book — rendered honestly as a diagnostic, not an optimizer)
- [x] liquidation ingest + flag-coverage table; the negative result is published in-page
- [x] B+ forward-test ledger: append-only daily coverage series (`screener/forward_test.json`),
      newest-verdict semantics, wired into `aegis_loop` every tick + rendered on the dashboard
- [x] orchestrator initiator **v2** recorded on every run (`orchestrator.json`): initiator's read-list = the three anchors; STATE.md is written before AND after work
- [x] dashboard web-dev pass 1: client-side watchlist (pin star per row, persisted to
      `localStorage`, `☆ watchlist` toggle); transitions time slider (filter the What-changed
      table to a time window); 44px touch targets for pin/tab/watch controls. All client-side,
      zero new dependencies, zero network requests — the flat-JSON/no-DB contract intact.
- [x] **DEX fee/volume feed** (`screener/dex_pools.py` + `dex_pools.json`): GeckoTerminal
      Base pool ingest, `fee_24h = volume × fee tier`, ranked by fee; `dex` intent wired into
      `chat_api.py` so Aegis answers fee questions deterministically. Closes the vault-venue
      blind spot (Aegis saw only lending venues, never the Aerodrome pools the vault deploys into).
- [x] **anomalous-velocity move detector** (`screener/velocity.py` + `velocity.json`): the
      real-time signal, exposed as MCP tool `velocity_alerts`. Flags a market whose LATEST move
      is unusual FOR ITSELF (z >= 3.0 against its own interval-move history) or a raw >= 5pp
      move. 60 markets tracked, 0 alerts at last build — a measurement, not a silent zero.
      Wired into `aegis_loop` every tick. This is the paid-tier signal; the read-only audit is
      the loss-leader.

## In progress / blocked

- [ ] **standing debt: the `abspath(__file__)` bug** — 12 writer modules fork state when invoked
      through `screener/` symlinks (logs split, shadow runs/). systemd runs root paths so
      production is safe; the fix is `realpath` + `screener/` copies → root-canonical. NOT started.
- [ ] 15 oldest runs fail replay (11 predate the 3 volatility fields, 4 a reasons rewording). A
      screen-module hash in provenance would make the next one self-describing.
- [x] `link_to_runs()` stale-walk bug — it attached the OLDEST verdict before each event
      (CAUTION 1); forward_test exposed it (CAUTION 4). Fixed to newest-verdict; both now agree.
- [ ] 31 of 61 price-cache series are all-null (HERMES, RSS, FUSD, HOME, kk, GRO...) — every one
      already AVOID on other grounds; refetched each cycle, no retry needed beyond that.

## Next immediate steps (pick ONE)

1. **C2: covariance → allocator sizes** — the matrix exists and is PSD; a real optimizer pass
   (portfolio-vol-aware weights) is the remaining piece. Watch the locked decision: no vault
   until a measurable edge exists; covariance is sizing, not edge.
2. **D: USR teardown publish** — data is in place (`USR_TEARDOWN.md`, 30 liquidation events,
   $35.6M outstanding); needs sourcing + writing.
3. Close the `abspath` debt (small, prevents a silent state fork).

## The salvage: sensor survives, actuator is dead (recorded 2026-10-09)

- Legacy `scripts/aegis/` daemons (daemon_v6, volatility_guard, fee_debt_model_v2, flip_executor,
  safe_executor, dex_arbitrage, flash_loan_arb, ~200 files) mixed measurement with execution.
- Their OWN backtest (`backtest_1min_results.csv`, 10,080 rows, real 1-min ETH 2026-04-30..05-07)
  settled it: Aegis leveraged-LP -67%, spot signal-trading -53%, **buy-and-hold +3.2%**.
- Salvaged ONLY the read-only sensor math into `screener/position_risk.py` + MCP tool
  `position_risk`: health = (value-debt)/value, leverage, LTV, drawdown-to-liquidation == health,
  and price-velocity regime (none/warn/alert/critical + directional danger). No sell/exit/flip.
- The actuator layer (every pause/exit/rebalance/flip/arb/flash file) is not carried over.
- Live position in Aegis_live_state.json (health 0.2075, ~3.77x, LTV 73.5%) is the SAME strategy
  that backtested to -67%. It is a warning, not a proof of life.

## Strategy (recorded 2026-10-09)

- **API is the product; the dashboard is not the surface.** Human eyes on the terminal is a
  distraction. The MCP is where the value is: one call, replay-verified, metered.
- **NOT "open-source Arkham".** Arkham sells attribution/entity intel; Aegis sells VERIFICATION
  (what a yield is made of, what the screen knew before a liquidation). Different buyers, moat,
  and regulatory surface. Frame: an open-source risk/DD ledger for lending markets.
- **The moat is time-bound data, not code.** An engineer can rebuild the deterministic screen in
  a weekend. They cannot rebuild N days of replay-verified runs + the forward-test coverage
  series + the measured negative results. Sell the accumulated ledger; open-source the code as
  the loss-leader (it buys "verified by construction" trust and costs nothing).
- **Pricing: metered, not a flat fee.** ~$0.05/audit (current $0.02 + 3 free/day), not $2/day.
  The buyer is an automated process running hundreds of audits/day that needs an auditable trail.
- **The paid signal is the move detector.** The read-only audit is the loss-leader; `velocity_alerts`
  (anomalous velocity on the 23 markets that move) is the thing an engineer would rather subscribe
  to than stand up and wait to accumulate.

## Numbers that are safe to publish

| claim | number | source |
|---|---|---|
| Morpho screen today | 17 REAL / 9 CAUTION / 34 AVOID (60 markets, run 20261008T231428Z) | latest `screen.json` |
| USR bad debt | $35.6M outstanding / $0 realised | same, `0xff0f2bd5…` |
| allocator today | $849,999 of $1,000,000, 15 positions | latest `allocator.json` |
| liquidations (2.3y) | 30,934 events; d30: 2,127, bad-debt 20 ($29.94) | `screener/liquidations.json` |
| coverage stat | 1,261 covered → AVOID 0 / CAUTION 1 / REAL 1,260 | `link_to_runs()` |
| structural backtest | 46.7% of indexed pools lost >50% TVL in 12mo [CI 38.1–55.5] | BACKTEST_FINDINGS.md |
| >8% APY promises | 0 of 12 delivered; median retention 56.6% | same |

## Numbers that must NOT be claimed

- pool flags predict loss (overlapping CIs, n=122)
- stress-backtest "detections" (circular: util>95% at T → util≥99% forward is one measurement)
- liquidations are screen failures (1,260/1,261 hit REAL markets — mechanism, not miss)
- any strategy beats buy-and-hold (corr −0.996 across 45 runs)

## If you are a new session

1. read `ARCHITECTURE.md` (the contract — especially the symlinking rule)
2. run `sh run_tests.sh`, confirm 0 failures; confirm `aegis-forward.timer` active
3. read `DECISIONS.md` top entries — do not re-litigate locked decisions
4. pick from "Next immediate steps"; update this file BEFORE working and again AFTER

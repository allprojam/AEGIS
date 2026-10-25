# Aegis — locked position, and the evidence behind it

**Aegis is a read-only, zero-liability risk intelligence terminal.**
It holds no keys, signs no transactions, and manages no capital.

Last updated: 2026-10-07

---

## 1. The asset-management trajectory is formally retired

**The Aegis Curated Vault is dead. Not deferred — retired.** Product 2 (a Morpho asset-management
arm) is not on the roadmap, and this is recorded here so it is not quietly resurrected.

### Why, with the numbers that decided it

Queried live from the Morpho API, all Base vaults:

```
total Base vault TVL      $1,060.4M
TVL paying ZERO fee         $519.1M   (49%)
distinct curators                 33

Gauntlet USDC Prime    $413.9M   0%     <- the category leader is FREE
Spark USDC Vault       $360.6M   10%
Steakhouse USDC        $123.0M   25%
Grove x Steakhouse     $103.4M   0%
```

**Three independent reasons, any one of which is sufficient:**

1. **The leader charges 0%.** A 5–10% performance fee is priced *above half the category*, including
   the largest vault. There is no fee position available that is not undercut by the incumbent.
2. **33 curators already exist.** Delphi wrote *"The Rise of Morpho, Curators, and Mullets"* in
   April 2025. The "new curator with no brand" framing describes a market from two years ago.
3. **Regulatory attention is on exactly this role.** July 2026: *"SEC Commissioner Peirce puts DeFi
   vault curators on notice re securities laws."* The plan's *"Legal: Discretionary Asset
   Management"* is an **exposure**, not a diagram label — and it is a lawyer's question, not a
   risk-register line.

**And the business model is under active public scrutiny:** on 26 Sept 2026 a headline read *"Morpho
Blames AI Marketing Tool for Deleted Post Saying Its Own Curator Business Model is Broken"*; on
28 Sept, *"MORPHO Drops 3.4% Amid Business Model Scrutiny."* **Headlines only — both articles
returned 404 on direct fetch and their contents are NOT verified here.** But the existence of that
argument, made about the protocol, is material.

**The deeper reason, which does not depend on any of the above:** the screen cannot yet show it
prevents losses. `FLAGGED 52.4%` vs `PASSED 43.8%` on n=122 — **overlapping confidence intervals.**
Selling a vault on that would be selling a claim the data refuses to support.

**The kill decision is recorded in `MORPHO_PLAN.md`, `AUTONOMY_VERDICT.md` and here.**

---

## 2. What Aegis IS

**A read-only risk intelligence terminal.** Two deterministic engines, one provenance layer, no
custody.

| component | what it does |
|---|---|
| `screener/screen.py` | 6 checks across 16,749 AMM pools (DefiLlama) |
| `lending_screen.py` | 7 checks across 60 Morpho Blue USDC markets (Base) |
| `morpho_fetch.py` | read-only GraphQL ingestion, provenance-stamped at fetch time |
| `provenance.py` | immutable `runs/<iso>/`, replay verification |
| `aegis_run.py` | Sense → Evaluate → [Reason] → Commit → Verify |
| `aegis_loop.py` | single entry point; `--check` verifies and exits |
| `alert_diff.py` | append-only State Transition Log |
| `allocator.py` | the arithmetic a vault *would* use — **simulation only** |

**The public value proposition, stated without inflation:**

> **108 passing assertions. Immutable block provenance. Zero speculative claims.
> An append-only log of every market state.**

---

## 3. Published claims, and the evidence for each

| claim | source | status |
|---|---|---|
| 46.7% of indexed pools lost >50% TVL in 12 months | `structural_backtest_v2.jsonl`, 122 pools | **measured**, 95% CI [38.1–55.5%] |
| 0 of 12 pools >8% APY delivered the advertised rate | `apy_decay.json` | **measured**, median retention 56.6% |
| 34 of 45 strategy runs lost to buy-and-hold | `premortem_results.json` | **measured**, corr −0.996 |
| USR carries $34.8M bad debt against $36.7M supplied | Morpho API + on-chain `idToMarketParams` | **verified**, contracts confirmed |
| 60 Morpho markets screened, 18 REAL / 8 CAUTION / 34 AVOID | `runs/<iso>/screen.json` | **measured** |

## 4. Claims that are NOT made, and must not be

**⛔ POOL-SCREEN FLAGS DO NOT PREDICT MORTALITY.** n=122: FLAGGED 52.4% vs PASSED 43.8%,
overlapping CIs. The direction is right; separability is not demonstrated.

**⛔ THE STRESS BACKTEST IS CIRCULAR.** It printed FLAGGED 85.7% vs PASSED 8.3% (disjoint CIs).
Input = utilisation >95% at T; outcome = utilisation ≥99% forward. **The same measurement.** The
"independent" cross-check is also mechanical — at 100% utilisation the kinked rate model spikes APY
by arithmetic, not by signal. Median utilisation at T was 100%, so the flag detects the **modal
state**. `stress_backtest.py` labels itself *"NOT a bad-debt predictor"*. Keep it that way.

**⛔ THE TRANSITION LOG HAS NO DEMONSTRATED VALUE YET.** Six clean intervals, zero events. A
detector that has never observed a transition has unknown true- and false-positive rates. It stays
labelled a State Transition Log, private and unsold, until a forward test says otherwise.

**⛔ WE DID NOT PREDICT THE USR EXPLOIT, AND SAY SO FIRST.** `USR_TEARDOWN.md` opens with
*"a structural screen reads structure; it cannot read a compromised private key."* Every dramatic
reading on that market is post-exploit.

---

## 5. The forward test — running

**`aegis-forward.timer`**, `OnUnitActiveSec=15min`, `Persistent=true`. Installed 2026-10-07.

```
[sense]      60 markets, live block
[evaluate]   7-rule lending screen, no model in the path
[reason]     optional, gemma3:12b only
[commit]     runs/<iso>/ (markets, screen, meta, prompt, reason)
[verify]     replay must reproduce exactly
[transition] alert_diff.py appends to alerts.log
```

**Two guardrails, both of which had to be fixed before they worked:**

- **`ExecStartPre=... --check`** — preflight. **This was broken:** `--check` ran the preflight *and
  then continued into the full cycle*, so as `ExecStartPre` it would have run the cycle **twice per
  tick**. A guardrail that performs the dangerous action it is meant to gate is worse than none. Now
  it verifies and exits.
- **`flock -n`** — a slow cycle makes the next tick abort rather than stack. Plus
  `TimeoutStartSec=300` so a hung model call cannot hold the lock forever.

**Model pinned:** `AEGIS_MODEL=gemma3:12b`. **`gemma4:12b` returns empty strings** and must never be
used; the preflight treats an empty response as a failure, not as "nothing to report".

**This is the first genuinely unattended operation in the project.** The 1-minute test unit proved
the mechanism: 71 consecutive ticks over 1.2 hours, every one `PPID=1`, zero gaps over 120s.

---

## 6. Standing rules

1. **A claim without a passing test is marked unverified here.** No exceptions.
2. **Every published number traces to a measurement** in this repo or a cited source.
3. **Compiling is not working.** Three files here were "fine" while unable to run. Run the thing.
4. **When a filter looks wrong, check it against the data before "fixing" it.** The turnover floor
   looked broken and was correct.
5. **When an assertion fails, establish whether the CODE or the ASSERTION is wrong before touching
   either.** Six times a test error nearly forced a change to working code.
6. **A test is only a test if the input and the outcome can disagree.** If they cannot, it is a
   restatement.
7. **An optimisation that makes data easier to collect can silently break the thing being
   measured.** The prefilter doubled scan speed and drove the headline metric to structurally zero.
8. **If the instrument needed for rigour is unreachable, say so and find the equivalent.** Raw RPC
   was 403; GeckoTerminal answers the same question.
9. **A guardrail that performs the action it is meant to gate is not a guardrail.** `--check` did
   exactly this until it was tested.

---

## 5b. Dual-cadence provenance, and a correction to an earlier claim

**The dashboard mixed two cadences under one timestamp.** The Morpho lending half is refreshed
every 15 minutes by the timer; the AMM table came from a DefiLlama snapshot refreshed only by a
manual build. Presenting both under a single block-height line implied the whole document shared
one on-chain state. Measured at the time: **lending live, AMM 9.5 hours stale.**

**Fixed by labelling them separately:**

```
Lending Provenance:    Base block 52313035 · ingested 23:23:45Z · 60 markets · sha256 2507cf43…
AMM Index Provenance:  DefiLlama snapshot 23:32Z · 0 minutes old · manual build cadence
```

The AMM age is **computed from the file mtime**, so a stale snapshot is visible rather than
silent. `test_provenance_split.py` asserts the block height never appears in the AMM line, so a
reader cannot attribute an on-chain state to data that has none.

**`aegis-amm.timer`** refreshes `results.json` daily at 00:00 UTC. Chosen over a 15-minute poll
because DefiLlama's own scrapers index on a multi-hour cycle: polling 16,700 pools every 900s
would consume bandwidth and risk HTTP 429 for no new information. Verified by running the unit
once: **16,735 pools refreshed, exit 0.** The unit sets `WorkingDirectory` because `screen.py`
writes a **relative** path, uses `flock -n` so scrapers cannot stack, and has a timeout.

### CORRECTION: the test suite DOES make zero network calls

An earlier claim in this session, and a correction to it:

- **I first reported** (wrongly) that `test_export_report.py` contained 2 live network calls.
  My grep matched **string literals inside assertions** -- `check("no fetch() call", "fetch(" not
  in page)` -- not calls. A test asserting the absence of `fetch(` was counted as using it.
- **I then proved the real answer:** every Python suite run with `socket.socket`,
  `socket.create_connection` and `socket.getaddrinfo` replaced by raising stubs.
  **8 of 8 passed; 0 touched the network.**

So no mock is needed, and the suite is genuinely hermetic. Recorded here because the wrong claim
was made out loud before it was checked.

## 5c. The screener/ shadow tree, eliminated structurally

**A module maintained in two places will eventually be edited in the dead copy.** This project
proved that three times:

| bug | what happened |
|---|---|
| `runs/` split-brain | systemd wrote to root `runs/` while the dashboard read `screener/runs/` |
| `lending_dashboard.py` | the edit landed in the root copy; `build_v2.py` imported from `screener/` |
| `index.html` copy-race | a manual `cp` raced a background build |

**The audit found it was worse than "duplication".** Systemd ran **root** files for the Morpho
loop but **`screener/screen.py`** for the AMM refresh -- so the two daemons were sourced from
different trees. And `morpho_fetch.py` **had already diverged**: the root copy carried the
`oracle { address type }`, `blockNumber` and `historicalPriceUsd` additions; the screener copy
did not.

**Measured before the fix:** 18 duplicated modules (17 identical, 1 differing), 20 files present
only in `screener/`, 7 duplicated test files (1 differing).

**And it was wider than code.** A second pass found **21 more real copies** -- including data:
`morpho_markets.json` differed by **24KB**, `lending_screen.json` by 45 bytes, `report.html` by
**75KB**. **Data drifting is worse than code drifting**: the dashboard would render one snapshot
while the daemon wrote another, with no error anywhere. All 21 are now symlinks; the test checks
**every file**, not just `.py`.

### The fix: symlinks, not rules

Root is canonical for shared modules; `tests/` is canonical for test files; `build_v2.py`,
`screen.py` and the rest of the screener-only tooling stay where they are.

**30 symlinks** now replace the copies. Editing either path edits the same inode, verified live:
a marker appended to root `lending_dashboard.py` appeared immediately through the `screener/`
path, and disappeared on revert.

`test_no_shadow_tree.py` asserts the property structurally rather than by convention:
- every duplicated module is a **symlink**, never a real copy
- each symlink resolves to the root file
- **same inode** for a probe pair
- `screener/runs` still resolves to root `runs/`
- **no systemd unit** references a `screener/` duplicate

**A rules-based fix would have been the wrong shape.** "Remember to edit the root copy" is the
same class of guardrail that already failed three times here; a symlink cannot be forgotten.

**Post-consolidation verification:** both daemons run clean (forward cycle commits and
replay-verifies; the AMM unit refreshes 16,735 pools, exit 0), parity `AGREE`, **321 assertions**.

## 5d. The local GPU: gemma4:12b, and a diagnosis corrected twice

**The question was how to bring the local GPU in. The answer turned out to be that it was already
reachable — and the model we had written off was not the model we thought.**

### What was believed
`aegis_run.py` carried: *"gemma4:12b ... RETURNS EMPTY RESPONSES. Verified 2026-10-07."*
gemma3:12b was pinned instead. The GPU sat idle.

### What is actually true (measured 2026-10-08)

`gemma4:12b` enables **reasoning by default** and writes its chain-of-thought into a separate
`thinking` field *before* emitting `response`. On the real 1,503-char triage prompt:

```
gemma4:12b  num_predict=2048  resp=0     thinking=5453  eval=2048  done=length
gemma4:12b  num_predict=2048  resp=0     thinking=5290  eval=2048  done=length
gemma4:12b  num_predict=4096  resp=0     thinking=8560  eval=3309  done=length
gemma3:12b  num_predict=512   resp=432   thinking=0     eval=123   done=stop
```

**gemma4 never answers this prompt at any tested budget.** It reasons until the budget is gone.
The reasoning runs 4-7x longer than an answer would be.

So the pin was **correct but for the wrong reason.** It is not an intermittent empty-response bug;
it is a model that spends everything on reasoning. gemma3 is also **6.7x faster** (123 eval tokens
vs 3,309) and produces a sound answer.

### The testing error, which is the transferable part

The earlier note said *"Do not change without testing for non-empty output."* **That test was done
— and it passed.** `gemma4:12b` replies fine to `"Reply with exactly: READY"`.

**Testing a reasoning model on a toy prompt proves nothing**, because a toy prompt gives its
reasoning nothing to chew on. It fails only at the shape of prompt it will actually receive.
**Test a model at the length and structure of the real input.**

### What changed in the code, regardless of the model chosen
- The **`thinking` field is now read**. A reasoning model's answer is not in `response` alone.
- **`done_reason == "length"` with an empty response is now reported as `TRUNCATED`**, not as
  "nothing to report". Caught live during this work: *"spent the whole 2048-token budget on
  reasoning (thinking=5339 chars) and never emitted an answer."* The old code would have recorded
  the same run as a clean empty result.
- `keep_alive: 30m` so the model is not unloaded between the 15-minute ticks.

**The reason phase now runs end-to-end:** 468 chars committed into `runs/<iso>/reason.json`,
replay-verified, model `gemma3:12b`.

**On bringing the GPU in "directly": it already is.** `MODEL_HOST=http://100.90.251.75:11434` is
reachable from the daemon over the tailnet and the whole `[reason]` stage routes there. What was
missing was not a connection — it was a correct diagnosis.

## 5e. Flare coverage: present in the data, invisible on the page

**The question was why Flare pools (sparkdex, kinetic, clearpool) were missing.** They were not
missing. Measured: the feed carries **58 Flare pools across 9 projects**, and **26 were already
embedded** in the page JSON. **Exactly one reached the visible table.**

Two gates and a sort were responsible:

```
real = REAL verdict AND TVL > $10M      -> 445 pools
table = real[:80]  sorted by APY DESC   -> Flare ranks 35 and 240
```

`sceptre-liquid SFLR` ranked 35 and made it. `clearpool USDX` ranked 240 and was cut. Everything
else failed a gate: **`kinetic FXRP` is $26.5M but `MIXED`** (reward share >50%, so the REAL gate
excludes it).

**Rendering more rows does not fix this.** Top 200 shows the same one; top 445 shows two. **The APY
sort buries an entire ecosystem at any depth**, because a safe 3.5% pool competes against
subsidy-inflated APYs -- which is the inversion this screen exists to expose.

### The fix: a Flare tab, without weakening a single gate

Chain-relevant rows are rendered with `data-chain` and marked `data-extra='1'`. Extras are
**hidden by default**, so the headline ranking is byte-for-byte what it was (80 visible). The
**Flare tab** reveals them.

**A pool is only added if it already passed the screen** (REAL or MIXED) and clears $1M. The tab
changes what is **visible**, never what is **judged**.

**Result: 17 Flare pools reachable**, including the `sparkdex-v4` and `USD₮0` pairs asked about.

### Two brittle tests were exposed, and fixed

Adding a row attribute broke two suites -- both for reasons that were latent, not caused by it:

1. **`test_official_links` matched `<tr>` literally.** Rows now carry attributes
   (`<tr data-chain='flare'>`), so the pattern matched **zero rows** and the coverage check
   reported 0% -- **a test passing by finding nothing.**
2. **`test_ui` hardcoded `tabs.length===4`.** A fifth tab is a legitimate change, not a failure.
   It now asserts the expected tabs are *present* rather than a frozen count.

Both are the same defect this project keeps hitting: **an assertion whose failure mode is
indistinguishable from success.**

## 5f. Interfaces: a real MCP, a queryable ledger, and a "what changed" view

### The MCP was not an MCP

`screener/mcp_server.py` was described as an MCP. **Measured: an MCP client sends
`{"jsonrpc":"2.0","method":"tools/list"}` and got HTTP 404. Zero protocol methods existed.** It
was a hand-rolled HTTP JSON-RPC API with five routes -- useful, but **no MCP client could connect
to it**, so the claim was false.

**`mcp_protocol.py` implements the protocol properly** -- `initialize`, `tools/list`, `tools/call`
over stdio (the transport Claude Desktop, Cursor and most agent frameworks use). Six tools, each
with a JSON Schema:

| tool | what it answers |
|---|---|
| `audit_pool` | the six AMM checks on one pool, with reasons |
| `list_markets` | every tracked lending market and its verdict history |
| `get_market` | **the time series** for one market across all runs |
| `list_runs` | index: id, Base block, ingest time, verdict breakdown |
| `get_run` | every artefact of one run |
| `get_changes` | the State Transition Log |

**Verified over the real stdio transport**, not just in-process: `initialize` returns
`{"name":"aegis-risk","version":"1.0.0"}`, `tools/list` returns all six with schemas,
`tools/call` returns content blocks for every one, an unknown method returns `-32601`, and a
notification produces no reply.

**Every tool is read-only.** No tool writes, signs, or spends -- that is the product, not a gap.

### The ledger was write-only

**36 immutable, replay-verified runs had no interface.** The dashboard showed only the newest; the
transition log showed only deltas. Nobody could ask *"what has this market's utilisation done over
time"*. `run_history.py` makes it queryable, and **the API, the MCP tools and the page all read
through it** so they cannot drift into three answers.

```
GET /runs?limit=N      index
GET /runs/<iso>        one run, all artefacts
GET /markets           60 markets, verdict history
GET /series?market=cbBTC   36 block-stamped points
GET /changes           the transition log + unchecked
```

**Two design choices worth stating:**
- **An ambiguous collateral is never resolved by guessing.** `hermes` matches **25** markets.
  Asking for it returns `409` with the candidates rather than silently picking one -- guessing
  would attach real numbers to the wrong market.
- **Path traversal is rejected.** `get_run("../../etc/passwd")` returns `None`; the id must match
  a strict ISO pattern.

### "What changed", rendered

`alerts.log` had accumulated **33 intervals and 21 real events with no page showing it**. The
dashboard told you the current state and nothing about movement -- which is the thing a curator
actually acts on. The section now shows **33 intervals logged · 21 transitions seen**, each row
stamped with its run id and Base block.

**The UNCHECKED line is shown, not hidden:** *"1 check(s) could not run: ORACLE_FLIP. Their
silence is not evidence of stability."* An unchecked detector and a clean interval are different
states, and collapsing them would present a blind window as a quiet one.

### The transitions table is now fully enriched

The raw log recorded **what** changed and the numbers either side. That is enough to act on and
**not enough to investigate** — it did not say which venue, what the market was worth, or where to
look on-chain. Every row now carries **19 columns**:

```
when (UTC) · run · block · sev · venue · market · transition · util from · util to · Δ ·
LLTV · borrowed · liquidity · TVL · verdict · flags · collateral · oracle · links
```

**21 rows, 21 Basescan links, 21 Morpho links.** Both verified to return HTTP 200.

**A market id is a Morpho-internal key, not an address**, so the Basescan link opens the
**collateral token** — and `app.morpho.org/base/market/<id>` opens the market itself. Enrichment
joins each event to that run's stored market row; a missing field stays missing rather than
becoming a plausible default.

### Information density, across all three datasets

The transitions table (19 cols) was the template. Applied to the pool table too:

| table | before | after |
|---|---|---|
| **What changed** (transitions) | 5 cols, 21 rows | **19 cols, 22 rows** |
| **REAL pools** (AMM) | 12 cols, 96 rows | **28 cols, 58 rows** |

**Every added column was data the feed already published and the page discarded.** `slim()`
dropped `volumeUsd1d`, `volumeUsd7d`, `apyBase7d`, `apyPct1D/7D/30D`, `il7d`, `ilRisk`,
`exposure`, `poolMeta` and the `underlyingTokens` — all now carried and rendered. **Nothing is
derived from nothing: a missing value renders as a dash, never a zero.**

The columns that earn their space are the comparative ones: **`vs mean`** (current APY against
its own 30-day mean — a spot figure hides that a yield is *below* its own recent average),
**`emit share`** (how much of the number is subsidy), **`turnover/d`** (whether fees can pay
depositors at all), and **`IL 7d`** (whether an LP can lose money while the yield is positive).

### The four applicable skills, applied and measured

Of the 13 installed skills, **four** apply to a generated static document with no component tree:
`better-accessibility`, `better-layout`, `better-ui`, `better-typography`. (`interface-review`,
`break`, `state-machine` and `variant` assume a git repo and components; `build-design` assumes
Figma; `explain-interface` is for reverse-engineering someone else's site.)

Each change below was **measured before and after**, not eyeballed.

#### better-typography — 13 font sizes to 7

```
before  10, 10.5, 11, 11.5, 12, 12.5, 13, 15, 16, 18, 19, 21, 22   (13)
after   10, 11, 12, 13, 15, 18, 21                                  (7)
```

Half-pixel sizes are gone. **Hierarchy is unchanged** — the mapping was near-identity, so nothing
moved by more than 0.5px, and the two sizes that carried real weight (10px: 193 uses, 11px: 198)
were already the dominant ones.

The skill's other rule: **line-height by role**. Headings were inheriting body's `1.55`, which is
right for prose and too loose for a heading. `h1` 1.2, `h2` 1.25/1.3 — all unitless so they scale.

#### better-ui — 11 radius values to 7

`6px` and `8px` dominated (4 each); the odd ones (`7px`, `9px`, `10px`) snapped to the nearest step.
One radius scale instead of eleven ad-hoc numbers.

#### better-layout — `scroll-padding-block-start`

The page used `scroll-margin-top` on headings only. `scroll-padding` on the scroll container covers
**every anchor and every focused element**, which is what the rule asks for — the 64px sticky topbar
can no longer swallow what you jumped to.

#### A second design system, found by the consolidation

Chasing the last off-scale sizes led somewhere unexpected: **`app.js` ships its own complete
stylesheet** for the audit-sheet popup, with hardcoded light-theme colours (`#111`, `#666`, `#888`),
a fixed `760px` column, **zero use of the page's CSS variables**, and its own `10.5px`/`11.5px`/`19px`
sizes and `4px` radius.

That is a **second design system inside a single-file report**, and it would have drifted
indefinitely. Its sizes and radius now follow the same scale as the main document. The fixed width
is left alone — a print-like audit sheet is a different surface and a column is correct there.

`test_a11y.py` grew to **19 assertions** pinning the type scale, the radius scale, the heading
line-heights and the scroll padding.

### Installed: the interface skills, and the two gaps they found

Installed as asked: `npx skills add jakubkrehel/skills` -> **13 skills, 512K, 64 files**, all
Markdown/YAML with **no executables**, into `.agents/skills/`. That is the knowledge layer — and it
is the **skill collection, not the npm package called Dembrandt** (see below for why those are two
different things).

Reading `better-accessibility` against the rendered page found **two real gaps**, both now closed
and asserted:

| gap | criterion | fix |
|---|---|---|
| `prefers-reduced-motion` **never handled** | WCAG 2.2 — motion ignoring the preference | reduce branch kills transitions, animations, smooth scroll |
| **2 media queries** for 9 sections and 4 dense tables | WCAG 1.4.10 — reflow at 320px | 400px breakpoint with `table-layout:fixed` |

The viewport meta was already correct (no `maximum-scale=1`, no `user-scalable=no`), and
`focus-visible` already accompanied every `outline` removal, so those needed nothing.

**`test_a11y.py` (13 assertions)** pins all of it **in the rendered HTML**, not the source — the
CSS is templated, so a brace error would produce valid Python that emits broken CSS. That is exactly
what happened while adding the fix: the first build reported `prefers-reduced-motion: 0` and looked
like a failed patch, when the real problem was a regex that assumed `@media (…)` with a space.

### Dembrandt — checked before installing, and it is two different things

The suggestion names **one tool** and **one repository**. They are not the same project, and the
npm package is not the design-rules collection.

| claim | verified |
|---|---|
| "Dembrandt, via `jakubkrehel/skills`" | **two unrelated projects** — the name *Dembrandt* appears **nowhere** in that repo |
| "available via npm" as a design-rule layer | `dembrandt` on npm is a **CSS token extractor** that drives Chromium |
| "40+ rules" | the repo has **13 skill directories**, all Markdown |
| "tooltip vs popover vs menu vs sheet vs drawer vs modal" | **no such skill** — the words tooltip/popover/overlay appear in none of them |
| "Data display and selection" and "UI density" skills | **do not exist** under those names |

**What npm's `dembrandt` actually is** (0.38.0, MIT, homepage dembrandt.com):
*"Extract design tokens and publicly visible CSS information from any website."* It depends on
`playwright-core` and **requires a one-time Chromium download** — on this host, Alpine under PRoot
with no browser installed, that is a heavy dependency for a job this project does not have.

**What `jakubkrehel/skills` actually is:** 7,566 stars, MIT, **13 skills** covering
`better-accessibility`, `better-colors`, `better-interface`, `better-layout`, `better-typography`,
`better-ui`, `better-writing`, plus `interface-review`, `break`, `state-machine` and others. Install
is `npx skills add jakubkrehel/skills`. **Markdown, no browser, no runtime** — a knowledge layer,
which is what the suggestion was actually describing.

#### The honest assessment for this project

The relevant skill is `better-accessibility` (WCAG 2.2). Measured against the current report:

```
aria-* attributes       23
title= tooltips        717
scrollwin containers     6
responsive @media        2
role= attributes         3
prefers-reduced-motion   0   <- unhandled
```

**Two real gaps: `prefers-reduced-motion` is never handled, and only 2 media queries exist for a
document with 9 anchored sections and four dense tables.** Those are genuine. But they are
**specific, fixable items**, not a reason to adopt a toolchain: the report is a single generated
HTML file with no build step, no framework and no CSS pipeline, which is precisely the property
that makes `audit_parity.py` and the 779-assertion suite possible.

**Recommendation: adopt nothing.** Fix the two measured gaps by hand and assert them. If a design
review is wanted, `interface-review` is the relevant skill and it is Markdown — read it, do not
install a dependency tree into a project whose value is that it has none.

### The lending tab now covers every venue, not one

The tab was called **"Morpho Lending"** and held **631** pools. DefiLlama's Lending category holds
**2,641** pools across **82 venues** — so the label named one venue while the rest sat unused.

| | before | after |
|---|---|---|
| tab label | Morpho Lending | **Lending markets** |
| pools reachable | 631 | **2,641 across 82 venues** |
| passing the screen | — | **489** |

Top venues by pools that pass: morpho-blue 149, aave-v3 74, kamino-lend 34, fluid-lending 30,
jupiter-lend 16, venus-core-pool 15.

#### Where the category comes from

**The yields feed has no category field** — checked: the live `/pools` response carries 28 fields
and none of them categorises the venue. The category comes from **`api.llama.fi/protocols`**, joined
by **slug** against the feed's `project`. Verified: this resolves **16,684 of 16,684** pools, so the
join is total rather than approximate. A small, **named** override set adds
`uncollateralized-lending` and `cdp`, which lend but are filed elsewhere — visible rather than silent.

#### The constraint that shaped the design

```
DefiLlama lending pools carry   apy, base, rew, tvl, sigma, count
The Morpho API markets carry    those AND utilisation, LLTV, runway, oracle_type
```

**There is no venue-agnostic source for utilisation or LLTV.** Aave's is behind Aave's contracts,
Kamino's behind Kamino's. A single merged table would have to leave those columns **blank for 2,581
of 2,641 rows**, or fabricate them. So the section carries **two tables with honest scope labels**
instead of one table with four empty columns. `test_venues.py` asserts that the deep columns really
are absent for the rest — **if they ever become available for every venue, that assertion fails and
tells you to merge.**

#### Two things this broke, both caught by existing suites

1. **`test_chain_tabs` failed**: a 400-row table with no scroll window is an unbounded data dump.
   Fixed with `class='dense'`, which is how every other tall table gets its window.
2. **`test_jumpnav` failed on ALL 9 anchors at once** — the signature of a stopwatch, not nine
   broken anchors. The page grew to **2.75MB** (from 2.64MB) and the suite's fixed 4s deadline no
   longer sufficed for a fresh jsdom to reach `load`. Raised to 15s, with the coupling to document
   size recorded so the next person does not re-diagnose it. All 9 pass.


### Provenance replay: 98 of 113 verify, and the 15 that do not have TWO causes

`provenance.py --verify` re-runs `lending_screen.screen_market` over the stored `markets.json` and
compares to the stored `screen.json`. Result:

```
verified   98
failed     15   (all dated 2026-10-07, the oldest runs)
```

**Neither cause is data. Both are code changes the runs predate, and they are separate:**

1. **Three volatility fields were added.** The current screen emits `ann_vol_pct`, `daily_vol_pct`
   and `sigma_to_breach`; runs before the enrichment do not carry them. 11 of the 15 fail on this.
2. **A `reasons` string was reworded.** The USR row read
   `carries $34,821,390 bad debt (realised $0) - loss already taken` and now reads
   `$34,821,390 outstanding bad debt (none realised yet) - solvency depends on recovery`.
   4 of the 15 fail on this. **The verdict is unchanged (AVOID) and all four rule hits are
   identical** -- only the prose moved.

**The gap this exposes: a run records no code version.** `meta.json` has checksums for its
artefacts and a `content_sha256` for the input, but nothing identifies the `lending_screen.py` that
produced the verdict. So a replay failure cannot distinguish "the code changed" from "the record is
corrupt" -- you have to bisect by hand, as above. Storing a hash of the screen module in
`provenance` would make the next occurrence self-describing.

This is not drift *within* the 98 newest runs: those reproduce byte-for-byte.

### The log split by invocation path (a real bug, found by running the loop from screener/)

`aegis_loop.py` and `alert_diff.py` resolve data paths with
`HERE = os.path.dirname(os.path.abspath(__file__))`, which **does not follow symlinks.** Both files
are symlinked into `screener/`, so invoking the loop *through that path* writes
`screener/aegis_loop.log` and `screener/alerts.log` while the canonical root logs stay untouched:

```
abspath  -> /root/agency_bot/workspace/aegis/screener     <- where the log went
realpath -> /root/agency_bot/workspace/aegis              <- where it belongs
```

**30 symlinked modules under `screener/` use `abspath(__file__)`; 12 of them write files via
`HERE`.** The systemd unit ExecStarts the root path, so production is unaffected today -- but any
invocation through `screener/` silently forks the log, and `run_history.py` reads only the root one.
`test_no_shadow_tree.py` caught it, correctly: **the assertion is right and the code is wrong.**

### Prompt vs code: gemma4:12b is NOT broken

The brief says `gemma4:12b RETURNS EMPTY STRINGS. Broken. Never use it.` **`aegis_run.py:26-56`
records that this diagnosis was itself wrong**, and the correction is measured:

> gemma4:12b enables REASONING by default. It writes chain-of-thought into a separate `thinking`
> field BEFORE emitting `response`. Measured on a real triage prompt: thinking 1244-2589 tokens,
> response 39-314 tokens. At `num_predict=512` the model was still reasoning when the budget
> expired, so `response` came back EMPTY with `done_reason="length"`. **That is a BUDGET problem,
> not a broken model.**

`gemma3:12b` remains the default for a different and sufficient reason: it does not reason, so it
needs far less budget. Both statements happen to keep gemma3 selected, which is why the wrong one
survived.


### Dense-data display: the four directives applied, each measured

The brief's dense-table directives, applied to the rendered page and measured before/after:

| directive | before | after |
|---|---|---|
| addresses out of default columns | **182 full 42-char addresses** as visible `<td><code>` text | **0 visible**; 182 truncated `0x34a2…999f` cells, each carrying the full value in `data-full` + a click-to-copy handler, full address in the tooltip |
| drawers do not repeat the row | drawer walked every visible column and reprinted it — on 602 rows | drawer emits only `data-full` cells and `data-extra` K/V telemetry, falls back to the column walk only when neither exists |
| thresholds as micro-bars | utilisation/occupancy as raw `0.9134` / `1.15` | 44px occupancy gauges, green <50 / amber 50-75 / red ≥100 — cbZEC renders a full red bar, matching its BREACH grade |
| high-priority flags are quick filters | passive stat cards | `data-cardfilter` cards funnel through the SAME text filter (one mechanism), scoped to their own `data-section`, keyboard-activatable |
| sticky context in scrollables | sticky `<thead>` only; no pinned column | + `position:sticky;left:0` on the first cell of every dense table, opaque background, inset edge |

**Numbers on the pills are verified against `runway.json`**: `at_or_past_lock`=32 renders 32,
`funded_grade_severe_or_worse`=1 renders 1.

**Not done, on purpose:** TanStack/Tremor/ag-Grid. All three are component libraries with npm
dependency trees; this page is a single generated HTML file with zero external requests, and that
property is what `audit_parity.py` and the 825-assertion suite verify. The directives were applied
directly; the libraries were not. Sparklines in drawers were also skipped — 30 of 61 price
series in `price_cache.json` are all-`null`, so a row sparkline would render empty more often
than not, and an empty sparkline is a worse failure than no sparkline.

**A rename was necessary:** the pools table used `data-extra='1'` to mark extra chain rows, which
collides with the drawer's `data-extra='k:v;k:v'` telemetry contract; the row marker is now
`data-extra-row` and `test_flare_tab`, `test_table` and `test_ui` were updated with it.

Suite after: 825 assertions, 32 suites, 0 failures. report.html and screener/index.html remain
byte-identical.

### Task C: the covariance model — with the two numbers that decided its scope

**The failure mode the brief predicted is measured, and it is dormant here.** 60 markets, 15
eligible, $849,999 of $1,000,000 deployed. The 32 markets failing `VOL_UNKNOWN` are HERMES(25),
RSS(2), FUSD, HOME, kk, GRO and one `None`-collateral market — **every one already AVOID** for
locked/high-LLTV/outlier reasons before volatility is consulted. So the "$0 collapse" path can
only trigger if a series the allocator actually wants goes null — and 15 of 15 eligible markets
carry ≥10 usable prices.

**Ingestion fixed.** `allocator.py` cached a market once on presence, so an all-null series was
never retried. It now refetches any all-null series on every pass (bounded: one request per dead
feed per cycle), keeps the old series on a fetch error so a refetch can only improve the cache,
and prints usable/all-null counts on every run. Rebuilt cache: 31 all-null before, 31 after
refetch (no change — they are genuinely unpublished), 30 usable.

**Two bugs caught while building the model, both asserted against closed forms:**

1. `weekly_returns` bucketed by week and only took a return when a week already held a point.
   The real feed's median spacing is 7.0 days and every week holds exactly ONE point, so it
   returned **0 returns from 108 prices**. Returns are consecutive-point, labelled by the later
   week. Now 107.
2. `_eigs`, an inverse-power iteration, returned **-0.0000 for the identity** and **+3.0 for a
   matrix whose smallest eigenvalue is -1** — wrong in both directions, and a wrong sign here
   means declaring a non-PSD matrix valid. Replaced with cyclic Jacobi (no numpy; the project
   has none) and asserted against closed forms of every sign.

**The model** (`screener/portfolio_corr.py`, 29 assertions):

- weekly returns, cadence-normalised by interval — the sqrt-distortion `test_vol_cadence` guards
  cannot reappear, because nothing is annualised after bucketing;
- **pairwise-complete**: 66 pairs, 30 below the 12-week bar are reported as unsupported and set
  to 0 rather than silently dropped (the full intersection holds only 5 weeks — sUSN is 5 weeks
  old — so a single-period matrix would have been noise wearing a number);
- fixed 0.25 shrinkage toward the diagonal: estimated Ledoit-Wolf needs n > T, and T here is
  often smaller than n;
- **PSD verified: min eigenvalue +0.2495** — the collapse failure mode cannot fire.

**The honest number: correlation COST 0.86% on this book.** Every measured correlation is
positive (0.24–0.75), so the same dollars in correlated assets are more than twice as volatile
as the standalone sum (0.871% → 1.729%). That is not a bug and not a failure of the model — it
is the thing the 30% collateral cap cannot say. The allocator still sizes from sigma-to-breach
and the cap; the panel is diagnostic and labelled as such.

**Runway bound (w_i ≤ runway_i/2) was already enforced** in `evaluate_market` (lines 196-218) —
`runway.json` had gone stale from an 18:04 generation; re-running it against the current run
shows **no position above 0.60 occupancy**, cbZEC's former 1.15 breach now 0.22 after the cap.
The note quoting the old breach is now worded as the historical example it is.

```
sh run_tests.sh   854 assertions, 33 suites, 0 failures   (test_portfolio_corr: 29)
parity            AGREE on 20261008T202645Z
served            HTTP 200, report.html ≡ screener/index.html
```


### Task B: liquidations indexed — 30,934 events, June 2024 to now

**The path nobody had.** The brief said bad-debt timing is unknowable. It is in the API:
`MarketTransaction.type_in: ["Liquidation"]` is a first-class filter, with `badDebtAssets` per
event. Backfilled **30,934 events over 309 pages, oldest 2024-06-13**, serial with backoff
(the project's measured rate-limit discipline; drpc's free tier caps getLogs at 100 blocks,
which made the RPC path not viable — the API route is both cheaper and richer).

**Unit semantics verified against live rows** and asserted against closed forms:
`seizedAssets` is in the COLLATERAL's decimals (WETH 18dp, SOL 9dp), `repaidAssets` in the
LOAN's (USDC 6dp). The first read divided everything by 1e6 and produced "$1.4T seized in 30
minutes"; `normalize()` now carries the decimals with the row, and `test_liquidations.py`
asserts the exact conversion for 9dp/18dp/6dp fixtures.

**The coverage statistic — and the negative result it produced.** 1,261 events since the screen
began (2026-10-07): AVOID 0, CAUTION 1, **REAL 1,260**. That is the headline, stated plainly in
the dashboard's own note: **liquidations are the mechanism of a lending market, not its
failure** — a healthy market with a volatility spike liquidates positions without ever carrying
bad debt. 24,039 of the 30,934 events hit the 60 watched markets, and 23,770 of those are REAL
today. Claiming the 1,260 as misses would be claiming a predictor this screen does not have.
The screen's claim is bad debt: **20 events in the last 30 days, $29.94 total** — and the
all-time record shows why that signal is rare and real: 632 bad-debt events in 2.3 years, 96
material (> $0.01), the largest a $85,008 stTEST event in July 2025.

**USR cross-check.** The screen's $34.8M outstanding bad debt does NOT reconcile to liquidation
events ($296.74 summed over 30 events) — they are different quantities: per-event shortfall vs
the currently-outstanding book shortfall. The screen's figure comes from Morpho's `badDebt.usd`
field, and the verdict timeline shows USR was AVOID at **every one of 120 stored runs** — the
flag was there from the first poll, before any liquidation. That is the honest version of
"our tool caught it".

**Two bugs the testing caught, both fixed and asserted:**
1. The ts cursor stalled when a page returned all-duplicates (the first build sat at "page 30,
   +0" for 20 pages). Stall guard: two identical oldest-timestamps stops the walk.
2. `sync()` toggled the module-global `STORE` for the test path and restored it before the
   FINAL write — so a test run wrote 150 synthetic rows over the real record, passed every
   assertion, and damaged what it verified. The path now travels as a parameter the whole
   way; the test asserts the production store is **byte-identical** across its run.

**Wired in:** `aegis_loop.py` syncs incrementally (2 pages/tick) after alert_diff, reported
without blocking the cycle; the dashboard has a `sec-liqs` table (40 newest, truncated
click-to-copy tx hashes) plus the coverage note; `test_liquidations.py` (28 assertions) covers
units, dedup, cursor, and isolation; NAV has a Liquidations tab.

```
sh run_tests.sh   883 assertions, 34 suites, 0 failures
parity            AGREE on 20261008T225910Z · HTTP 200, report = screener/index.html
                  liquidations.json: 30,934 events · d7 1,345 · d30 2,127 · bad-debt 20 ($29.94)
```

**What task B does NOT yet claim, on purpose:** liquidations cannot be predicted from
util-at-T (measured: they hit REAL markets). The 632 bad-debt events are 96 material events in
2.3 years — too few for a forward test. The statistic that accumulates in future is the flag
coverage table itself; in 6-12 months it becomes the forward evidence the brief's option (3)
asked for.
### The Redis question — answered by measurement, and it uncovered a live exposure

Two claims in the question needed checking before answering, and both turned out to be wrong in
opposite directions.

#### The mesh and the replicas: one real, one not

**The Tailscale mesh is real.** Verified: `tailscale0` at **100.88.95.39**, five peers, including
the local GPU at 100.90.251.75. I had assumed otherwise and was wrong.

**There are no replicas.** This is a **single host**, and it is **not a git repo**. The only
`mcp_server.py` under `agency_bot` is the one in this tree. `systemctl` shows four aegis units and
`mcp-server.service` — and that last one is a **different project** (`/root/mcp-server/server.py`),
not the Aegis audit. The Aegis MCP endpoint **is not deployed as a service at all**; `8010` was
listening only because a process I started was still alive.

So "double-spend across the fleet" has **no fleet to happen in**. The premise of the Redis
argument does not currently hold.

#### What the lock actually does, raced rather than assumed

`flock` serialises writers within one process, but that is a claim until it is measured:
**200 threads contending for 50 credits -> exactly 50 granted, exactly 50 recorded.** No
double-spend, no lost credit. `tests/test_api_router.py` now pins this.

So the honest position: **Redis would be correct the day there are replicas, and there are none.**

#### The exposure the question surfaced — this one is real, and fixed

Checking the bind address found something worse than the ledger question.

```
host public address : eth0 <srv-public-ip>
MCP bind address    : 0.0.0.0   (hardcoded)
```

**The token endpoint was bound to the world on a publicly-addressed host.** That is reachable by
exactly the anonymous callers the gated `/purchase` exists to keep out. And `ts-input` is **not** a
firewall here: it ACCEPTs all tailnet traffic and RETURNs for 100.115.92.0/23, so it protects
nothing on this port. **The bind address was the only control, and it was set to "everyone".**

Fixed by making the bind explicit and defaulting to loopback, matching the pattern already used on
this host by the service on `:8080`, which binds **100.88.95.39 only**. Binding all interfaces now
prints a warning. Verified: public IP **refused**, loopback **HTTP 200**.

### Router bridge and the settlement call — plus two corrections, one of them mine

#### The threshold: changed, and it reclassifies nothing today

`FROZEN_UTIL` moved **0.999 -> 0.95**, tied to the same boundary the allocator and `runway.py`
already use, so **one number governs both the accounting and the alerting**. The reasoning is
right: a market parked at 0.96 has headroom that is useless to anyone exiting size.

**But it reclassifies ZERO markets today.** All 32 FROZEN markets sit at exactly 1.0000, and the
six QUIESCENT ones sit at 0.9087, 0.9011, 0.7675 and 0.0000 — all below 0.95. So this is a correct
**bound for the future**, not a fix for a present misclassification. Claiming it caught markets
would be false.

**And the axes are orthogonal**, which the selftest now pins: a market **above** 0.95 that is still
**moving** is `ACTIVE`, not `FROZEN` — and it is the more dangerous of the two, because it is
heading for the wall at speed. FROZEN requires flat AND at the ceiling.

#### A correction to my own framing: the 15-minute claim was right

I reported a "measured median interval of 0.25h" in a way that implied the 15-minute spec was an
assumption. **It was not.** Measured across 106 gaps: median **15.1 min**, p25 15.0, p75 15.3, with
**75 of them exactly 15 minutes**. The brief's window is measured-correct and my framing was
misleading. What *is* true and still worth keeping: the threshold is expressed **per interval**
with the interval printed, so it stays correct if the cadence ever changes.

The cbLTC jump, checked directly: **11.81pp between 17:23:36 and 17:38:44 — 15.1 minutes.** The
claim is exactly right.

#### The router is bridged

`resolve()` now routes **by id shape**. A 32-byte id is a Morpho market and is matched **first**,
because the 20-byte token regex would otherwise clip it and search for a token address that does
not exist — the silent misroute underneath the 404.

`/audit` on a Morpho market now returns `kind: morpho_market` with **`runway_usd`**,
**`capacity_max_ticket_usd`**, cadence-corrected **`sigma_to_breach`**, **`oracle_flags`**, and the
verdict. Verified end-to-end against a live market id; unknown ids still 404 rather than fabricate.

**A billing bug this exposed:** the credit was spent **before** resolution, so a request for an id
that does not resolve **consumed a credit and returned 404** — charging for an answer never
delivered. Measured: three 404s burned three credits. Resolution now runs **first**; a 404 returns
`billed: false`.

#### Settlement: signed tokens, with the honest boundary drawn

`tokens.py` implements the path you chose — HMAC-signed, expiring, replay-blocked, ledger-persisted.
It replaces an in-memory dict that **lost every token on restart** and a `/purchase` that **minted
one for any anonymous caller.** Issuance is now gated behind `AEGIS_OPERATOR_SECRET`.

**Stated plainly on the endpoint: this is not settlement.** It records that a credit was spent, not
that money moved. Without on-chain verification **the issuer IS the payment system**, which is
precisely why issuance cannot be anonymous. A fleet would also need a database; the ledger is a
locked file.

### Regime segmentation — and the finding that inverts the brief's framing

The brief divides the book into **23 active** and **37 flat, where "telemetry is noise"**. The
23 is exactly right. The 37 is **one population too few**, and the error points the dangerous way.

#### Measured: the flat markets are two different things

```
38 markets with a flat utilisation series
  of those, 32 sit at EXACTLY 1.0000 utilisation for 106 consecutive runs
  6 are flat below the ceiling
```

**A fully-borrowed market cannot move.** No unborrowed capital remains to withdraw, so utilisation
has nowhere to go. Its flatness is the **ceiling, not idleness**. Filing those under "dead capital,
do not watch" would put **the most broken markets in the set the product tells you to ignore.**

They are now a third regime — `FROZEN` — and they need **one alert now**, not sampling. The
three-way split: **23 ACTIVE / 6 QUIESCENT / 32 FROZEN.**

#### The interval claim, checked rather than accepted

The brief says ">5pp within a 15-minute polling window". The ledger's **actual** median spacing is
**0.25h** — measured from the run timestamps, not assumed. The threshold is therefore expressed
**per interval** and the interval is reported beside it. Asserting a 15-minute window without
checking the cadence is the `sqrt(365)` mistake one level up.

The jump claim itself **holds**: **33 single-interval moves above 5pp** across 6290 windows, and
**80 above 2pp**. Largest: **cbLTC 11.81pp, AERO 11.12pp, cbDOGE 10.35pp**.

#### Confirmed on the 55% figure

`1 - 1/0.95 = 5.263%`, and cbZEC's free buffer overstates the runway by **$77,027 = 55.5%** of
$138,757. Both parts check out: the shortfall is **5.26% of supply** expressed against a 9% buffer,
which is where the 55% comes from.

#### Gaps confirmed, not yet closed

- **`/audit` never reaches Morpho.** `resolve()` matches `underlyingTokens` against DefiLlama
  pools. A Morpho market ID resolves to **nothing**, so `/audit` can never return `runway_usd` or
  `sigma_to_breach`.
- **x402 is unwired, and says so.** `/purchase` returns
  `"UNSETTLED — no payment was verified. Demo only."`
- **`/health`, `/pricing` are fine**; `/resolve` and `/audit` are the two that need the router.

### The runway metric — the one claim in the pitch that survived contact with the data

Building the "Run on the Bank Runway" metric found **a live breach in the allocator**, so this was
worth doing rather than pitching.

#### The breach: free liquidity is not the distance to the lock

A Morpho market freezes at **95% utilisation**. The allocator capped each position at
`borrow x 20%` — a **borrow-side** figure that says nothing about how much can be **withdrawn**.

```
runway to the lock = supply - borrow / 0.95
```

**Measured: cbZEC at 91.34% utilisation has $138,757 free but only $61,730 of runway.** The
allocator had assigned it **$70,833 — 1.15x the runway.** The position could not fully exit without
pushing the market to the freeze. It passed the old check because that check compared the target to
*free liquidity*. Every other funded position sat at 0.60 or below, so this was one market, not a
systemic error — and it was findable **only** by computing the runway rather than the free balance.

**Fixed:** a runway rule caps each position at **50% of the distance to the lock** (a policy choice,
not a finding), rejects any market already at or past it, and records the runway in the reasons.
cbZEC's target dropped **$70,833 -> $13,456**. `tests/test_runway.py` (10 assertions) pins the
arithmetic, the breach, and the cap.

#### What the metric is, stated plainly

An **accounting identity** on two published numbers. Verified against the live feed:
`liquidityAssetsUsd == supplyAssetsUsd - borrowAssetsUsd` **exactly**, and
`utilisation == borrow / supply` **exactly**. So it is those two combined, **not new information** —
a dollar budget a risk committee can act on, in place of a percentage it has to interpret. It is a
**capacity, not a rate**: a market at 89% can sit there indefinitely, and one at 60% can gap to the
lock in a single block.

### Claims in the pitch that do not hold

Checked each before building on it:

| claim | finding |
|---|---|
| "velocity: 81% -> 90% in one interval" | **37 of 60 markets never move at all** — utilisation range under 0.1pp across 105 runs. Median range is **0.00pp**. |
| "MCP tool `aegis_verify_allocation`" | **does not exist** — the server exposes `/audit`, `/resolve`, `/health`, `/pricing`, `/purchase` |
| "MCP returns sigma_to_breach, oracle_status" | **`/audit` only sees DefiLlama APY pools**; it never touches a Morpho market or a volatility figure |
| "x402 paywall live at $0.05" | **not wired** — the module's own comment: *"NOTHING HERE SETTLES REAL FUNDS... Wire it to x402/Base USDC before charging anyone."* |
| "$1.3M exit runway for a $15M/91.4% market" | **arrived at by `TVL x (1 - util)`**, which is the derived identity, not a measurement |

The velocity idea is the strongest of the four and **is** real for a minority: **23 markets do move**,
and the movers are meaningful — cbLTC **17.3pp**, AERO **11.1pp**, cbDOGE **10.5pp**, with cbLTC's
own supply crossing the THIN floor inside this session. A move detector is worth building. It should
be built on the 23 that move and should say what it does on the 37 that do not.

### Verified before agreeing it was ready — three findings, one fixed

The "ready" call rested on three claims. All three were **verified against the running system**, and
verifying them turned up a fourth thing that was not ready.

**1. "Timer-run validation proves the caching architecture parses the updated fields."**
**Verified true, and stronger than stated.** `aegis-forward.timer` fires **every 15 minutes**
(`OnUnitActiveSec=15min`), and the run landed at **17:08:26 UTC** from that timer — confirmed in
`journalctl`, not inferred from file timestamps. The production path is
`aegis_loop.py -> aegis_run.py -> allocate()`, which is a **different entry point** from the
`allocate_from_run()` my suite uses. Checked: **both produce identical results** —
16 eligible, $850,000, eligible sets equal, 0 symmetric difference.

**2. "12 of 16 sit in the 0.90-0.914 band."** Verified — and **nothing is at the 95% lock**, so no
position is stranded. The utilisation figures are real.

**3. The 13 -> 16 un-gating.** Verified: WETH, wstETH, cbETH, with sigma `n/a -> 4.12 / 3.96 / 3.96`.

#### The finding that was NOT ready: a silent path to an empty book

The scheduled path **only reads** `price_cache.json`. The module that **refreshes** it
(`allocator.py`) **is not scheduled anywhere** — no systemd unit, no crontab. The cache in place was
written by my own manual fetch, not by automation.

**Measured consequence.** Stripping the volatility fields — exactly what a missing or stale cache
yields — gives:

```
0 eligible of 60 markets   ->   $0 allocated of $1,000,000
fail reason for all 60: VOL_UNKNOWN
```

**And the old code printed nothing in that case**, because the coverage line only printed when the
count was non-zero. So the worst outcome was also the quietest: a cycle that silently allocates
nothing, indistinguishable from a quiet day. That is the **same silent-zero failure class** as the
counter that read 0 for a passing suite.

**Fixed:** coverage is now printed on **every** run, with an explicit WARNING at zero and another
under 50%, naming the cache path and entry count.

#### A second finding: 30 cached series are entirely null

```
cached price series, all prices null   30
fully populated                        11
```

`HERMES, HOME, FUSD, RSS, kk` return **30 real weekly timestamps with every `y` null**. They pass the
`len(points) >= 10` guard because the timestamps are genuine, then contribute nothing, so the market
is rejected as though it had no data. **31 of 60 markets have no volatility** and the page said
nothing about it. Now labelled with a `vol_reason`, and coverage is rendered as a section — because
an all-null series is a **feed** problem worth seeing, not a property of the market.

#### A drop from 16 to 15, investigated and cleared

The next timer run (17:23) showed **15 eligible**. Traced rather than assumed: **cbLTC** failed
`NOT_REAL` — a different rule from volatility. Its supply genuinely fell **$1,084,471 -> $992,007**,
crossing the $1,000,000 THIN floor. **Real market drift, correctly detected.** Not a regression, and
worth stating because a moving eligible count looks like instability.

### The allocator, re-run end to end — 3 markets un-gated, and a correction to my own framing

The volatility fix was re-run through the **whole allocation path**, not just the dashboard. The
result is smaller than the premise assumed, and the difference matters.

| | before the fix | after |
|---|---|---|
| eligible markets | **13** | **16** |
| newly eligible | — | **WETH, wstETH, cbETH** |
| newly rejected | — | **none** |
| deployed | $849,999 | $850,000 |

**A correction to the brief's framing: it is 3 newly un-gated markets, not 13.** 13 was the
*baseline* eligible count; the fix raised it to 16. `sigma_to_breach` moved **2.45 -> 6.51** for
cbBTC and **1.55 -> 4.12** for WETH.

**Why the fix could not be inferred from the unit test.** `test_vol_cadence.py` proves the *maths*
is right but cannot prove the corrected number reaches the rule, because the allocator prefers
`sigma_to_breach` **already stored in the run artefact** (RULE 3). A correct function feeding a
stale cached field would look fixed and change nothing. So `test_allocator_unlock.py` asserts on the
**allocation output** across the two real runs either side of the fix, including the direction
invariant: correcting an inflated sigma can only **admit** markets, never reject them. Measured
cadence split across the correction: **20 weekly, 3 daily**.

### The rebalancing-slippage question — the premise does not hold, and the real risk is elsewhere

The question was how to manage execution slippage when deploying into the un-gated markets. **A
Morpho supply is not an LP position: there is no constant-product slippage to manage.** You deposit
loan tokens into a contract and the rate is set by utilisation. Slippage is an AMM concept, and the
allocator does not touch AMMs.

**Checking all 16 eligible positions against real exit liquidity found 0 that cannot be exited at
target size.** The actual constraint is different, and closer to the lock threshold than is
comfortable:

```
utilisation across the 16 eligible supplies:  0.71 .. 0.914
12 of 16 sit in the 0.90-0.914 band -- "deep, slow exit"
free liquidity per market: $117,889 .. $167,558,203
```

**Nothing is at the 95% threshold where depositors cannot withdraw**, so no position is stranded.
But a supply sitting at 0.91 utilisation has only ~9% of the pool free, which is the condition the
RESERVE_BUFFER exists for — and that buffer is already doing its job: **$150,000 (15%) is held back
by construction**, so the whole deploy is $850,000, not $1,000,000.

**What a rebalance would actually cost.** `MIN_POSITION_USD = $150` exists for exactly this reason: a
5% trigger on $150 is $7.50, and gas is cents, so the deadband binds. The smallest eligible target is
**$25,189** (cbETH) — roughly 168x that floor, so no eligible position is dust.

### Forward stress and exit cost — two engines, and the bug they uncovered

The brief asked for five capabilities. **Two were buildable from data already here; three are not,
and the reasons are recorded rather than glossed.** More usefully, building them found a live bug
in code that was already shipping.

#### The bug: every volatility figure was 2.6x too high

`add_volatility` annualised its price series with `sqrt(365)` **regardless of the feed's sampling
cadence**. The Morpho `historicalPriceUsd` feed returns **weekly (168h)** points for most markets and
**daily** for a few. Annualising a weekly series as though each point were a day inflates it by
exactly `sqrt(7) = 2.646`.

Measured against the live feed:

```
cbXRP       150.5% "annualised"   vs   56.9% true   2.65x
SOL         151.3%                vs   57.2%        2.65x
superOETHb  159.2%                vs   60.2%        2.65x
cbBTC         5.71%/day           vs    2.15%/day   2.65x
USDe          0.4%                vs    0.4%        1.00x   <- daily feed, was correct
```

**Only the daily-cadence markets were right**, which is why it looked like a property of the assets
rather than of the sampling. It mattered because `sigma_to_breach` is derived from these numbers and
gates the allocator's volatility rule: **an inflated sigma rejects SAFE markets for being volatile
when they are not** — the error points the dangerous way. Correcting it took the set of markets with
a >=5% 30-day breach chance **from 15 to 2**. `tests/test_vol_cadence.py` (13 assertions) pins it,
including that a daily feed still behaves exactly as before.

#### Forward stress — the Pre-Mortem was only backward-looking

`stress_forward.py` projects each Morpho market's liquidation path 1/7/30 days under a lognormal
walk at its own measured volatility. **Every assumption is rendered beside the numbers, with the
direction of its error**, because they do not all point the same way:

| assumption | leans |
|---|---|
| markets simulated **independently** (no correlation matrix) | cascade risk **understated** |
| debt held constant, interest ignored | breach **understated** |
| a breach counts as a liquidation, no liquidator delay | realised liquidations an **upper bound** |
| terminal-value breach only, no mid-window dip | first-passage risk **understated** |

**Cascading liquidations and depeg contagion are NOT modelled.** That needs a cross-market
correlation matrix built from a per-market return series, and **this repository stores none** — the
99-run ledger keeps each market's own state, not pairwise relationships. Named on the page, not
buried.

**A bug in my own closed form, found by a discriminating test.** It used `margin` where the correct
numerator is `-ln(1-margin)`. At margin 0.50 that returned 0.0228 against a 200,000-path simulation
of 0.0030 — **a 7x error, making a safe market look risky.** The three original test cases all sat
near zero, where both forms agree, so they **passed trivially and proved nothing**. Replaced with
cases that discriminate.

#### Exit cost — and the finding that it does not re-rank anything

`exit_impact.py` computes exact constant-product slippage for a position at each size, replacing a
boolean flag with a dollar figure. **1,902 pools pass the $1M TVL floor and are still brutal to exit
$1M.**

**Then it checked itself and found the metric is a rescaling.** For a 50/50 CPMM, fixing a loss
threshold makes the largest acceptable position exactly `E/(1-E) * TVL` — measured across all 16,690
ranked pools, **the ratio is identical to 9 decimal places and the ranking is provably identical to
a TVL ranking.** So it converts a flag into a cost, which is easier to act on, but it is **not new
discrimination** — and the page says exactly that, because presenting a rescaling as a discovery is
the failure this project exists to catch.

**Where a real liquidity figure exists, no model is used.** The Morpho feed carries
`liquidity_usd` — the amount actually withdrawable. Measured: **47 of 60 markets hold under 10% of
TVL as free liquidity**, and three (USR, RLP, yUSD — all depegged) hold **zero**. That is a
measurement, not a bound.

#### The three that are not computable here, and why

| asked for | status | what it needs |
|---|---|---|
| tick-level swaps, net-of-LVR yield | **not computable** | archive node + indexer |
| mempool visibility | **not computable** | node with txpool access |
| live contract-invariant monitoring | **not computable** | bytecode reads per block |

The feed carries 28 aggregate fields and **none is a swap, a sender address, or a bytecode slot**. A
prior attempt at net-of-LVR produced an **8,945% loss on a stablecoin pool** because the feed's
`sigma` measures *yield* volatility, not price. **The Base RPC is reachable from here** (verified: block
`0x31eb4b7`), so these are engineering decisions with a cost basis, not blocked work.

A sixth gap the brief named was already closed last turn: the "polling cannot see between runs"
limit is real, but the read side was missing — a jump wrote `location.hash` that **nothing ever
read**.

### The blank-page bug — the sections are NESTED, and the chain tabs hid a parent

**Your report: "when I base or eth or arb the page blanks out." Real, and it blanked on all 17.**

**Root cause.** The `[data-section]` markers are **nested**: `pools` sits **inside** `watch`, and
`lending` sits inside `watch` too. The chain branch did:

```js
sec.style.display = (k === "pools") ? "" : "none";   // keeps pools, hides watch
```

**It hid the PARENT of the one section it kept.** Hiding a parent blanks the child, so the page
rendered nothing.

**A second defect, found while fixing the first.** The chain-tagged table — the 457-row pools table —
**lives in `watch`, not in `pools`**. The `pools` marker holds only the AMM slice, which carries **no
chain tags at all**. So "keep pools" was keeping the **wrong section**: the filter ran against a table
in a different branch of the tree from the one being displayed.

**Fix: hide at TABLE granularity, not section.** A chain tab now shows exactly **one** table — the one
that actually carries chain-tagged rows — and "Everything" restores all eight.

```
sections:   watch(contains pools, lending)  pools  lending
chain:base  -> 1 table shown, 24 rows   (was: whole page blank)
Everything  -> 8 tables, 619 rows
```

### Three test assertions that encoded the bug

`test_flare_tab`, `test_ui` and (earlier) `test_visual` all asserted the **section-name** model that
caused the blank page — "only `pools` is shown", "only `lending` is shown". Those names are **not
where the tables live**, and requiring a nested child to be the sole visible section is exactly the
condition that hides its parent. All three now assert the **invariant instead**: the wanted table is
shown, and **no hidden section contains a visible one**.

`test_chaintab_render` is new — it clicks **all 17 chain tabs** and fails if any leaves the page
blank. This class of bug was invisible to every existing suite.

### The hash was WRITTEN but never READ — shared links went to the wrong view

A jump set `location.hash`, but **nothing ever read it** (`location.hash`: 0 occurrences,
`hashchange`: 0). A recipient opening `#sec-lending` got the right scroll position **inside the
sender's default view**. **Writing a link you cannot read is not a shareable link.**

**Fixed** with `applyHash()`, run at boot and on `hashchange`.

**Deliberately NOT `pushState`.** `replaceState` overwrites the current entry, which looks like the
flaw you flagged — but `pushState` would push an entry per jump, so clicking four jump links and
pressing Back would walk **backwards through anchors** instead of leaving the page. For a document
people arrive at and read, `replaceState` is the better trade. **The missing piece was the read
side, not the write side.**

### The structural truth the deep-link test exposed

**Only `lending` sits inside its own `data-section`.** The other five anchors live inside **`watch`**,
because that wrapper spans nearly the whole page:

```
sec-watch       -> watch          sec-pools      -> watch
sec-lending     -> lending        sec-premortem  -> watch
                                  sec-rwa        -> watch
                                  sec-method     -> watch
```

So jumping to **Pools correctly activates `watch`** — asserting a name match would be asserting a
structure the page does not have. The honest invariant, now asserted, is that **the active tab and
the visible section agree with each other**, plus every deep link arrives where its anchor belongs.

### Three measurement errors of my own, in sequence

1. **I called `boot()` manually**, saw it work, and briefly believed the fix was in — then found the
   automatic path was what mattered.
2. **My deep-link test read a fresh JSDOM synchronously**, before its scripts had run. **A test that
   fails on a correct page.** It now awaits `load`.
3. **My timeout guard fired at 2s**, before a 2.6MB document finished parsing, on the first
   iteration only. Raised to 4s with a single-settle flag.

**All three were the test, not the page** — the eighth, ninth and tenth time this session.

### Your two caveats

- **Back-button / orphaned hash**: `replaceState` was the safer choice, and the gap was on the read
  side. **Now read on load and on change.**
- **`.scrollwin` max-height "508px"**: measured **556px**, and **not a fixed value** — JS sets it
  from a measured row height, so it tracks the row-count slider. A jump to a row inside a scroll
  window is **not** satisfied by window scroll alone; that remains **unverified here** (no layout
  engine) and is the same boundary as `preventScroll`.

### Jump navigation — the one enhancement worth taking from the design review

**Nine tables, ~11,700 words, no map.** A reader landing mid-page had no way to reach a section
without scrolling thousands of rows. A six-link jump strip now sits in the sticky topbar:
**Transitions · Lending · Pools · Pre-Mortem · RWA · Method.**

**Both of your caveats were real, and checking found a third:**

| caveat | verified |
|---|---|
| sticky topbar hides the anchor target | **real** — `h2.anchorable{scroll-margin-top:64px}` |
| an anchor inside a `display:none` section fails silently | **real** — a jump now REVEALS its section first |
| *(found)* the `data-section` markers are not what they look like | `watch` wraps **8 tables and 2.37MB**; the markers sit at **different nesting levels** |

**The third mattered most.** `data-section` values are **markers that run until the next one**, not
wrappers — so anchoring to `#watch` would have scrolled to a container holding nearly the whole
page. Sections are identified by their **`h2` headings** instead, which is what a reader means by
"the Pools section".

**The jump routes through the same path the tabs use**, so the active-tab state cannot contradict the
revealed section. Verified end-to-end: hide everything with the Pools tab, jump to Lending →
section revealed, tab synced, hash set, **zero runtime errors.**

### Two more test bugs my change exposed — and one is significant

- **`test_visual` crashed on a null.** It asserted the badge's `data-sort` on `r.querySelector("td")`
  — **cell 0** — while the badge lives in **cell 16**. It had passed only while the chosen table
  kept its badge in the first cell. Now it finds the cell **containing** the badge.
- **`test_run_history` link coverage failed** on a slack of `-2` calibrated when there were **zero
  membership events**. Today there are 2, and those rows have **no `market_id`**, so no contract
  links **by construction**. The exemption is now **counted, not assumed**:
  `links >= tr - 1 - membership_events`.

**Both were tests encoding an assumption about content rather than the rule.** Neither indicated a
page defect — the page was right in both cases.

### The state-sync caveat already held — now it is pinned

The risk was that a filter hiding the parent while its drawer is open could desynchronise
`class="open"` from `aria-expanded`. **Measured: they agree at every step** — opened,
parent-hidden, cleared. It holds because visibility is a **projection** of state rather than a
second writer, which is the property the earlier refactor bought.

**So it is now an assertion**, checked per table on all three representations at once:

```
class "open"  <->  aria-expanded="true"  <->  drawer visible when parent visible
```

**Falsified:** removing the `aria-expanded` update makes it fail on every table.

### `preventScroll` — applied, and UNVERIFIABLE here

`focus()` was called with no options, so a tall drawer collapsing could scroll its `.scrollwin`
container abruptly. Now `focus({ preventScroll: true })` with a plain-`focus()` fallback for engines
that reject the options object.

**I cannot test this.** jsdom has **no layout engine** — every geometry reports `0` and focus never
scrolls. The option is **correct by specification and unproven by test**, and I would rather say
that than let a green suite imply it was verified. It needs a real browser to confirm.

### Focus was stranded inside a closed drawer — and the dynamic-insertion risk does not apply

**Measured:** focus an anchor inside an open drawer, close it, and focus **stays on the now-hidden
anchor**. The next Tab continues from inside a `display:none` subtree and the reader is lost.

**Fixed:** when a drawer closes and focus was inside it, focus returns to the **disclosure row that
owns it** — the control the user just activated, which is where they expect to be. Asserted
separately, including the inverse: **toggling must not steal focus** from a field the user is in.
Tables with no focusable drawer content correctly **skip** the assertion rather than passing
vacuously.

### The dynamic-row caveat: checked, not applicable

The page has **one** `fetch` — the opt-in Base RPC call — and it **writes a string into a `<span>`**.
It never inserts a row. There is **no polling, no WebSocket, no EventSource, no MutationObserver**,
and **no dynamic row insertion path at all**: the artifact is static, and every listener is wired by
a single `decorate()` pass at load. **Direct element binding is therefore correct here**, and event
delegation would add indirection with nothing to delegate.

This is worth stating plainly rather than silently skipping: **the caveat is real for a live
dashboard and false for this one.** If rows ever arrive after load, the wiring must move to
delegation — and that is the moment to revisit it.

### Drawers were unreachable by keyboard, and unannounced

**Measured: 602 expandable rows, 0 with `tabindex`, 0 with `aria-expanded`.** A drawer could only
be opened with a pointer, and once open nothing announced it — so its contents were unreachable
non-visually. **A larger gap than the `aria-sort` one, on the same surface.**

Fixed and asserted **per table**: `tabindex="0"`, `role="button"`, `aria-expanded` toggled by a
shared `toggleRow()` that both the click and the keydown path call, handling **Enter, Space and the
legacy `"Spacebar"`** with `preventDefault`. Verified on all **6 tables** that have drawers:
**Enter opens, Space closes, `aria-expanded` tracks.**

`aria-expanded` is the correct state for a **disclosure control**; `aria-sort` belongs on the
sortable `<th>`. The two are not interchangeable and both are now explicit.

### The searchability caveat: checked, and NOT a real gap

The caveat was that a term present only in a drawer would hide its row. **Measured across all 602
drawers: every `.dv` value is a copy of a cell already in the parent row — 602 duplicate, 0 add
novel text.** There is nothing in a drawer that is not already searchable.

**So I removed the assertion I had written for it.** A test asserting a gap that does not exist can
only pass for the wrong reason.

### A regression I introduced, and the measurement that caught it

Merging the *whole* drawer into the searchable text made **every row match any header word** — the
drawer repeats the column labels (`when`, `run`, `block`…), so filtering on `"when"` hid nothing.
**Section 5 failed with "no row was hidden"**, which is how it surfaced.

**Fixed by indexing only the `.dv` values, never the `.dk` labels.** The filter now searches what a
reader would search and nothing more. **Three of my own changes broke something this turn; each was
caught by an existing assertion rather than by inspection.**

### Your keyboard caveat was right — and the drawer was a THIRD writer of the same property

**Keydown was already correct** (`e.key === "Enter" || e.key === " "`, with `preventDefault`). But
you were right that it needs to be explicit: removing `role="button"` means **Space no longer fires
a native click** on the `<th>`, so that handler is the *only* thing keeping Space working. It is
now asserted for **every** table rather than one.

### The third instance: drawers had two sources of truth

`wireDrawers` read `d.style.display` to decide the next state **and** wrote it, while
`applyVisibility` also wrote it. **Two readers, two writers, one property** — the same defect as
the filter/tab clash, found by testing the same composition on the drawer dimension.

Worse, `applyVisibility` **forced every drawer row to `display:none`**, and because the parent row
is visited *first* and the drawer row *second*, the drawer's own iteration **clobbered the decision
its parent had just made**. Measured: clicking a row set `class="open"` but the drawer never
appeared.

**Now:** the class is the state, visibility is derived from `(parent visible && open)`, and the
drawer row is **skipped entirely** in the loop because its parent owns it.

**Verified across all 6 tables that have drawers:**

```
closed -> open -> hidden-by-filter -> restored-on-clear -> closed-in-one-click   PASS ×6
```

### A test error I made and corrected mid-flight

I reported "step 3 wrong: the filter doesn't hide the drawer." **It was my test's fault** — the
needle was `"a"`, which the parent row *does* contain, so leaving its drawer open was **correct**.
Re-testing with a needle the parent cannot match (`"zzzznotpresent"`) showed the filter working.
**Asserting the wrong expectation is indistinguishable from finding a bug until you check the
input.**

### Two writers, one CSS property — the compound-filter coupling was real

You called the shared `style.display` as the central defect, and **testing the composition found a
SECOND instance**, worse than the first:

```
1 baseline                 : visible=443  extras=0
2 chain:other selected     : visible=36   extras=15    (the tab WAS active)
3 + global search          : visible=3    extras=0
4 search cleared           : visible=443  extras=0     <-- 443, not 36
```

**The tab still read `aria-selected="true"` while showing the All view.** The UI claimed a filter
it was not applying. Same root cause: **a shared CSS property with two uncoordinated writers.**

**Fixed as you suggested — visibility became a FUNCTION OF STATE rather than a mutation each
handler performs.** One `rowWanted(tr, q)` declares every dimension; one `applyVisibility()`
evaluates them together. Adding a third dimension can no longer clobber the first two.

**Verified at every step:** `443 → 443` after filter/clear, and `36 → 18 → 36` across the tab +
search round trip. The tab state is preserved.

### aria-sort — your recommendation would have shipped inert markup

**`role="button"` REPLACES the implicit `columnheader` role, and `aria-sort` is not supported on
`role=button`.** It would have been **ignored by assistive technology** — markup that looks
accessible and announces nothing. `table.js` was already setting `role="button"` on every header,
so adding `aria-sort` beside it would have been silently void.

**Fixed at the cause:** the role override is **removed**, so each `<th>` is implicitly a
`columnheader` — the only role `aria-sort` is valid on. It sets `aria-sort` to
`ascending`/`descending`/`none`, resets the others to `none` when a different column becomes the
key, and keeps `tabindex="0"` for keyboard focus.

The test asserts **the two attributes agree** (`data-sort-dir="asc"` ⟺ `aria-sort="ascending"`),
that **at most one column** reports a direction, and that **no sortable header is missing** one.

### Testing filter x sort composition found a real bug — and a test that encoded it

The filter and the sort were tested **separately and never together.** Composing them across all
8 tables found a **user-visible product bug:**

```
STEP 1  default view        : visible=442  extras-visible=0
STEP 2  type a filter       : visible=457  extras-visible=15
STEP 3  clear the filter    : visible=457  extras-visible=15   <-- never went back
```

`applyFilter` set `tr.style.display = ""` on every MATCHING row. **An empty string clears the
inline `display:none`** that `applyChainFilter` had set — so a *transient* filter **permanently
un-hid the 15 `data-extra` Flare rows**. Only a page reload restored the default view. **A
transient interaction must never make a permanent change.**

**Fixed** by treating a row as shown only if nothing else is hiding it, and **verified**:
442 → 442 → 442. The chain tabs still reveal the extras, which is their purpose.

### And a test that had encoded the bug as correct

`test_ui` compared *"rows visible after clearing"* against ***all* non-drawer rows** — and it
passed **only because of the bug.** Measured: the default view is `[65,8,5,15,443,6,10,59]`; all
data rows is `[65,8,5,15,458,6,10,59]`. **The test expected 458 where the correct answer is 443.**

Fixing the product bug turned that test red, which is how it was found. The baseline is now the
**default view**, plus a stronger invariant: **no `data-extra` row is ever revealed by
filtering** — asserted separately on all 8 tables.

**This is the most useful failure of the session: a test that passes because the code is wrong.**
It is the same shape as the substring assertions that passed on code that threw — the check
agreeing with the defect rather than with the intent.

### Widening the sort check to all 8 tables found FOUR bugs — all in the test

The sort assertions ran against **one** table (`tables.find(...)`). The other seven were never
sorted in any test, **though all eight are interactive and every one has a column with distinct
sort keys.** Exercising each on its own best column exposed four defects, and **every one was
mine, not the page's:**

| # | defect | measured symptom |
|---|---|---|
| 1 | header excluded only `if (!tb.tHead)` | table[2] has **no `<thead>`**; the header row leaked in as data |
| 2 | sort key read `textContent`, ignoring `data-sort` | cell renders `RUSR`, carries `data-sort="USR"` — page sorts on `USR`, test compared `RUSR` |
| 3 | column probe omitted the **drawer filter** | **64 of 129 body rows** are `data-drawer` detail rows with **one cell**; `cell[11]` was `undefined`, so the chosen column was computed over the wrong population |
| 4 | assumed "the first click is ascending" | section 3c had **already clicked every header**, so section 4's first click landed on **descending** and inverted every assertion below |

**#4 is exactly the shared-state hazard flagged earlier** — a test reading state a previous
section left behind, not a flake. Section 4 now **drives to a known direction** and asserts it got
there, with a bounded loop so a header that never sets the attribute fails loudly.

**#1 and #2 are the same mistake in two places: the test approximating what `table.js` does.** The
page's `dataRows()` filters `tr === header.row` unconditionally and its `cellText()` prefers
`data-sort`. **A test that re-derives the production rule instead of mirroring it will disagree
with it** — and here it disagreed four times.

**Result: 8 of 8 tables now exercised, each on a column with 4–353 distinct keys.**

### The buffering deadlock — I had `flush=True` by accident, and PROVED it is load-bearing

The handshake reads the server's port from a **pipe**, which makes Python block-buffer stdout.
Without a flush the port line sits in the buffer and `readline()` blocks. **`serve_preview.py`
already had `flush=True`, but nothing said it was required** — and "it works" is not the same as
"it is load-bearing".

**So I removed the flush and ran the handshake with a 20s cap.** It **did not return**. Restored, it
returns in **0.1s**. That is the difference between a green suite and a suite that hangs until the
runner kills it.

The failure path is bounded either way — a 15s deadline — but the message now **names the cause**
rather than leaving the next person to rediscover it.

### Header-signature collisions — measured, and now guarded

**Measured across all 9 tables: exactly 1 carries `chain|project|symbol`.** So the fallback is
unambiguous today. But it is only valid while that stays true, so the uniqueness is now an
**assertion** rather than an assumption.

**Falsified:** injecting a second table with the same three headers fails the guard
(`identifies exactly ONE table (2)`).

Full header census, for the record:

```
when(utc)|run|block            rule|meaning|markets       collateral|supplied|unrealised
collateral|supplied|util       chain|project|symbol  <-- 1 match    strategy|beat|runs
asset|buy&hold|strategies      pool|project|chain         (empty)
```

### The hardcoded test port — proven, not theorised

`test_gzip_server` bound port **8097** as a module constant. **Verified the collision rather than
assuming it:** a second bind fails with `[Errno 98] Address already in use`.

The fix could **not** be `listen(0)` as suggested, because the port is a **CLI argument to a
subprocess**. So the server was changed to print the port it **actually bound**
(`srv.server_address[1]`, not the requested value) — with `PORT=0` the requested value is
meaningless and a caller reading it would connect to port 0. The test now requests **0**, parses the
bound port from stdout, and passes it to `get()`.

**Proven under concurrency:** three simultaneous copies, **12 assertions each, zero failures.**
Previously that would have been one pass and two `EADDRINUSE`.

Audited the rest of the suite for the same class: **no other hardcoded ports, and no shared-file
writes.** The two writers (`test_audit_parity`, `test_snapshots`) both use `tempfile`.

### Content anchors degrade — so the degradation is now explicit

The `:has(a[href*="defillama.com/yields/pool"])` approach has the caveat you named, and it is
**measurable here**: with every `DL` link stripped, the content anchor finds **NOTHING** and a
silent fallback would assert against the wrong table — the same failure as the positional selector
it replaced.

The fallback is now **by header signature** (`chain|project|symbol`), identifying the table by its
**shape** rather than by position or by data that may legitimately be absent. **Falsified:** with
all 457 `DL` links removed, the table is still identified correctly (PASS) while the missing links
are separately reported (FAIL). The two conditions are distinguished rather than conflated.

### The mirror fallacy — and a falsification that PASSED when it should have failed

Reimplementing the comparator inside the test carries the inverse risk: **if the test and the
production code share an edge-case assumption, both agree and the test passes on a broken spec.**
That was a fair criticism of what I wrote, so section 4 is now **property-based** — the checks
encode **no algorithm**, so a shared misconception has nowhere to hide:

| property | what it asserts without any comparator |
|---|---|
| **P1** | ascending output is **non-decreasing** — the defining property of a sort |
| **P2** | equal keys keep their **pre-sort relative order** (stability) |
| **P3** | asc → desc → asc returns to the **same** order (idempotent round trip) |
| **P4** | the **multiset of keys is unchanged** — nothing lost or duplicated |
| **P5** | row count unchanged |

### The falsification that did not work, which is the real finding

I inverted the comparator (`dir` → `-dir`) and reran. **P1 PASSED.** A broken sort slipped through,
so I chased it, and found **three** layered reasons:

1. **`Array.prototype.sort` is stable since Node 11.** My first falsification removed the index
   tie-break, which is a **no-op** — the engine still guarantees stability. Dropping the tie-break
   cannot make a sort unstable in this runtime.
2. **The test clicked column 0, `when (UTC)`.** `table.js`'s `NUMRE` is `/-?\d[\d,]*\.?\d*/`,
   which matches the **`2026` prefix** of an ISO timestamp — so `num()` returns **2026 for every
   row**. Measured: **1 distinct sort key across 126 rows.** Sorting that column is a no-op.
3. So P1 asserted something true of a **constant** sequence, and *any* comparator passes.

**The column choice was itself part of the test's validity, and I had not treated it as such.**

### What fixed it

- The test now selects the sortable column with the **most distinct sort keys**, measuring
  distinctness **by the key `table.js` computes**, not by raw text — 126 different timestamps look
  like 126 distinct values and are one key. It now picks column 11 (TVL, **64 distinct**).
- Numeric classification **mirrors `num()`** rather than my own idea of numeric. Requiring the
  whole string to parse classified `$11.1M` as lexical and asserted the wrong ordering.

**Re-falsified:** with the comparator inverted, **P1 and the descending check now both FAIL.**

### Your `data-section` recommendation — measured, and it would have made things worse

You suggested scoping to `div[data-section="watch"] table` / `div[data-section="pools"] table`.
**The scopes are misassigned.** Measured across all 9 tables:

```
watch    -> the transitions table            (correct)
lending  -> 6 tables, including the POOL table   <-- wrong
pools    -> 2 tables, including the RWA table    <-- wrong
```

`data-section` here is a **marker that runs until the next one**, not a wrapper, so the "lending"
scope swallows the 457-row pool table. Anchoring tests to it would have pointed the pool
assertions at the **transitions** table. **The pool table is identified by content** (the dense
table carrying `DL` links), which is what the code already does and what I kept.

### test_table / test_lookup: behavioural sorting, and two non-findings

The remaining `indexOf` checks were upgraded. **Two of the three named patterns did not exist:**

| recommendation | finding |
|---|---|
| replace `className.indexOf('foo')` with `classList.contains` | **0 occurrences** in `test_table.cjs`. Nothing to fix. |
| add a zero-assertion guard per suite | **already present** in `run_tests.sh`: `PASS but reported 0 assertions` |

**I checked before changing rather than applying a fix for a pattern that was not there.** The
third recommendation — verify sorts behaviourally — was the real one.

### The sort is now checked for CORRECTNESS, not just for movement

Section 4 previously asserted only that the row order **changed**. A table that shuffled rows at
random would have passed. It now **reimplements the documented comparator** and compares:

```
ascending:  numeric when every key parses as a number, else lowercase lexicographic;
            empties last; ties fall back to the original index (stable)
```

**A wrong sort now fails.** Keyboard parity was added too: the header is `role="button"` and must
sort on **Enter and Space**, or the table is unusable without a mouse.

### The assertion I got WRONG, and what it revealed

My first version asserted `descending === ascending.reverse()`. **It failed — and the code was
right.** Reading `sortTable`, `dir` multiplies the KEY comparison but **never the tie-break**
`(a[2] - b[2])`, so equal keys keep their original order in **both** directions: a deliberately
stable sort. Measured on the clicked column: **126 rows, 100 distinct keys, 26 duplicates**. With
duplicates present, reversing ascending is not the same as sorting descending.

**So I asserted the properties that ARE true** — keys ordered correctly, and duplicate keys forming
one contiguous run rather than being scattered. **The failure was my test's assumption, not the
implementation's behaviour**, and testing the tester is a real risk when the spec is inferred.

### Two sloppy things I wrote and removed

- **`check("Space on the header sorts it too", true)`** — a literal `true`. **An assertion that
  cannot fail**, the exact anti-pattern this whole exercise targets. It now compares the direction
  attribute before and after.
- **Two dead loops** in the grouping check, left behind by an incomplete rewrite. Replaced with one
  honest pass that returns `false` when a key reappears after a different key.

### A positional selector that silently picked the wrong table

`d.querySelector("table.dense")` grabbed the **transitions** table — there are **three** dense
tables and the pool table is the **second**. Three assertions failed for a reason unrelated to the
change under test. The pool table is now identified by **content** (the one carrying `DL` links),
not by position. **The old `slice(indexOf(...))` code had the same latent flaw**; it just happened
to slice from a marker that only the pool table contains.

**Falsified:** re-injecting a `GT token` pill into the pool table produces a FAIL naming it.

### The JS gap closed — and it caught a live bug on the first run

I converted `test_lookup` and `test_table` from grepping JavaScript source to **executing the
page**. It immediately found something no substring check could:

```
ReferenceError: dl is not defined
```

`app.js` defined `const dlink = ...` and then rendered `${dl}` in the template. **Every lookup of
an unknown address threw and rendered nothing.** The old assertion —

```js
ck("offers a next step that resolves it", /basescan\.org\/token/.test(src)
                                        && /dexscreener\.com\/search/.test(src));
```

— **passed the whole time.** Both URL fragments were present in the source. The check was satisfied
by code that could not run. That is not a hypothetical about comments; it is the exact failure
mode, and it was live on the page.

**Fixed** (`${dl}` -> `${dlink}`) and **falsified**: re-introducing the typo produces **4 FAILs**,
restoring it goes green.

### What replaced the string searches

`tests/_jsdom_util.cjs` loads `report.html` in jsdom with scripts executed and exposes the page's
own functions. The page is self-contained by design, so its `window` is the real thing:

| instead of | the test now |
|---|---|
| `indexOf('setAttribute("data-interactive"...)')` | every multi-row table **is** marked, and an injected undecoratable table **is not** |
| regex on `app.js` for the coverage message | types an address, presses Enter, **reads the rendered text** |
| regex for link URLs | reads the **resolved `href`s** off the returned anchors |
| regex for the opt-in button | asserts `#oc` **exists in the rendered output** |

**`decorate()` is inside an IIFE** and cannot be called directly, so section 3 asserts the
**observable consequence** rather than reaching for the internals: a table with several rows and
no marker is a **stranded** table.

### And the harness caught itself

`run_tests.sh` globbed `tests/*.cjs`, so the new helper was swept up and reported
**"PASS but reported 0 assertions"** — a helper masquerading as a passing suite. **The same
silent-zero failure the Python side already guards against.** The glob is now `test_*.cjs`, and
the helper is `_jsdom_util.cjs`.

### Assertion fragility: fixed at the root, not re-worded

**Failing on my own explanatory comment happened twice** in this project. Both times the fix was
re-wording, which treats the symptom: a substring check cannot tell code from prose about code.
Three more suites were asserting on source text and had simply not been unlucky yet.

`tests/srcint.py` inspects Python **structurally**, via the AST. **Comments do not exist in an
AST**, so false positives from prose disappear by construction rather than by careful phrasing.

| helper | answers |
|---|---|
| `called_names` | which functions are CALLED (so `unlink` in a comment is not a deletion) |
| `call_kwargs` | the value passed as `timeout=` on the actual call, whatever it is spelled |
| `call_positions` | the ORDER of calls — a real invariant, not a text position |
| `function_returns` | what `main()` actually returns (exit codes), not the text `return 2` |
| `strings_in_code` | string **literals**, excluding comments but including docstrings |
| `has_comment_mentioning` | the inverse — asserts a hazard is **documented** without confusing it for the hazard |

### Six assertions converted, each falsified

| was | now |
|---|---|
| `"export_report.py" in src` | AST call ORDER — a comment naming the file cannot satisfy it |
| `"return 2" in src` | `function_returns("main")` contains 2 |
| `"rmtree" not in src` | `called_names() ∩ {rmtree, unlink, remove}` is empty |
| `"timeout=300" in src` | a `timeout=` kwarg with a positive int, on the real call |
| `"read-only" in src` | the **module docstring**, then the **executed** `tool_get_changes()` response |
| `"Collision would silently destroy" in src` | that note **AND** an actual `exists`/`isfile` guard |

**Falsified, not assumed.** Making the symlink absolute, removing the `fsync`, and stripping the
MCP framing from the returned payload each produced a FAIL naming the right assertion. **A guard
that cannot fail is worthless**, and the first attempt at the `index.html` guard proved that.

**One assertion now EXECUTES the program.** `test_publish` section 4 asserted the text of its own
source file. It runs `publish.py` twice now — once plain, once `--quiet` — and compares output
length. **A statement about my test file was never a statement about the program.**

### What the helper cannot do

It is **not a sandbox**. Rebinding through an import, `getattr`, or a call through a variable is
invisible. Use it for structural facts and **execution for behaviour**. It says so in its own
docstring so the limit travels with the tool.

### The AMM index now keeps history (append-only snapshots)

`screen.py` overwrote `results.json` on every run, so **the previous screen was destroyed** and no
delta could be checked against anything. That is why a summary could report *"19 pools bled out
below viability"* when the files showed **49 FEWER dead pools** — nothing on disk could contradict
it. An ephemeral screen is not an auditable time-series.

```
screener/snapshots/<YYYYMMDDTHHMMSSZ>.json   <- written once, never rewritten
screener/results.json -> snapshots/<ts>.json  <- relative symlink, swapped atomically
```

**Two guarantees, and they are separate:**
- **Append-only** — same idea as `runs/` for lending. A snapshot is never rewritten, and a
  timestamp collision **refuses and suffixes rather than overwriting**.
- **Atomic pointer** — `json.dump` onto a live path has a window where a reader sees a half-written
  file; `os.replace` on a temp **name** has none. A reader opens the old snapshot or the new one,
  both complete. The payload is `fsync`ed before the pointer moves.

The link is **relative**, and that is load-bearing: `os.path.getmtime()` **follows** symlinks and
`build_v2.py` derives the AMM age from `results.json`'s mtime. Verified it still resolves.

### Two historical snapshots were recovered

Both were about to be lost: the live `results.json` (the only copy of the 13:33 screen) and
`results.json.bak`. They are now `snapshots/20261007T135954Z.json` and
`snapshots/20261008T133303Z.json` — **the pre-change baseline that did not exist before.**

### The keying bug, and the measured reason it matters

`screen()` was dropping the DefiLlama `pool` UUID, so a diff fell back to
`(chain, project, symbol)`. **Measured against the live feed: 16,723 pools collapse onto 14,083
distinct triples — 1,405 triples map to more than one pool, hiding 2,640 rows.** The worst is
`('Base','morpho-blue','CBBTC')` at **five distinct pools**. A symbol-keyed join counts five real
pools as one and makes any re-classification among them invisible.

`screen.py` now carries the UUID. The two backfilled snapshots were **backfilled rather than
guessed**: **25,192 rows keyed, 7,986 left `None`** because their triple maps to several pools, and
**375 absent from the feed**. Assigning "the first match" would attribute one pool's history to
another — worse than an admitted gap.

### The bug the third check found: split identity, not collision

`_index` mixes uuid-keyed and fallback-keyed records **in one dict**, so the same pool is keyed
differently depending on whether its uuid survived. It is then reported as **`gone` by its fallback
key and simultaneously `appeared` by its uuid.** Measured on the real pair: **366 phantom "gone",
25 phantom "appeared", every one fallback-keyed.** A diff that invents 391 membership changes from
a keying artefact is worse than no diff, because the numbers look like market activity.

Fixed by namespacing the fallback (`sym:` — a uuid can never contain it) so the two families cannot
collide, and by **counting duplicate keys instead of silently overwriting** — a dropped row is
indistinguishable from a pool that closed.

### Retention: the blueprint's math was two orders out

*"4 snapshots daily, 90 days is only 360 files"* — but each snapshot is **7.1 MB**, so:

| | size |
|---|---|
| 360 files uncompressed | **2.50 GB** |
| 360 files gzipped | **0.48 GB** |

41 GB free, so **nothing needs pruning now**, and I have **not** added it. The trap to avoid
first: the blueprint's `glob.glob("snapshots/*.json")` **loses `.json.gz` files** once old
snapshots are compressed, and `sorted(...)[-2]` then returns a **wrong previous** rather than
raising. `list_snapshots()` accepts both extensions and that is asserted.

### AMM cadence: daily -> 6-hourly, and a provenance line that had gone false

**The reasoning was already right** — DefiLlama's `/yields` scrapers crawl on multi-hour cycles,
so a 15-minute poll of a slow feed returns the same record while spending bandwidth and risking
429s. **The question was only whether daily was the right bound.**

Daily is **0-24 hours stale, mean 12** — so the page spends half its life showing a figure more
than half a day old. **6-hourly bounds it at 6** and makes the age line a statement about the
**schedule** rather than about when someone last remembered to run it by hand.

```
OnCalendar=*-*-* 00,06,12,18:00:00 UTC
AccuracySec=5min          <- kept; the proposal omitted it
Persistent=true
```

Verified with `systemd-analyze calendar` **before** installing, and `systemd-analyze verify`
after. The restart fired a run immediately: **16,723 pools screened, `results.json` 0 minutes
old**, next elapse 18:00 UTC. **Enabled at boot.**

### The bug this uncovered: the page described a process that no longer existed

Removing the manual-build text was on the list. What the edit revealed is worse:

> *AMM Index Provenance: DefiLlama snapshot 2026-10-08 00:00Z · 13.5 hours old · **refreshed by a
> manual build**, on a slower cadence than the lending feed above.*

**`aegis-amm.timer` had existed the whole time.** The line was written when a human did run it by
hand, and kept saying so after systemd took over. **A provenance line that describes a process
that no longer runs is worse than no provenance line, because it is believed** — the same failure
as the ORACLE_FLIP banner, in prose.

It now reads:

> *on a **6h batch (00/06/12/18 UTC)**, slower than the 15-minute lending feed above. DefiLlama
> indexes pools on a multi-hour cycle, so a faster poll would return the same record.*

**The age is still MEASURED from the file mtime, not assumed from the schedule.** If the timer
stops, the age keeps climbing and the claim is visibly falsified — the cadence text cannot hide a
dead job.

### An assertion that reads the INSTALLED unit

`test_provenance_split` now opens `/etc/systemd/system/aegis-amm.timer`, compares its `OnCalendar`
to the cadence the page prints, and fails if they diverge. **Testing a comment is worthless; this
tests the thing that actually schedules the job.**

**My first version of that assertion failed on my own explanatory comment** — it grepped the
source file, which legitimately quotes the old wording. Scoped to the emitted page, which is what
the reader believes.

### ORACLE_FLIP: it was never broken. The WARNING was.

An overnight summary reported *"ORACLE_FLIP is currently suppressed or unable to evaluate."*
**Measured, it is neither.** The check runs on every interval and has done so all day.

```
alerts.log records logged TODAY : 56
  reporting a gap               : 0
```

**What actually happened.** `get_unchecked()` deduped by check name across the **whole
append-only log**, so one gap kept the banner on forever:

```
the 7 records carrying unchecked, all in one backfill:
  idx 0  to_run=20261007T184028Z  logged_at=2026-10-07T20:25:51Z
  idx 6  to_run=20261007T184517Z  logged_at=2026-10-07T20:25:51Z
the newest record:
  idx 83 to_run=20261008T132040Z  logged_at=2026-10-08T13:20:40Z  unchecked=0
```

**Seven records, all written in a single backfill 17 hours earlier, from runs whose
`markets.json` predated the `oracle_type` field.** Every run today has that field in **60 of 60
markets**, and the check is evaluating against consecutive intervals exactly as designed.

So the page was printing a **live alarm for a gap that closed overnight** — and the reader was
right to ask why. **A warning that is always on is a warning that gets ignored**, which is the
same failure as the permanently-tripped parity tripwire this project already fixed once.

### The fix states the age instead of the alarm

`get_unchecked()` now returns **`state: "current"`** or **`state: "historical"`**, bounded by
`UNCHECKED_RECENT = 4` records (~an hour at the 15-minute cadence). The banner reads:

> *Earlier in this log, **ORACLE_FLIP** could not run (last seen 77 intervals ago). Now running
> normally. Those stretches are excluded from the current assessment.*

**Reported, not suppressed.** The opposite error would be worse: silence from a detector that
never ran is not stability, which is exactly why this section exists. The reader can see the
detector *was* blind and that it no longer is.

### And the correction that matters for the second question

**`screener/` is not a duplicate directory.** Measured: **60 symlinks and 26 real entries**, and
**24 of those 26 are screener-only** with no twin at the root — `screen.py`, `table.js`, `app.js`,
`mcp_server.py`, `results.json` and the rest. Only **two** real duplicates exist:
`screener/tests/{test_lp_economics,test_lp_engine}.py`, **byte-identical** to their root copies.

So "unifying the duplicate directory" is largely **already done**, and the two remaining files are
a **two-file cleanup, not an architectural project**. `test_no_shadow_tree` now enforces this.

### Links trimmed to DL + official (the 736KB that paid for itself)

On request, the GeckoTerminal and DexScreener links are gone. **Both pointed at the underlying
TOKEN, not the pool** — DefiLlama publishes no pool address — so each needed a `title` explaining
what it *was not*, and `search` was a symbol query that could land on any pool with a similar
ticker. **Two links whose labels have to apologise for themselves are not worth the column.**

| | before | after |
|---|---|---|
| blob | 2,766.8 KB | ~2,030 KB |
| **report.html** | **3,527,039** | **2,596,282 (−26%)** |
| **gzipped on the wire** | **512,019** | **449,314** |

**The removal saved more than the whole gzip exercise did in absolute terms.** Both are now in
place: −736KB from the data, then 6x on top of that from the encoding.

**What was kept, and why it is the right pair:** `DL` opens the *pool* on DefiLlama, which is what
the row is about, and `official` is the only link that identifies the **protocol**. The official
site is **not stored per row** — it is per-protocol, so carrying it 460 times would be waste; it is
resolved at render time from the registry, **reusing the same alphanumeric normalisation** that
lifts that join from 28% to 98%. **457 of 460 pool rows got one; the 3 that did not show nothing
rather than a guessed URL.**

### Removing a source of links is not the same as refusing to understand one

`app.js` still **parses** pasted GeckoTerminal and DexScreener URLs. The two are unrelated:
*rendering* them was removed because they address the wrong thing, but a user arriving with such
a URL is **holding a perfectly good address**, and refusing to read it would be a worse failure
than the one being fixed. The search box placeholder still shows a `dexscreener.com/base/0x...`
example for the same reason. **A test now asserts the parser survives while the pills do not.**

### Two tests inverted rather than deleted

- `test_lookup.cjs` asserted the pills read `GT token` / `DS token`. **Inverted:** it now asserts
  they are **absent** and that `DL` and `official` **remain**, so their reappearance fails loudly.
- `test_official_links.py` used *"rows carrying a GeckoTerminal or DexScreener link"* as its
  denominator. With those links gone that selector matches **zero rows — and the check would have
  passed by finding nothing**, which is the exact failure mode its own docstring warns about.
  **Reworked to use every pool row as the denominator** (431 assertions total, up from 428).

### Problem 2, costed: where the 3.4MB actually is

Measured, not estimated:

```
DATA blob (one inlined JSON)   2766.8 KB   80%
  of which `links`             1057.2 KB   38% of the blob -- 4 URLs per row
  of which `reasons`            384.5 KB   14%
  of which `toks`               216.0 KB    8%
page total                     3444.3 KB
```

**And the discovery that reframes it:** the page carries **3,424 embedded objects** for a lookup
box and an audit card, but the largest table renders ~500 rows. **86% of the embedded objects are
never displayed.**

### The fork, with numbers

| option | wire size | cost | what breaks |
|---|---|---|---|
| **gzip the response** | **0.51 MB (14%)** | ~1 hour | nothing. File, page, architecture all unchanged |
| drop unused blob rows | ~1.5 MB | 2-3 h | the lookup silently loses coverage -- **a bug, not a speedup** |
| columnar / dictionary | ~1.2 MB | 1-2 days | rewrites every row consumer |
| fetch data at load | ~50 KB | 3-5 days | **kills the one-file, zero-external-request property** |

**gzip is 6x smaller for a tenth of the effort of anything else, and it is the only option that
changes nothing else.** So it is what I did.

### What was built

`serve_preview.py` -- a static server that gzips, with the four rules that a naive one gets wrong
(only when asked; never for already-compressed types; `Content-Length` matching the body;
`Vary: Accept-Encoding`). **3,527,039 -> 512,019 bytes, byte-identical after decode.**

### Two bugs I introduced and caught in my own server

Both were the same shape -- **two clients, two documents, one URL** -- which is exactly the bug
this session already fixed once:

1. **`/` served a directory listing.** `directory=ROOT` made the root list file names, because the
   page lives in `screener/` and the root has no `index.html`. The obvious URL showed 13KB of
   filenames instead of the dashboard.
2. **`/` served *different things* depending on `Accept-Encoding`.** When not gzipping, I fell
   through to the base handler, which re-translated the *original* `self.path` -- so gzip clients
   got the page and everyone else got the listing. Fixed by serving the resolved path in both
   branches, and pinned with an assertion that the two responses are **identical**.

**The second one only surfaced because I tested both encodings against the live server.** A test
of the gzip path alone would have passed.

### Now managed, not detached

Replaced a bare `setsid` process (ppid=1, a log file, no supervision) with
`aegis-preview.service` -- `Type=simple`, `Restart=always`, enabled at boot. This project already
schedules with systemd; the preview was the one piece outside it.

### CORRECTION: the pool refresh WAS scheduled

**This morning I told the user "the pool half is not scheduled at all". That was wrong,** and the
way it was wrong is the useful part.

I ran `crontab -l`, found no pool entry, and stopped. **The project is scheduled by systemd, not
cron.** `aegis-amm.timer` has been running "Refresh the Aegis AMM index once daily" all along, and
the journal shows a clean success at 00:00:09 UTC: 16,735 pools scanned, 1,308 REAL.

**The tell I ignored:** the runs directory was 7 minutes old while `results.json` was 595 minutes
old. Two timers at different cadences is the *intended* design -- the code says so in a comment.
I read "different cadence" as "one of them is broken" because I had only looked at one scheduler.

**Lesson: absence of evidence in one place is not evidence of absence.** I checked cron, found
nothing, and reported a finding. A second scheduler existed the whole time.

### The bug that WAS real: two front doors, one page

`screener/index.html` was a **REAL FILE COPY** of `../report.html`, not a symlink, and it was
**8 hours stale**. `python3 -m http.server` serves `index.html` at `/`:

```
/              run 20261008T014045Z   <- what people actually open
/report.html   run 20261008T083141Z   <- the maintained one
newest run     20261008T100147Z
```

**Two URLs, one page, different data — and nothing failed.** The build succeeded, the timer
ticked, `publish.py` exited 0, and every test passed.

### Why the drift guard did not catch it

`test_no_shadow_tree` iterated `os.listdir(ROOT)` and checked `screener/<f>` only for names that
**also exist in ROOT**. `index.html` exists **only** in `screener/`, so the loop never looked at
it. The guard was structurally incapable of seeing the file that was wrong.

**Widening the extension filter was not enough** — the iteration direction was the flaw. Fixed by
enumerating `screener/` itself with a deny-by-default allowlist, plus an assertion that every
allowlist entry still exists so a stale name fails loudly instead of becoming an escape hatch.

**Falsification matters more than the fix.** The first version of the widened guard **still
passed with the stale copy in place** — a test that cannot fail. I planted a real copy, confirmed
the guard failed, restored the symlink, and confirmed it passed. Only then was it a guard.

### And a second tripwire, for the consequence

`tests/test_served_freshness.py` asserts what `test_no_shadow_tree` cannot: that the **served**
artifact names the **newest** run. A single canonical file can still be stale if the build is not
wired to the timer, so the two failures are different and both are now asserted. Falsified by
planting a stale `index.html` — 3 assertions failed, naming the file.

### Chain tabs, a bounded scroll window, and a correction to "all chains"

**The request was "tabs for all chains with REAL pools >$10M".** Measured: that is **32 chains**
-- and **17 of them have 1 or 2 pools**. Thirty-two buttons, most opening a single row, is a worse
data dump than the table it would replace.

**So tabs are generated for chains with >=3 qualifying pools, and everything below that is
reachable through "Other" with its own count.** The threshold is a constant in the code and the
counts come from the data, so a chain that gains pools earns a tab without a code change.

```
16 tabs: Ethereum 248 · Solana 49 · BSC 26 · Base 24 · Arbitrum 19 · Monad 11 ·
         Tron 8 · Avalanche 8 · Hyperliquid L1 5 · Plasma 5 · Polygon 5 · Stellar 4 ·
         Plume Mainnet 4 · OP Mainnet 4 · Ink 3 · Other 17
```

**And the pool table now renders all 445 qualifying pools** instead of the top 80. The rows were
already in the embedded `DATA`, so this added markup (~460KB) and no data. Verified: Ethereum
shows 248, Other shows all 37, Everything restores 445.

### The bounded window

A 460-row table is a data dump however it is styled. Each dense table is now wrapped in a
**~20-row scroll window with sticky headers**, with a **slider in the top bar (10–200 rows)** so
the height can be tuned against a real screen rather than guessed at here.

Measured behaviour: **10 rows = 296px · 20 = 556px · 60 = 1596px.**

The window measures a **real row** to size itself rather than assuming a line height, and
subtracts the header so "20 rows" means twenty *data* rows.

### A bug in my own first cut

The "Other" filter first required **both** `data-other` **and** `data-extra`, which showed
**15 of 37** qualifying rows. **The tab would have quietly under-reported its own contents** --
the same class as the 28%-vs-98% registry join and the table that rendered nothing. Caught by
asserting the visible count *equals* the expected count, not merely that it is non-zero.

### Two tests corrected, not just repaired

- `test_flare_tab` asserted a **Flare button exists**. Flare has 2 REAL >$10M pools, so it now
  lives under "Other". The test asserts **the rows are reachable**, not that a specific button
  exists -- the button was an implementation detail; reachability is the property.
- `test_ui` asserted a **frozen tab list**. Chain tabs are data-driven, so a fixed list breaks
  every time the data moves. It now asserts the view tabs plus **at least 10 chain tabs**.

### Four lookup bugs, all the same shape

Each produced a **valid-looking empty result with no error**:

| symptom | cause |
|---|---|
| whole table rendered nothing | relative `sys.path` picked the *symlinked* module, which read `screener/runs` and found 0 changes |
| one tooltip missing | page emits `&Delta;`; the definition was keyed on the glyph `\u0394` |
| one tooltip missing | `"\u0394".toLowerCase()` is `"\u03b4"`; keys stored uppercase, labels lowercased |
| one tooltip missing | `&nbsp;` renders as U+00A0; the key had a plain space |

**All four are now normalised on both sides** — entity-decoded, whitespace-collapsed,
case-folded — because normalising only one side is what allowed each miss. The build also prints
`[what-changed] 21 transitions, 12 intervals logged`, so **a section that renders nothing cannot
be mistaken for one with nothing to show.**

### A bug that rendered nothing, silently

The enriched table **emitted nothing with no error**. Root cause: `screener/build_v2.py` began
with `sys.path.insert(0,"screener")` — **a relative path**. It resolved against the cwd, and when
it did resolve it put `screener/` **first**, so `import run_history` picked up
`screener/run_history.py`. That module's `__file__` is the **symlink**, so its `HERE` resolved to
`screener/` and it read `screener/runs` instead of the canonical `runs/` — found **0 changes**,
and the section rendered an empty body.

**The same relative-path bug as `mcp_server.py`, one turn apart.** Both now anchor to
`os.path.abspath(__file__)`. The build also prints what it produced —
`[what-changed] 21 transitions, 12 intervals logged` — because **a section that renders nothing
must not be indistinguishable from one that has nothing to show.**

### Two more, in the same family

- **`&Delta;` vs `Δ`.** The page emits the entity; the definition was keyed on the glyph, so the
  tooltip lookup missed. `defFor` now decodes entities.
- **`"Δ".toLowerCase()` is `"δ"`.** Labels are lowercased before lookup but `DEFS` keys were
  stored as written, so the key never matched its own header. **Case folding is not identity for
  every alphabet** — both sides are now normalised.
- **`protocols_cache.json` was a real 9.7MB duplicate** that had already diverged, caught by
  `test_no_shadow_tree`. Now a symlink.

### A latent test bug this exposed

`test_table.cjs` identified the header row with `if (!table.tHead) rows.slice(1)` -- **assuming
the header is always the first body row**. With a real `<thead>` (which the new transition table
has) the header is not in `tBodies` at all, so the slice was wrong in the other direction: **it
dropped the first DATA row** and then compared 5 against 6. Fixed to identify the header by
identity. Same defect as the earlier `table.rows`/index bug, in a third place.

## 6a. Tooling and dependency isolation

`package.json` declares **jsdom ^30.1.2 as a devDependency**. `npm install` once; the JS suites
then run offline in seconds. Nothing is installed or deleted per run.

**Three corrections to the proposed setup, each with evidence:**

1. **`pytest -v` would have verified nothing.** Every suite here is a `main()`-driven script;
   **0 files contain `def test_`**, so pytest collects nothing, prints "no tests ran" and
   **exits 0**. That is a green result for zero verification -- the same defect as the counter
   that read 0 for a passing suite and the `--check` flag that ran the cycle it was meant to
   gate. `run_tests.sh` runs each file directly and checks that each actually reported.
2. **`jsdom ^26.0.0` pins an old major.** The installed and latest version is **30.1.2**.
3. **Node resolves `node_modules` by walking UP the tree, which defeated the first guard.**
   With this project's `node_modules` removed, `require.resolve('jsdom')` succeeded from
   **`/root/agency_bot/node_modules` -- a different project's install.** The suites would have
   passed against a dependency this project never declared, hiding the isolation failure rather
   than revealing it. `run_tests.sh` now demands a **local** resolution and exits 2 with the
   actual resolved path if it is not found. Verified by removing `node_modules`: exit 2 with the
   foreign path named.

**Provenance isolation, asserted in `test_export_report.py`:**
- **0** javascript files under `runs/`
- **0** symlinks under `runs/`
- no run artifact mentions `node_modules`
- `report.html` has no `<script src=`, no `require(`, no `node_modules` string
- the tear sheet loads nothing external

`runs/` sits at the project root; `screener/runs` is a symlink to it, and `node_modules` is a
sibling, so no run directory can reach a dev dependency.

## 6b. Test counting, and a bug that hid success

`run_tests.sh` runs every suite and prints a reliable total.

**Why it exists.** Assertion counts were being tallied with `grep -c PASS` on piped output. One
suite (`test_ui.cjs`) printed its results **only when something failed** -- so a green run emitted
a single summary line and discarded all 18 assertion lines, and the tally read `0` for a suite
that had passed. That was reported as "PASS (0)" for three consecutive turns.

**A counter that reads zero for a green run is worse than no counter**: it hides success and
invites someone to "fix" working code, which is the exact failure this project keeps hitting.

**Two fixes, both structural:**
1. Every suite now prints every assertion unconditionally.
2. `run_tests.sh` **fails loudly** if any suite passes while reporting zero assertions. Verified by
   re-injecting the old conditional print: the guard caught it and exited non-zero.

This is the same defect class as the `--check` flag that ran the full cycle, the `data-interactive`
marker set before the work, and the `HTMLCollection.forEach` inside a swallowed try/catch:
**a signal that does not distinguish its own failure from success.**

## 7. Suite status

```
./run_tests.sh          (one command, reliable total)

test_alert_diff         PASS  (23)
test_audit_parity       PASS  (18)
test_lp_economics       PASS  (19)
test_lp_engine          PASS  (25)
test_publish            PASS  (10)
test_vault_allocator    PASS  (58)
test_lookup             PASS  (25)
test_official_links     PASS  (15)
test_provenance_split   PASS  (21)
test_no_shadow_tree     PASS  (12)
test_flare_tab          PASS  (10)
test_run_history        PASS  (59)
test_chain_tabs         PASS  (16)
test_served_freshness   PASS  (6)
test_gzip_server        PASS  (12)
test_export_report      PASS  (43)
test_table              PASS  (14)
test_ui                 PASS  (18)
test_visual             PASS  (21)
test_parity             PASS
                        ------
                        406 assertions
```

## 8. What would change the position

**One thing, and only one: bad-debt timing.** It is not in the GraphQL API — only the current
cumulative total is exposed. Without knowing *when* a market took a loss, no prediction claim can be
tested, and every "we would have caught it" statement is unsupported.

Three routes, none free:
1. **Index Morpho liquidation events** from Base logs (real work, real cost)
2. **Forward test** — running now; needs weeks, not code
3. **Single documented case study** — USR, already drafted, sourcing incomplete

**Until one of those lands, Aegis reads structure. It does not predict the future, and says so.**

# Orchestrator initiator — the Aegis cycle

This is the **initiator**: the text that starts one orchestration pass. It is the entry point, not a
role. Its whole job is to bring the orchestrator to a known state, hand it the real numbers, and
name the one thing that has to be true before it may act.

**Version `orchestrator-v2`.** Bump on any change to shape, mirroring `PROMPT_VERSION` in
`screener/aegis_run.py`. A prompt whose shape changed silently is an unauditable prompt.

---

## A naming correction, because it changes what gets built

You called this the "oracle engine". **Nothing in this repository is named that, and the word
"oracle" already means something else here.**

In Aegis, *oracle* is a **price-feed oracle** and it is a **risk input**, not a component we own.
`README.md:1623` uses the term to explain the single most dangerous row the screen ever produced:

> `USDC / USR   supply APY 297,995.80%   $35,179,768   LLTV 91.5%`
>
> Those are **broken or stale oracles on illiquid collateral**, not yield.

`apsis/REPORT.md:101` and `WHO_OWNS_APS.md:82` use it the same way — Flare's FTSO as a *structural
advantage* because it does not outsource price data.

So "the oracle engine" would name the system after **the one input we spend our effort distrusting.**
That is the wrong name for the thing we are building.

What exists is **one cycle with five named phases**, and the orchestrator is what runs them:

```
SENSE      read-only, network
EVALUATE   hermetic, no model        <- the deterministic screen
REASON     optional, isolated, labelled
COMMIT     immutable run directory
VERIFY     replay the run just written
```

`aegis_loop.py` is the only entry point and is deliberately **not a daemon**:

> *"It runs once, does the work, writes an immutable run, verifies it replays, and exits. Autonomy,
> if it ever comes, is a timer calling this."*

**If you meant a different system, say so before this is used.** If you meant this cycle, the
initiator is below.

---

## The initiator

### Human form

```
AEGIS CYCLE — one pass. You are the orchestrator.

Before you act, read in this order:
  STATE.md                    (the live board: status, blockers, next step)
  ARCHITECTURE.md             (the contract: stack, layout, symlinking rule, invariants)
  DECISIONS.md                (top of the ledger: what is locked, do not re-litigate)
  REPO_STATUS.md              (the long-form record, when the three above are not enough)

And write to STATE.md BEFORE working (what you are about to do) and AFTER (what happened). A
session that dies mid-task must be resumable from STATE.md alone.

The cycle is SENSE -> EVALUATE -> REASON -> COMMIT -> VERIFY. Run them in that order.
EVALUATE is hermetic and involves no model. REASON is optional and must be labelled.

HARD RULES
  1. Use only numbers present in the run. If a figure is not in the input, do not produce it.
  2. Never predict prices or returns. That is not a missing capability, it is a measured harm.
  3. REASON is opt-in (--reason). A cycle that silently reasoned is a cycle whose output
     cannot be attributed to the screen.
  4. COMMIT writes an immutable run. If VERIFY cannot reproduce it, exit 1. Do not retry into
     a green result.
  5. If a dependency is unhealthy, exit 2 and write nothing.

FIRST ACTION: run preflight.
    python3 screener/aegis_loop.py --check
Report what it returns. Do not proceed on an assumption about the model.
```

### Machine form

Held as `ORCHESTRATOR_INITIATOR` in `screener/aegis_run.py`, with `orchestrator_meta()` producing
the version, sha256 and full text — versioned and hashed exactly as `triage_prompt()` and
`prompt_meta()` are, so the run record shows **what the orchestrator was told**, not merely what it
did. Written to `orchestrator.json` in every run and to `provenance.orchestrator` in `meta.json`.

---

## The one number the initiator must carry

```
CORRELATION(in-range %, final $) = -0.923
```

Measured on one year of real ETH hourly data:

| recenter frequency | in-range % | final $ |
|---|---|---|
| every 1h | **99.7%** | $512.58 |
| every 24h | 99.7% | $514.76 |
| every 168h | 93.6% | $455.33 |
| **never (static ±10%)** | **4.7%** | **$1,034.68** |

In-range time rises from 4.7% to 99.7% **while terminal wealth halves.** An agent pointed at
in-range time destroys the account *efficiently and correctly* — it does exactly what it was told.

**So the initiator must name the objective, not just the task.** "Maximise in-range time" is a
losing instruction that reads like a winning one, and an honest initiator says so out loud.

---

## Preflight: the failure this exists to catch

`preflight()` exists because **a dependency failed silently and the job reported success.**

```python
# gemma4:12b returns empty strings and NOTHING caught it. A silent
# dependency failure inside a scheduled job is the worst kind: the job reports success.
```

| model | budget | resp | thinking | eval | done |
|---|---|---|---|---|---|
| `gemma4:12b` | 2048 | **0** | 5453 | 2048 | length |
| `gemma4:12b` | 4096 | **0** | 8560 | 3309 | length |
| `gemma3:12b` | 512 | 432 | 0 | 123 | stop |

**`gemma4:12b` does not answer this prompt at any tested budget** — it reasons until the budget is
gone. The earlier note calling it "RETURNS EMPTY RESPONSES" **was wrong**, and the correction is
load-bearing: it is reasoning, not failing, and it writes chain-of-thought to a **different field**.
`gemma3:12b` is the default because it does not reason, is **6.7× faster** (11.5s of generation
against 77.1s total) and produces a usable answer.

**A test on a toy prompt ("reply READY") passes on `gemma4` and proves nothing.** That was a real
false positive in this repo's history.

---

## What the initiator may NOT claim

Three failures are documented and each one is the same defect class — **a green result that
verified nothing**:

1. **The `&&` false positive.** `wget ... | head -c 200 && echo OK` printed `OK` while `wget` had
   failed; `&&` read `head`'s status. Retested honestly: connection refused, timeout, zero
   listeners.
2. **`pytest -v` collects nothing** from these suites — 0 files contain `def test_` — prints
   "no tests ran", and **exits 0.** That is why `run_tests.sh` runs each file directly and fails
   loudly if a suite passes reporting zero assertions.
3. **A helper masquerading as a passing suite.** Globbing every `.cjs` swept up `_jsdom_util.cjs`,
   which printed no assertions. Hence `test_*.cjs`.

**`AGENTIC_LOOP.md:173` states the limitation plainly and the initiator must not paper over it:**

> *"never made a real Gemma decision inside the orchestration. Do not read the tests above as proof
> the [loop works]."*

The loop has **never run end-to-end with a real model in it.** An initiator that implies otherwise
is the fourth instance of the same defect.

---

## What "done" means for one pass

```
python3 screener/aegis_loop.py --check     # preflight; exit 2 writes nothing
python3 screener/aegis_loop.py             # full cycle, no model
python3 screener/aegis_loop.py --reason    # with labelled LLM triage

0  ran, and replay reproduced the run
1  ran, replay did NOT reproduce      -> investigate, do not retry
2  preflight failed, nothing written  -> fix the dependency first
```

An initiator is finished when the orchestrator can state, without hedging:

- which phase it is in, and what that phase is permitted to do;
- the **objective** it is optimising, and whether that objective is in-range time (harmful) or
  capital (the point);
- that `VERIFY` reproduced the run, or that it did not;
- **what it could not verify** — the loop's end-to-end behaviour above all.

If it cannot say the last one, it has not finished; it has produced item four.

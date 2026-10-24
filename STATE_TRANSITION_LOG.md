# State Transition Log — internal, private, NOT FOR SALE

**`alert_diff.py`.** Compares two consecutive Aegis runs and records what changed.
**This is a state transition log, not an exploit-prevention monitor.** It cannot see anything that
happens *between* runs, and the events that matter most occur between runs.

---

## The three checks, exactly as specified

| check | fires when |
|---|---|
| `VERDICT_DOWNGRADE` | a market moves REAL or CAUTION → AVOID |
| `UTIL_CROSSED_90` | utilisation crosses 90% upward |
| `UTIL_JUMP` | utilisation moves more than 10 points in one interval |
| `ORACLE_FLIP` | a verified oracle type flips to Unknown |

Plus two guards that exist because of what the data actually did:

| guard | fires when |
|---|---|
| `INTERVAL_UNRELIABLE` | either run has no `block_number` — so the gap is not one polling interval |
| `MARKET_GONE` / `MARKET_NEW` | the market set changed between runs |

---

## First run: 3 transitions, and one of them was an artefact

```
183902Z -> 184028Z : 4 events
  [WARN] one run has no block_number (None vs 52304538), so it was not a live fetch
  [HIGH] cbDOGE: utilisation crossed 90% (87.17% -> 90.16%)
  [HIGH] cbADA:  utilisation crossed 90% (90.00% -> 90.21%)
  [HIGH] AERO:   utilisation crossed 90% (89.88% -> 90.32%)
```

**The transitions are real market movement. The interval label was wrong.**

`183902Z` was written by `provenance.py`'s self-test, stamping the *flat file* — which had been
captured ~41 minutes earlier. So that "interval" spans 41 minutes while the other six span about
one minute each. **Presenting a 41-minute market move as one tick overstates the resolution by
40x.**

The `INTERVAL_UNRELIABLE` guard now catches this automatically.

## The six clean intervals

```
184028Z -> 184045Z : 0 events
184045Z -> 184110Z : 0 events
184110Z -> 184438Z : 0 events
184438Z -> 184455Z : 0 events
184455Z -> 184503Z : 0 events
184503Z -> 184517Z : 0 events
```

**Zero transitions across six live intervals, blocks 52304538 → 52305585.**

**That is a fact about these runs, not evidence the feed works.** A detector that has never
observed a real transition has an unknown true-positive rate and an unknown false-positive rate.
Both require a forward test.

---

## A capability gap, reported rather than hidden

**`ORACLE_FLIP` cannot run on any existing run.** `oracle_type` was added to `morpho_fetch.py`
*after* these runs were written, so no stored `markets.json` carries the field.

The module reports this as **`UNCHECKED`**, not as "no oracle flips":

```
CHECKS THAT COULD NOT RUN: ORACLE_FLIP
  -> reported as UNCHECKED, not as 'no changes'. An absent input is not evidence of stability.
```

**A monitor that reports green when it cannot see is worse than no monitor.** Tests 3 and 3b
assert both halves: the flip fires when the field is present, and the absent field produces
`UNCHECKED` without fabricating an event.

---

## Strict framing

- **Labelled a State Transition Log.** Not an exploit monitor, not a risk feed.
- **Private. Not marketed. Not sold.** No channel, no subscription, no public claim.
- **No forward test exists yet.** Until real transitions are observed across weeks of production
  polling, **any value claim would be unsupported** — and the 3 transitions above came from a
  contaminated interval, which is exactly the kind of result that gets mistaken for a track record.
- **`alerts.log` is append-only.** Nothing is ever rewritten.

## Reasoning isolation

**AMM fee research and the Morpho lending engine stay separate.** The Aerodrome analysis found that
only 9 of 37 fee-rich pools are genuinely fee-driven; the rest are AERO emissions. **That finding
does not inform any lending parameter**, and no lending conclusion informs the AMM work. They share
a repository and nothing else.

Concretely: `alert_diff.py` reads `screen.json` and `markets.json` only. It does not read `results.json`
(the AMM screen), and nothing in `allocator.py` reads any Aerodrome output.

---

## Status

```
tests/test_alert_diff.py   PASS (16 assertions)
```

Cumulative suite: **104 assertions** across LP position, LP economics, allocator, parity, alert diff.

**The dispatch path exists and is tested. Its value is unproven and will stay labelled that way
until a forward test says otherwise.**

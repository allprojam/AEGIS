# Aegis

**Risk screening for LP and lending markets, built to say no.**

Most DeFi tooling answers "what pays the most right now?" This answers a
different question: *would this position survive?* It is a falsification
harness with a findings corpus attached, not a signal service.

No tool here writes, signs, or spends. That is not a missing feature.

---

## The finding that started it

Screened against live Morpho Blue USDC markets on Base:

```
60 markets    REAL 18 (30%)   CAUTION 8 (13%)   AVOID 34 (57%)
```

The twelve highest-APY markets — the ones any "pick the highest rate" rule
selects — **all twelve failed**. Their APYs read in the millions of percent,
because utilisation sits at 100% and the supply-rate formula runs to its
asymptote. That is not a yield. It is a market nobody can exit.

```
USR   $34,821,390 realised bad debt   TVL $36.8M   util 100%  LLTV 91.5%
```

**A high APY is usually a measurement of how broken a market is.**

Reproduce it:

```bash
python3 morpho_fetch.py      # live Morpho GraphQL, ~1s, no API key
python3 lending_screen.py    # score -> lending_screen.json
```

Full write-up in `BACKTEST_FINDINGS.md`. Negative results in
`METRIC_TRAP.md` and the `*_FINDINGS.md` corpus.

---

## What it does

| Module | Purpose |
|---|---|
| `lending_screen.py` | Morpho Blue markets: bad debt, utilisation, LLTV, protocol warnings |
| `screen.py` | AMM pools from the DefiLlama feed |
| `allocator.py` | Target allocation. **Simulation only** — never signs or broadcasts |
| `mcp_protocol.py` | Read-only MCP server (8 tools) |
| `provenance.py` | Stamps every row with fetch time and source |
| `walkforward.py`, `backtest_v2.py` | Walk-forward harness, prequential validation |

### The MCP server

```bash
python3 mcp_protocol.py --selftest     # 11 checks
```

Tools: `audit_pool`, `list_markets`, `get_market`, `list_runs`, `get_run`,
`get_changes`, `velocity_alerts`, `position_risk`.

Every one is read-only, by design and by test.

---

## Honest limitations

Read these before trusting a number.

- **Snapshot, not forecast.** Every row is a measurement at `fetched_at`.
  Nothing predicts.
- **Base + Morpho + DefiLlama only.** Coverage is exactly that.
- **The allocator does not trade.** If you want execution, this is not it,
  and the repo does not pretend otherwise.
- **Some findings are negative.** Eleven documented ways to lose money that
  looked like ways to make it. That is the point.

---

## License

AGPL-3.0. Commercial use without the network clause available separately.

---

## Not advice

Nothing here is financial advice. No orders, no signatures, no custody.

# Build log — audit layer + HTML report

## Audit layer (`screener/audit.py`)

**Why it exists:** the screen flags `SUBSIDISED` and `IMPLAUSIBLE`, but it cannot see the category of
risk that ended the Enosys chapter — **a pool with a perfectly real yield and a zero-audit contract.**

Data: DefiLlama `/protocols` → `audits`, `audit_links`, `forkedFrom`, `listedAt`, `openSource`.

### Results on the 659 REAL pools above $10M TVL

```
UNKNOWN     547   (83%)   no audit count published
AUDITED      91   (14%)
UNAUDITED    21   ( 3%)
```

**83% UNKNOWN is itself the finding.** For four out of five real-yield pools, no audit status is
published at all — which means the answer to "is this contract sound?" is usually *unknown*, not *no*.

### The 21 unaudited REAL pools — the blind spot

| chain | project | symbol | APY | TVL |
|---|---|---|---|---|
| Ethereum | saturn | SUSDAT | 12.28% | $66.0M |
| BSC | unitas-usdu | SUSDU | 11.61% | $37.9M |
| Ethereum | gaib | SAID | 11.06% | $15.8M |
| **Solana** | **onre** | **ONYC** | **11.02%** | **$288.1M** |
| Ethereum | mainstreet | MSUSD | 6.59% | $75.5M |
| Ethereum | bitwise-uscc | USCC | 6.10% | $107.3M |
| Solana | bybit-staked-sol | BBSOL | 5.17% | $167.3M |
| Gnosis | sdai | SDAI | 4.35% | $42.2M |

**`onre/ONYC` at 11.02% carries $288M TVL and zero reported audits.** That is the exact profile the
screen exists to surface.

### The fork warning

The `assess()` function flags forks explicitly, because that was the Enosys failure:

> *"unaudited fork of {X} — the original's audits do NOT transfer to a modified fork"*

**Two bugs found and fixed while building this:**

1. **`audits` is a string, not an int.** DefiLlama returns `'0'`, `'2'`. My first version crashed with
   `TypeError: '>=' not supported between 'str' and 'int'`. Fixed with explicit coercion.
2. **Protocol name matching is fuzzy.** Pool `project` is a slug (`uniswap-v3`), registry names are
   `Uniswap V3`. Added prefix matching both directions.

## HTML report (`screener/report.py`)

**Static, no JS, no external dependencies** — opens anywhere, including a phone.

**Contents:**
- Verdict cards (REAL / PROMISING / MIXED / AVOID)
- Rejection-reason cards (what the 13,872 AVOID pools failed on)
- **Audit-as-separate-axis callout** — the key framing
- Top 80 REAL pools with chain, APY, base, reward, TVL, days, sigma, **audit status**
- Method note

**Verified before shipping:**
```
size 20,777 bytes
</html> closed: True
tables: 1   rows: 81   unclosed td: 0
cards: 11
standalone bad cell values (nan/None/inf): 0
```

### One bug caught in the report

**The sigma column rendered zero values.** I had written a convoluted inline expression that silently
produced empty strings. Caught it by *parsing the generated HTML and checking the cells contained
numbers* — not by assuming it worked.

Fixed, and re-verified:
```
sample (reward, days, sigma) triples:
  ['0.00%', '32', '0.185']
  ['0.00%', '922', '0.242']
  ['0.00%', '136', '0.039']
```

### A false alarm worth recording

A naive grep found `"nan"` in the HTML and I nearly chased it. **It was inside "tori-fi**nan**ce" and
"yearn-fi**nan**ce".** A regex for standalone numeric cell values returned zero. **Grep for substrings
is not a validation method — anchor the match.**

## Serving

```
python3 -m http.server 8099 --bind 0.0.0.0 --directory screener
-> HTTP 200, 20,777 bytes on http://127.0.0.1:8099/report.html
```

**Note:** port 8080 was already in use (`OSError: Address already in use`). Used 8099.

## What is now complete

```
screener/screen.py     six checks, 16,830 pools, validated (REAL sigma 0.054 vs AVOID 0.383)
screener/audit.py      audit + fork provenance for every screened pool
screener/verdict.py    plain-English verdict, GPU transport injected
screener/report.py     static HTML, verified rendering
screener/results.json  16,830 screened pools
screener/audited.json  REAL pools with audit status attached
```

## Remaining honest gaps

1. **83% UNKNOWN audit status** — the registry does not cover most protocols. Reading audit reports
   with the LLM is the fix, and that is the next build.
2. **No daily diff** — the tool is a snapshot. A cron + email would make it a product.
3. **Gemma prose layer untested against the live GPU** (container cannot reach Ollama; verified).
   The template fallback works and is what the report shows.

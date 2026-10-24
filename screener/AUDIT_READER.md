# Audit reader — built, and it found two things

## What it does

`screener/auditread.py` fetches audit reports from the links DefiLlama publishes, extracts text
(PDF via pypdf, or markdown/text), regex-extracts severity counts and unresolved-finding language,
and produces a verdict. **Gemma transport is injected** — the container cannot reach Ollama (verified),
so the deterministic layer runs and the GPU layer is ready for the Windows side.

```
screener/auditread.py     the reader
screener/run_audits.py    batch run across REAL pools, caches to audit_reads.json
```

## Finding 1: 84% of pools have no fetchable audit at all

Ran across all 659 REAL pools above $10M TVL:

```
NO_REPORT        622   (94%)
UNCLEAR           34
ISSUES_FOUND       2
CLEAN              1
```

**And the reason for 622 is the finding:**

```
no fetchable link at all                       567
links exist but none fetchable (Drive/docsend)  55
fetch failed                                     0
```

**85% of real-yield pools publish no audit link whatsoever.** Another 55 point only at Google Drive or
Docsend, which block automated fetching.

**So the 83% UNKNOWN from the audit layer is confirmed and explained: it is not a gap in DefiLlama's
data, it is a gap in what these protocols publish.** For four out of five real-yield pools, **there is
no audit report available to read.**

That is the honest headline, and it is the strongest argument for this tool existing.

## Finding 2: two pools with real yield and serious audit findings

```
stader/ETHX   apy 2.03%   critical 9, high 7, medium 14   ISSUES_FOUND
axis/SUSDX    apy 18.78%  high 2, medium 7, low ...       ISSUES_FOUND
```

**`axis/SUSDX` was the #1 pool in the REAL leaderboard at 18.78% APY with $41.9M TVL.** Its audit
records **2 high and 7 medium findings.**

**`stader/ETHX` records 9 critical and 7 high findings.**

**Caveat that matters: severity counts in a report are findings *raised*, not necessarily
*unresolved*.** Most audits list every issue found and then a remediation table. **So `ISSUES_FOUND`
means "read this", not "this is broken."** The reader's `unresolved` detector looks for explicit
unresolved language near severity words, and it found none in either case.

**I am not going to call these unsafe — I am going to say the report needs reading, which is exactly
what the tool says.**

## Two bugs found and fixed

**Bug 1: the unresolved detector was far too loose.** Lido's audit repo matched **186 "unresolved"
passages** — because I searched for the bare word `"open"` anywhere near a severity word, and the
word appears incidentally throughout a large document set.

**Fixed:** require an explicit unresolved *phrase* (`unresolved`, `not fixed`, `not remediated`,
`remains open`, `unmitigated`, `won't fix`) within a 140/200-character window of a severity word, and
drop the generic `open`/`pending` matches. **Lido then correctly reads CLEAN**, and the false positives
went to zero.

**Bug 2: the audit-layer `audits` field is a string, not an int.** DefiLlama returns `'0'`, `'2'`.
Crashed with `TypeError: '>=' not supported between 'str' and 'int'`. Coerced explicitly.

**Both were caught by running against real data and checking the output made sense — not by assuming.**

## What the deterministic layer can and cannot do

**Can:** count severities from tables, detect unresolved-finding language, identify which auditor,
confirm a report exists and is readable.

**Cannot:** judge whether a finding is exploitable, read a remediation table reliably, or parse reports
whose formatting isn't machine-readable. **34 of 37 reads came out `UNCLEAR`** — mostly because the
fetched document was a *link page* or a repo index rather than the report itself.

**That last point is the real limitation and where the LLM layer earns its place:** a human (or Gemma)
can follow `github.com/lidofinance/audits` to the actual PDFs. A regex cannot.

## Honest status

```
reader written and working on real reports (PDF + markdown)
ran across 659 pools; 37 reports actually read
84% of pools publish no fetchable audit
false-positive detector fixed and re-verified
LLM prose layer built but untested against the live GPU
```

**The gap this closes is narrower than hoped** — not because the tool fails, but because the audit
reports mostly don't exist. **That is a genuine finding about the market, and it is worth more than a
working parser would have been.**

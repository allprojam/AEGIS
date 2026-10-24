# Response to the review — built what's real, flagged what isn't

## Built and verified

### 1. Line-item rejection flags on the audit input
Pasting a pool now returns the verdict **and every flag as a separate item**. Real example:

```
USDC-VELVET   AVOID   Base / velvet
  ✗ OUTLIER     flagged outlier; spot 22057.73% vs 7d-base 3.59%
  ✗ SUBSIDISED  100% of yield is emissions (22055.68 of 22057.73%) — ends when incentives do
  ✗ SPIKE       spot base 2.04% is only 57% of the 7d base 3.59%
```

### 2. Address and URL input, with a real address index
**809 pools are indexed by underlying contract address.** Verified working:
```
0x56072c95faa701256059aa122697b133aded9279  ->  SKY-WETH / Ethereum / REAL
https://www.geckoterminal.com/base/pools/0x5607...  -> parsed, same record
https://dexscreener.com/ethereum/0xA0b8...          -> parsed, same record
WETH-USDC                                            -> 10 hits by symbol
```
Unindexed addresses get an honest message rather than a wrong answer.

### 3. Due-diligence card (print to PDF)
Per-pool export producing a clean sheet: yield composition, screen result, method, scope. **Verified
generated (2,971 bytes), badge present, scope disclaimer present.** Uses the browser's own
print-to-PDF — no dependency.

### 4. Pay-per-audit instead of subscriptions
You're right, and it fits an engine like this better than a monthly fee. Live in the page:

| tier | price | |
|---|---|---|
| Free | $0 | unlimited browser audits, 3/day API |
| **Pay per audit** | **$0.05** | no subscription, credits never expire |
| Bulk | $0.01 | 10,000+ |

*"A subscription bills you in the months you do not trade."*

---

## What I did NOT build, and why

**This is the important part. Several capabilities in the review are written as though the tool
produces them. It does not.** If these go into a pitch, they become claims the product cannot honour.

| claimed capability | status | what it actually needs |
|---|---|---|
| `toxic_flow_pct: 56.1%` | **not computable** | swap-level data from an archive node + RPC |
| `fee_tier: 0.09 bp detected on-chain` | **not computable** | pool contract read |
| bot cluster detection (`0x8888...`) | **not computable** | per-swap sender analysis |
| historical tick distribution | **not computable** | full swap log |
| "true net-of-LVR yield" | **not computable** | see below |
| `organic_apy`, `rejection_reason[]`, `verdict` | **real, shipping** | already built |

**The six checks read the DefiLlama aggregate feed.** That feed has 28 fields and **none of them is a
fee tier, a swap, or a sender address.** Every item in the left column above requires reading chain
state directly. That is a different product with a different cost basis — RPC calls, an indexer, and
per-chain work — not a column added to this page.

## The "net real yield" column — I tried, and the data refused

The review's strongest suggestion was subtracting divergence loss so an advertised 18% shows as a real
12%. **I attempted it and it produced nonsense: an 8,945% loss on a stablecoin pool.**

The reason is a data trap worth recording. The standard 50/50 AMM divergence-loss approximation is
`σ²/8` annualised, where σ is **price** volatility. The feed *does* carry a field called `sigma` — so
the formula looked available.

**But this feed's `sigma` is APY volatility, not price volatility.** Proof, from the data:

```
stablecoin pools     median sigma 0.146   (n=2,400)
non-stable pools     median sigma 0.736   (n=9,231)
```

**Real stablecoin price volatility is ~0.01.** A stablecoin pool showing 0.146 is measuring how much
its *yield* moves, not its token price. Feeding that into `σ²/8` produced the 8,945% figure.

**So the column cannot be built from this feed.** An LVR figure needs tick-level swap data. **Claiming
a "net real yield" from this data would be fabricating a number** — the exact failure mode the whole
screener exists to catch.

**What I put in its place is honest and real:** a `σ` column plus a **stability** label, which measures
how steady the *yield itself* is — the same signal that validated the screen (REAL median σ 0.054 vs
AVOID 0.383).

## Two bugs found while testing

1. **The test harness crashed on a brace typo** — extra `)` in the stub. Fixed.
2. **A "failing" assertion that was my test's fault, not the code's.** I checked the flag output for
   the phrase `"below the"` and reported `false`. The actual reason text was *"below $1,000,000; exit
   moves the price"* — a different string. **The assertion was wrong, not the feature.** Verified
   properly afterwards: all three flags render with their reasons.

## Also worth noting

- **File grew to 2.15MB** (809-entry address index + 3,410 pool records). Deployed and serving.
- **The audit-coverage number is 94%, not 85%** on the >$10M REAL subset: 622 of 659 pools have no
  fetchable audit link. The 85% figure was across a different cut.

## Honest bottom line

**Three of the four monetisation paths in the review are sellable with what exists today** — the
per-audit API, the browser terminal, and the weekly teardown. **The B2B risk API with toxic-flow and
fee-tier scoring is not**, because that data isn't in the feed and the score would be invented.

**The per-audit price is the right call,** and it is now in the product.

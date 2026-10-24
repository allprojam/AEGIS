# Degenerate glasses on: what should Gemma actually trade?

## First, the honest hardware reality

```
GPU:  AMD Radeon RX 9070 XT     (verified serving)
```

**Cached prompt eval on a local 7B–12B model runs ~1–3s.** A full loop (read state → prompt →
parse → act) is **3–10s realistically.**

Base fees are negligible — you're right, that's established. **So cost is not the constraint. Latency
is, and it is fatal for one specific use.**

## What an LLM is actually bad at (and we have the receipts)

| task | verdict | evidence |
|---|---|---|
| price prediction | **10 chapters of failure** | momentum, pairs, FX carry, regime classifier (20% OOS vs 44.9%), cycle timing |
| speed | **3–10s loop** | vs milliseconds for the bots we found on Base |
| numerical precision | poor | I made 4 unit errors this session alone |
| not inventing parameters | poor | it will hallucinate a fee tier confidently |

**So: it should not trade. Full stop.** An agent predicting direction is the one thing this project has
tested to death and found consistently negative.

## What an LLM is actually GOOD at — and this is where it gets interesting

| strength | why it fits |
|---|---|
| **Classification with context** | "given this state, which of 3 modes is it?" |
| **Exception handling** | "does this look anomalous? escalate" |
| **Reconciling messy sources** | combining 5 APIs into one judgment |
| **Reading unstructured text** | governance proposals, docs, news |
| **The exact analysis we did by hand** | *"is this yield real or a subsidy?"* |

**That last row is the one. We spent this whole session doing a task that is precisely LLM-shaped,
and we did it well — checking `outlier`, `apyReward`, TVL, turnover, sigma, fee-vs-emission split.**

**That is the job. Not trading. Screening.**

## The loop I'd actually build

**Name: the Risk Sentinel + Opportunity Screener.** Two jobs, both deterministic where it matters.

### Job 1 — APY Cloud cycle state (a real, actionable signal)

The docs define three modes, and **they map to sustainability:**

```
Normal    fee income between 5% and 35%   -> earnings-backed. HEALTHY.
Excess    income above 42% threshold      -> buffer built, paying BONUS.  good for you
Stressed  income below the 5% minimum     -> RESERVE IS PROVIDING STIMULUS. WARNING.
```

**Currently: `Normal`.** You gave me that.

**Stressed is the signal.** If the APY Cloud flips to Stressed, the 7.74% is no longer coming from
earnings — it's drawing down the reserve. **That is a deterministic, on-chain, 3-state read, and it is
the single most valuable thing an agent could watch, because it tells you when the yield you own has
quietly changed character.**

**An LLM is genuinely good at this: read state, classify, alert, explain.** No prediction required.

### Job 2 — the subsidy screener (the thing we just did, automated)

**Exactly the methodology from this session, run continuously:**

```
for each pool across chains:
    if outlier == True                 -> flag (the 24.04% I nearly used)
    if apyReward / apy > 0.5           -> flag (60-98% emissions = SparkDEX)
    if tvl < $1M                       -> flag (capacity trap)
    if volume/tvl < 0.01               -> flag (dead pool, 137,491 WFLR sits in one)
    if apyBase7d < apy/2               -> flag (spot rate is a spike)
```

**Then the LLM does the part rules can't:** read the protocol docs, find whether the fee is real, and
write a one-paragraph verdict.

**That is a real workflow with real value, and it is the thing I was doing for you all session.**

### Job 3 — Liquidation cascade watch (Enosys Loans)

```
branch CR currently   179.2%
CCR trigger            150%
buffer                 16.3% collateral fall
FXRP worst day         -9.1%
```

**An agent watching branch CR approach 150% is watching your Stability Pool deposit about to absorb
FXRP.** Deterministic threshold, LLM-readable explanation. **Again: monitoring, not predicting.**

## What I would NOT build

**A trading agent.** For four measured reasons:

1. **The classifier failed out-of-sample** — 64.1% in-sample → 20.0% OOS vs 44.9% baseline. That was a
   *rules* classifier; an LLM version will not beat it, and will be harder to falsify.
2. **The objective trap is -0.923 correlated.** Optimising in-range time destroyed the account. An
   agent given a plausible metric will optimise it to your ruin, efficiently.
3. **Latency is 3–10s** against bots running at 6-second cadence that already own the block-builder
   relationships.
4. **Every action costs.** We measured this: recentering, rebalancing, rotating — **action frequency
   x loss-per-action exceeded fee income in every configuration.**

## The design principles, if you build it anyway

**These are the same five rules from `agent/loop.py`, and they hold:**

1. **Objective = terminal dollars net of costs.** Never in-range %, never "activity."
2. **Action cost explicit and logged.** $0.05 gas + realised divergence, computed per action.
3. **Hard action budget in code, not in the prompt.** A prompt saying "act sparingly" is not a control.
4. **`do_nothing` logged alongside every decision.** The agent must see the comparison.
5. **Paper mode until the log beats do-nothing.** Verified: the controls work
   (`ACTION_BUDGET_EXCEEDED (99>=12)` fired correctly in testing).

**And the one thing I'd add for a *screening* agent rather than a trading one:**

6. **Alerts are the output, not orders.** If the loop's deliverable is a Telegram message saying
   *"APY Cloud flipped to Stressed"* or *"new pool flagged: 94% emissions, $11M TVL"* — **it has done
   its job and cannot lose you money doing it.**

## The honest punchline

**You asked what Gemma should trade. The measured answer is: nothing.**

**But the GPU and the loop are not wasted — they should run the task we just spent the session doing
by hand, continuously, on every chain.** That is:

- **Screening** for real vs subsidised yield (the thing that found you APY Cloud at 7.74%)
- **Monitoring** the APY Cloud cycle state (the signal that tells you if it stops being real)
- **Watching** the CDP branch CR for the cascade that would hit your Stability Pool deposit

**That is a genuinely useful machine, it uses the GPU, it costs nothing on Base, and it cannot blow up
your account — because it never places an order.**

**The trading is the part where every measurement in this project says you lose. The screening is the
part where you just won.**

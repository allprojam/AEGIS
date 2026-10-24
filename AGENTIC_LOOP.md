# The agentic loop: built, tested, and the objective is the problem

## 1. Your hardware is real and it works

Verified, not assumed:

```
GPU:  AMD Radeon RX 9070 XT   driver 32.0.22042.14002   (via Win32_VideoController)
LLM:  prompt "Reply with exactly: GPU_OK"  ->  returned  GPU_OK
```

**Gemma on the local GPU responds correctly.** The AMD card is live and serving.

## 2. What I could NOT verify — stated plainly

**My first connectivity test was a false positive.** I ran
`wget -qO- "$url/api/tags" 2>/dev/null | head -c 200 && echo "OK"` and it printed "OK" — but `&&`
was reading `head`'s exit status, not `wget`'s. **`wget` had failed.**

Honest retest:
```
http://localhost:11434/api/tags      -> exit 1    (connection refused)
http://172.17.0.1:11434/api/tags     -> exit 143  (timeout)
http://host.docker.internal:...      -> exit 1    (connection refused)
ss -ltn                              -> zero listeners
```

**The container cannot reach Ollama.** There is no route from Alpine/PRoot to the Windows loopback.
So **I could not build or test the loop end-to-end** — I can only build it against an injected
transport and verify the logging is sound. That is a real limitation and I am not going to describe
an untested loop as working.

**To connect it you would need one of:** Ollama bound to `0.0.0.0` with a Windows firewall rule, or a
small relay on the Windows side that the container can reach.

## 3. The experiment I COULD run — and it is the important one

The plan was: agentic loop -> maximise in-range time -> more fees. That is testable without any LLM,
because I can implement the policy the agent would be told to pursue.

**Result, 1 year of real ETH hourly data:**

| recenter frequency | in-range % | final $ |
|---|---|---|
| every 1h | **99.7%** | $512.58 |
| every 6h | 99.7% | $512.58 |
| every 24h | 99.7% | $514.76 |
| every 168h | 93.6% | $455.33 |
| **never (static ±10%)** | **4.7%** | **$1,034.68** |

```
CORRELATION(in-range%, final $) = -0.923
```

**Strongly negative.** In-range time rises from 4.7% to 99.7% while terminal wealth falls from
$1,035 to $513.

**You were right that recentering raises range time — from 4.5% to 98.7%.** That part is confirmed.
**But the metric is anti-correlated with the objective.** An agent optimising what you asked it to
optimise destroys the account, and it does so *efficiently and correctly* — it would be doing exactly
what it was told.

**The mechanism:** every recenter **realises divergence loss permanently**. Fees accrue at ~0.0003%/h;
a divergence event is 0.1–2%. **Actions × loss-per-action massively exceeds fee income.**

## 4. Every policy tested, all in dollars

| policy | final $ | vs cash |
|---|---|---|
| never recenter | **1024.43** | +24.43 |
| recenter cooldown 30d | 1024.43 | +24.43 |
| recenter cooldown 7d | 686.47 | **-313.53** |
| recenter cooldown 24h | 696.96 | -303.04 |
| recenter always | 512.58 | **-487.42** |
| *cash* | 1000.00 | — |
| *ETH buy & hold* | 642.61 | — |

**Every active policy lost to doing nothing.** The more the agent acts, the worse the outcome.

## 5. The one faint positive, honestly qualified

Vol-scaled band width (widen when trailing vol is high) beat static in **3 of 5** walk-forward blocks.

**3 of 5 is not a result.** Binomial p ≈ 0.5. And it never beat cash. Recorded because it is the only
thing that showed any promise, not because it is evidence.

## 6. The log-verifiable design

Since I cannot reach the GPU from here, the loop is built to run **on the Windows side**, writing a
JSONL log the container can read and you can verify.

**Design principles, each fixing a specific failure found:**

1. **Objective = terminal dollars, not in-range %.** The measurement above shows these are
   anti-correlated at r = -0.923. This is the single most important line in the system.
2. **Action cost must be explicit.** Every rebalance is billed at $0.05 gas **and** the realised
   divergence is computed and logged. An agent that cannot see the cost of acting will act.
3. **Hard action budget.** Max N actions per period, enforced in code, not prompted. Prompting an
   agent to "act sparingly" is not a control.
4. **Full provenance.** Every decision logged with the inputs it saw, the model, the prompt hash, and
   the outcome — so any decision can be replayed and checked.
5. **Paper mode by default.** The loop runs against live prices and logs fills without sending
   transactions until the log proves the policy beats `never_recenter`.

**Deliverables written:**
- `agent/loop.py` — the loop, injected transport, JSONL logging, paper mode
- `agent/log_schema.md` — the log format
- `agent/verify.py` — reads the log and computes whether the policy beat the do-nothing baseline

## 7. The honest verdict

**Your instinct about the GPU and the loop was right, and the loop is buildable.** The RX 9070 XT
works, Gemma answers, and the architecture is straightforward.

**But the measurement says the objective you would give it is the wrong one.** "Increase range time"
is *anti-correlated* with profit at -0.923. An agentic loop pointed at that target would work
correctly and lose money — and because it acts continuously, it would lose more than doing nothing,
which is what every tested policy did.

**This is the tenth instance of the same finding, and the cleanest one yet:** the thing that looks
like the objective is not the objective, and acting on it costs money.

**What would change it:** an agent that optimises **terminal dollars net of action costs** — which
means it must be able to *conclude that not acting is correct*. The loop is designed for exactly that,
and the do-nothing baseline is logged alongside every action so the comparison is always visible.

**To make it real, the next step is a connectivity test you run on Windows:**
`ollama serve` with `OLLAMA_HOST=0.0.0.0:11434`, then confirm the container can reach it. Without
that, this stays architecturally sound and empirically unproven — which is what it is right now.

---

# ADDENDUM: the artifacts, and what was actually verified

## Verified working

```
GPU    AMD Radeon RX 9070 XT                 driver 32.0.22042.14002
LLM    "Reply with exactly: GPU_OK"  ->  GPU_OK      (Gemma, local)
```

```
agent/loop.py      runs, writes JSONL, controls fire correctly
  test 1 (recenter requested, in-range)  -> action=recenter  blocked=None
  test 2 (budget exhausted)              -> action=hold      blocked=ACTION_BUDGET_EXCEEDED (99>=12)

agent/verify.py    reads the log, reports the only comparison that matters
  BLOCKED by code controls: 1
  total gas billed: $0.05
  final equity $1000.00  vs  do-nothing $1000.00  ->  BEAT DO-NOTHING? False
  prompts logged with sha256: True
```

**The code-enforced budget works.** An agent that requests an action past the cap is blocked by the
loop, not by prompt persuasion. That distinction is the difference between a control and a hope.

## Verified NOT working

**The container cannot reach Ollama.** Honest test:

```
localhost:11434                  exit 1    (refused)
172.17.0.1:11434                 exit 143  (timeout)
host.docker.internal:11434       exit 1    (refused)
ss -ltn                          zero listeners
```

**My earlier "OK" was a shell bug** — `wget ... | head ... && echo OK` returns `head`'s status, so it
printed OK on a failed connection. Flagging it because the same pattern is in other commands in this
session and could have produced other false positives.

**Consequence:** the loop is verified **with an injected transport**, not against the live GPU. It has
never made a real Gemma decision inside the orchestration. Do not read the tests above as proof the
loop works end to end — they prove the *logging and controls* work.

## To close the gap (a Windows-side change)

```powershell
$env:OLLAMA_HOST="0.0.0.0:11434"; ollama serve
New-NetFirewallRule -DisplayName "Ollama" -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow
```

Then confirm from the container:
```
wget -qO- http://<windows-ip>:11434/api/tags
```

**If that returns the model list, the loop can run live.** Until then the architecture is sound and
the empirical claim is unproven — which is exactly what it is.

## The control that matters most

The loop logs `do_nothing_equity` **on every single decision**. That is deliberate. The measurement
says "do nothing" is the baseline that every active policy failed to beat across a year of real data
— so the agent is never able to act without the comparison sitting in its own state, and you are never
able to review a decision without seeing whether it beat inaction.

**The agent cannot beat do-nothing, and the log will now say so honestly rather than report a rising
in-range percentage.**

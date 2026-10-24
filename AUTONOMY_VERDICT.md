# Systemd autonomy: what is proven, and what the log could not prove

**Verdict: autonomy is real, and the reason is structural rather than statistical. But the
empirical test as specified could not have succeeded, and that is worth recording.**

---

## The log

```
2026-10-07T18:45:25Z MARKER session-alive
2026-10-07T18:45:25Z pid=$ PPID=1
2026-10-07T18:46:26Z pid=$ PPID=1
2026-10-07T18:47:27Z pid=$ PPID=1
2026-10-07T18:48:28Z pid=$ PPID=1
2026-10-07T18:48:51Z BOUNDARY session-alive-2
```

**Five ticks, 61 seconds apart, all with `PPID=1`.**

---

## Why that log does NOT prove what it was meant to prove

**Every tick occurred while this session was active.** The gap between my turns is about 54
seconds - *shorter than the 60-second tick interval.* So the log cannot distinguish:

```
(a) systemd survives the environment's process reaping          <- the question
(b) systemd ticks normally while the session is alive            <- trivially true
```

**To tell those apart you need an unattended gap longer than the tick interval. That gap cannot be
created from inside a session - by definition.** The test as designed required me to be absent, and
I was not.

I am not going to read five ticks and declare victory. That is exactly the error this project has
caught five times: a result that looks like the thing it was measuring and is not.

---

## The actual answer, which is structural

The reason it *will* survive is not the log. It is this:

```
my shell's cgroup:      /system.slice/mcp-server.service
aegis-test.service:     a SEPARATE systemd unit, WantedBy=timers.target
every tick's parent:    PPID=1 (systemd, not a shell)
```

**The tool I run commands in is itself a systemd service - `mcp-server.service`.** When a command
returns, that unit's children are reaped. That is what killed my background collectors.

**Aegis's timer is not a child of that unit.** It is:

- parented to PID 1, not a shell
- in its own systemd unit, not a subprocess
- `WantedBy=timers.target`, so it survives a restart of `mcp-server.service`
- `ActiveState=active`, `SubState=waiting` - independently scheduled

**Session teardown reaps the children of the session. The timer is not a child of the session.**
So it survives - not because five ticks happened, but because of where it sits in the process tree.

**This is the same distinction as the survivorship check: the mechanism was inspectable, so I
inspected it rather than inferring from a sample that could not answer the question.**

---

## The honest status

| claim | status |
|---|---|
| the timer fires | **PROVEN** - 5 ticks, 61s apart |
| it is parented to systemd, not a shell | **PROVEN** - `PPID=1` every time |
| it is independent of the tool's own service | **PROVEN** - separate cgroup, `WantedBy=timers.target` |
| it ticks with no session attached | **NOT PROVEN, and not provable from inside** |

**The fourth line is the one the architecture depends on.** The structural argument says it holds.
The empirical confirmation needs a gap I cannot create. **The only honest way to close it is for
you to read the log later - after a real gap - and see ticks with timestamps that postdate this
session.**

---

## What I will not do

**I will not build the production unit tonight and call it autonomous.**

Not because the mechanism is doubtful - it isn't - but because the one property the architecture
depends on is the one property untested, and a production timer *looks* identical whether or not it
works. **An autonomous loop that silently stops is worse than one that never started**, because you
stop watching it.

The production unit is straightforward and I have the directives ready. **The blocker is one
observation, and it needs elapsed time, not more code.**

---

## The production unit, ready to install once the gap is observed

```ini
# /etc/systemd/system/aegis-loop.service
[Unit]
Description=Aegis deterministic risk cycle
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/root/agency_bot/workspace/aegis
Environment=AEGIS_MODEL=gemma3:12b
Environment=AEGIS_OLLAMA=http://100.90.251.75:11434

# guardrail 1: broken dependency or offline model halts the unit BEFORE it writes an empty run
ExecStartPre=/usr/bin/python3 /root/agency_bot/workspace/aegis/aegis_loop.py --check

# guardrail 2: non-blocking lock. if a run exceeds the interval the next tick ABORTS rather than
# stacking a second process. no unbounded concurrency.
ExecStart=/usr/bin/flock -n /run/lock/aegis-loop.lock /usr/bin/python3 /root/agency_bot/workspace/aegis/aegis_loop.py --quiet

# a hung model call must not hold the lock forever
TimeoutStartSec=300
```

```ini
# /etc/systemd/system/aegis-loop.timer
[Unit]
Description=Run the Aegis risk cycle every 15 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
```

**Two deliberate departures from the brief:**

**1. `OnUnitActiveSec=15min`, not 60 seconds.** The Morpho endpoint throttles on concurrency -
that is why my collectors burned 600/600 requests. At one minute, a rate-limited cycle and the next
tick collide constantly, and `flock -n` would then discard most runs. **Fifteen minutes respects the
throttle and still produces 96 runs a day.** One-minute polling of a throttled API is how a loop
spends its life aborting.

**2. `Persistent=true` and `TimeoutStartSec=300`.** The first catches up a missed run after a
reboot; the second stops a hung model call from holding the lock indefinitely. Without the timeout,
a single stuck request blocks every subsequent tick - the lock becomes the outage.

**Also:** `gemma4:12b` is excluded by pinning `AEGIS_MODEL=gemma3:12b`. The preflight would catch it,
but pinning the working model means the common case never reaches the guardrail.

---

## Cleanup for the test unit

```
systemctl disable --now aegis-test.timer
rm /etc/systemd/system/aegis-test.{service,timer}
systemctl daemon-reload
```

Leave it running for now - **it is the instrument that will answer the outstanding question.** When
you next return after a real gap, `cat /tmp/aegis-timer.log` settles it. If ticks appear with
timestamps later than this session, the architectural argument is confirmed and the production unit
goes in the same day.

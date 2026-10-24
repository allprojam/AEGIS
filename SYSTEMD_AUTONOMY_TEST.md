# Systemd autonomy test — set up 2026-10-07T18:45Z

## The question

Background processes in this environment die when the invoking session returns. Does a systemd
timer survive that, or is true autonomy impossible here?

## The test

```
/etc/systemd/system/aegis-test.service   oneshot, appends a UTC timestamp to /tmp/aegis-timer.log
/etc/systemd/system/aegis-test.timer     OnUnitActiveSec=60s
```

Seeded with a marker so ordering is provable:

```
2026-10-07T18:45:25Z MARKER session-alive
```

## What was confirmed BEFORE ending the session

The timer genuinely fires, and the process is reparented:

```
2026-10-07T18:45:25Z MARKER session-alive
2026-10-07T18:45:25Z pid=$ PPID=1        <-- PPID 1 = systemd, not the shell
```

`PPID=1` is the mechanism that matters: the job is not a child of the invoking shell, so session
teardown should not reap it. (`pid=$` printed literally — a quoting bug in the ExecStart, cosmetic
only; the append worked.)

## What the next session determines

Read `/tmp/aegis-timer.log`. Specifically, lines with a timestamp **later** than the marker, at
greater than 60-second spacing, mean the timer ticked while nothing was attached.

- **If it ticked while unattended** -> systemd survives the reaping, and the autonomous loop is a
  timer pointing at `aegis_loop.py --quiet`. Phase C is viable.
- **If it did not tick** -> autonomy here is not achievable and every run stays a manual
  invocation. That is an acceptable constraint, and the correct response is to accept it rather
  than build machinery that only appears to work.

## Cleanup, whichever way it goes

```
systemctl disable --now aegis-test.timer
rm /etc/systemd/system/aegis-test.{service,timer}
systemctl daemon-reload
```

## If it works, the production unit is NOT this one

This test only proves the timer mechanism. The real unit would need, before it is trusted:

- `Type=oneshot` calling `aegis_loop.py --quiet`
- `Environment=AEGIS_MODEL=gemma3:12b` (gemma4:12b returns empty responses — verified)
- a lock so two runs cannot overlap
- the preflight from `aegis_loop.py --check` as `ExecStartPre`, so a broken dependency fails the
  unit loudly instead of writing an empty run
- a rate limit on the model call, since the model is on a different tailnet node

#!/usr/bin/env python3
"""aegis_run.py - one deterministic evaluation, written as an immutable run.

This is the Sense -> Evaluate -> Commit half of the agentic loop, with the Reason phase
deliberately left as an OPTIONAL, clearly-separated step (--reason). The reason: the
deterministic engine must be able to run and be audited with no model in the path at all.
If the model is unavailable or broken, the screen must still produce a stamped record.

    python3 aegis_run.py                    # sense + evaluate + commit (no model)
    python3 aegis_run.py --reason           # also add LLM triage, clearly labelled as such
    python3 aegis_run.py --top 100

APPEND-ONLY: writes runs/<iso>/{markets,screen,meta}.json and never overwrites. The dashboard
reads the latest run; every earlier run stays on disk as a fact.

EXPLICITLY NOT DONE HERE: no allocation, no signing, no transactions, no writes to any shared
state. This is read-only analysis with an immutable record of itself.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import provenance   # module-level: prompt_meta() uses _sha() and is defined below

MODEL_HOST = os.environ.get("AEGIS_OLLAMA", "http://100.90.251.75:11434")
# gpu.js names gemma4:12b. An earlier note here recorded it as "RETURNS EMPTY RESPONSES" and
# pinned gemma3:12b instead. THAT DIAGNOSIS WAS WRONG, and the correction matters:
#
# gemma4:12b enables REASONING by default. It writes its internal chain-of-thought into a
# separate `thinking` field BEFORE emitting `response`. Measured on a real triage prompt:
#     thinking: 1244-2589 tokens     response:  39-314 tokens
# The reasoning is 4-7x longer than the answer. At num_predict=512 the model was still
# reasoning when the budget expired, so `response` came back EMPTY with done_reason="length",
# roughly one run in three. That is a BUDGET problem, not a broken model.
#
# So: keep gemma4 selected but give it room, and read the right field for whichever endpoint is
# used. gemma3:12b remains the fallback because it does not reason and needs far less budget.
#
# RESOLUTION (measured 2026-10-08, on the REAL 1,503-char triage prompt, not a toy one):
#
#   gemma4:12b  num_predict=2048  -> resp=0     thinking=5453  eval=2048  done=length
#   gemma4:12b  num_predict=2048  -> resp=0     thinking=5290  eval=2048  done=length
#   gemma4:12b  num_predict=4096  -> resp=0     thinking=8560  eval=3309  done=length
#   gemma3:12b  num_predict=512   -> resp=432   thinking=0     eval=123   done=stop
#
# gemma4 does not answer this prompt AT ANY TESTED BUDGET. It reasons until the budget is gone
# and never emits a response. So the original pin was CORRECT -- but for the wrong reason. It is
# not "returns empty responses" as an intermittent fault; it is "spends everything on reasoning".
# gemma3 is 6.7x faster (11.5s of generation vs 77.1s total), does not reason, and produces a
# sound answer that correctly reads the data.
#
# The earlier note said "Do not change without testing for non-empty output." That test was done,
# by accident, using a TOY prompt ("reply READY") on which gemma4 passes. It fails on the real
# one. Test a model at the shape of prompt it will actually receive.
MODEL = os.environ.get("AEGIS_MODEL", "gemma3:12b")
NUM_PREDICT = int(os.environ.get("AEGIS_NUM_PREDICT", "512"))
# A reasoning model needs room for thinking BEFORE its answer. If a future model reasons, this
# is the budget it needs; set AEGIS_NUM_PREDICT=4096 and expect no answer on long prompts.
MODEL_FALLBACK = os.environ.get("AEGIS_MODEL_FALLBACK", "gemma3:12b")


def llm_triage(prompt, timeout=180):
    """Ask the model to triage. Returns (text, note). Never raises into the caller."""
    import urllib.request
    try:
        body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                           "options": {"num_predict": NUM_PREDICT},
                           "keep_alive": "30m"}).encode()
        r = urllib.request.Request(MODEL_HOST + "/api/generate", data=body,
                                   headers={"Content-Type": "application/json"})
        j = json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())
        txt = (j.get("response") or "").strip()
        think = j.get("thinking") or ""
        if not txt and j.get("done_reason") == "length":
            # Ran out of budget while still reasoning. This is NOT "nothing to report" -- it is
            # an unfinished run. Reported as such so a truncated answer is never mistaken for a
            # clean bill of health.
            return None, ("TRUNCATED: %s spent the whole %d-token budget on reasoning "
                          "(thinking=%d chars) and never emitted an answer. Raise "
                          "AEGIS_NUM_PREDICT." % (MODEL, NUM_PREDICT, len(think)))
        if not txt:
            return None, "EMPTY RESPONSE from %s - treat as failure, not as 'no findings'" % MODEL
        return txt, None
    except Exception as e:
        return None, "model unreachable: %s" % str(e)[:60]


def triage_prompt(flagged, total, markets=None):
    """Build the triage prompt.

    TWO BUGS FOUND BY TESTING THE FIRST VERSION:

    1. It truncated to flagged[:8]. The first eight happened to all be HERMES, so the model
       reported "all flagged markets are HERMES" -- true of the sample, false of the set.
       A truncation that happens to be unrepresentative is indistinguishable from a lie.
    2. It never passed bad_debt_usd. The single largest risk in the dataset (USR, $34.8M)
       was structurally invisible to the model.

    Fixed: summarise the WHOLE flagged set by group, and always include bad debt and the
    worst offenders by TVL, so the prompt cannot hide the headline risk.
    """
    import collections
    groups = collections.Counter(r.get("collateral") for r in flagged)
    reasons = collections.Counter(f for r in flagged for f in (r.get("fails") or []))
    bd = sorted([r for r in flagged if (r.get("bad_debt_usd") or 0) > 0],
                key=lambda r: -(r.get("bad_debt_usd") or 0))
    big = sorted(flagged, key=lambda r: -(r.get("tvl_usd") or 0))[:6]

    lines = []
    lines.append("COLLATERAL GROUPS AMONG THE %d FLAGGED:" % len(flagged))
    for k, v in groups.most_common(12):
        lines.append("  %s: %d" % (k, v))
    lines.append("")
    lines.append("RULE HITS:")
    for k, v in reasons.most_common():
        lines.append("  %s: %d" % (k, v))
    lines.append("")
    if bd:
        lines.append("MARKETS CARRYING BAD DEBT (highest first):")
        for r in bd[:5]:
            lines.append("  %s: bad_debt_usd=%s, tvl_usd=%s, util=%.3f, lltv=%.3f"
                         % (r.get("collateral"), format(int(r.get("bad_debt_usd") or 0), ","),
                            format(int(r.get("tvl_usd") or 0), ","),
                            r.get("utilization") or 0, r.get("lltv") or 0))
        lines.append("")
    lines.append("LARGEST FLAGGED BY TVL:")
    for r in big:
        lines.append("  %s: verdict=%s, tvl_usd=%s, util=%.3f, lltv=%.3f, fails=%s"
                     % (r.get("collateral"), r.get("verdict"),
                        format(int(r.get("tvl_usd") or 0), ","),
                        r.get("utilization") or 0, r.get("lltv") or 0,
                        ",".join(r.get("fails") or [])))
    return (
        "You are summarising a deterministic risk screen of %d lending markets, %d of which "
        "are flagged. Write at most 5 sentences. Use ONLY the numbers below. State the single "
        "largest risk first. If a figure is not listed, do not produce it. Do not predict "
        "prices or returns.\n\n%s" % (total, len(flagged), "\n".join(lines))
    )


# ---------------------------------------------------------------------------------------------
# ORCHESTRATOR INITIATOR (orchestrator-v2)
#
# The text that STARTS one cycle, as opposed to triage_prompt() above which summarises one
# RESULT. Kept here, next to PROMPT_VERSION, so both prompts that can shape a run are versioned
# and hashed the same way and neither can change shape unnoticed.
#
# WHY THIS CARRIES A CORRELATION AND NOT JUST INSTRUCTIONS: the orchestrator's most likely
# serious mistake is optimising the wrong objective, and it would commit that mistake while
# performing perfectly. Measured on 1y of real ETH hourly data:
#
#   recenter 1h      -> in-range 99.7%  -> final $512.58
#   recenter 168h    -> in-range 93.6%  -> final $455.33
#   never (static)   -> in-range  4.7%  -> final $1034.68
#
# CORRELATION(in-range%, final $) = -0.923. In-range time nearly triples while terminal wealth
# halves. An agent told to maximise in-range time destroys the account efficiently and correctly.
# So the initiator names the objective rather than assuming it.
# ---------------------------------------------------------------------------------------------
ORCHESTRATOR_VERSION = "orchestrator-v2"

ORCHESTRATOR_INITIATOR = (
    "AEGIS CYCLE - one pass. You are the orchestrator.\n"
    "\n"
    "The cycle is SENSE -> EVALUATE -> REASON -> COMMIT -> VERIFY. Run them in that order.\n"
    "EVALUATE is hermetic and involves no model. REASON is optional and must be labelled.\n"
    "\n"
    "HARD RULES\n"
    "  1. Use only numbers present in the run. If a figure is not in the input, do not produce it.\n"
    "  2. Never predict prices or returns.\n"
    "  3. REASON is opt-in. A cycle that silently reasoned is one whose output cannot be\n"
    "     attributed to the screen.\n"
    "  4. COMMIT writes an immutable run. If VERIFY cannot reproduce it, exit 1. Do not retry\n"
    "     into a green result.\n"
    "  5. If a dependency is unhealthy, exit 2 and write nothing.\n"
    "\n"
    "READ FIRST, in order: STATE.md (live board), ARCHITECTURE.md (contract), DECISIONS.md\n"
    "(locked decisions). Write to STATE.md before and after working.\n"
    "\n"
    "OBJECTIVE. Do not optimise in-range time. Measured on 1y of real ETH hourly data,\n"
    "CORRELATION(in-range%, final $) = -0.923: recentering every hour reaches 99.7% in-range for\n"
    "$512.58, while a static position at 4.7% in-range returns $1034.68. The metric improves\n"
    "while the account halves. Optimise capital, not range occupancy.\n"
    "\n"
    "FIRST ACTION: run preflight and report what it returns. Do not assume the model is healthy:\n"
    "gemma4:12b returns resp=0 at every tested budget because it REASONS into the limit and\n"
    "writes chain-of-thought to a different field - it is not broken, it is answering elsewhere.\n"
    "  python3 screener/aegis_loop.py --check\n"
)

def orchestrator_meta():
    """Audit record for the INITIATOR, mirroring prompt_meta().

    Same reason as prompt_meta: the run must record what the orchestrator was TOLD, not only what
    it did. A change in the initiator's shape is otherwise invisible in the run history.
    """
    return {
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "orchestrator_sha256": provenance._sha(ORCHESTRATOR_INITIATOR),
        "orchestrator_chars": len(ORCHESTRATOR_INITIATOR),
        "orchestrator_text": ORCHESTRATOR_INITIATOR,
    }


PROMPT_VERSION = "triage-v2"   # bump whenever triage_prompt() changes shape


def prompt_meta(prompt, flagged, total):
    """Everything needed to audit WHY the model said what it said.

    Without the prompt text, the Reason phase cannot be audited: the same model given a
    truncated or incomplete prompt produces a different summary, and the run record would
    show only the output. Versioned so a change in prompt shape is visible in the record.
    """
    return {
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": provenance._sha(prompt),
        "prompt_chars": len(prompt),
        "prompt_text": prompt,
        "input_scope": {
            "total_markets": total,
            "flagged_shown": len(flagged),
            "truncated": False,          # v2 summarises the whole flagged set by group
            "bad_debt_included": True,   # v2 always includes it; v1 omitted it entirely
        },
    }


def main():
    do_reason = "--reason" in sys.argv
    n = 100
    if "--top" in sys.argv:
        n = int(sys.argv[sys.argv.index("--top") + 1])

    import morpho_fetch as mf
    import lending_screen as ls

    t0 = time.time()
    print("=== Aegis run %s ===" % provenance._iso(), flush=True)

    # --- SENSE (read-only) ---
    print("[sense] fetching markets...", flush=True)
    raw = mf.fetch_markets(n)
    rows = [mf.normalize(m) for m in raw]
    blk = provenance.block_from_rows(rows)
    stamped, prov = provenance.stamp(rows, mf.API, block_number=blk,
                                     extra={"markets_requested": n})
    print("  %d markets, block %s" % (len(stamped), blk), flush=True)

    # --- EVALUATE (hermetic, no model) ---
    print("[evaluate] running the lending screen...", flush=True)
    # Enrich each market with the collateral-to-volatility margin BEFORE screening, so the
    # number lands in the immutable run and every consumer (dashboard, tear sheet, allocator)
    # reads it from there instead of recomputing it. price_cache.json is a local cache; a
    # missing entry simply leaves the fields absent rather than inventing a value.
    try:
        import json as _j
        _cache_path = os.path.join(os.path.dirname(os.path.abspath(ls.__file__)), "price_cache.json")
        _cache = _j.load(open(_cache_path)) if os.path.exists(_cache_path) else {}
        _enriched = []
        for m in stamped:
            pts = _cache.get(m.get("market_id")) or []
            _enriched.append(ls.add_volatility(m, pts) if pts else m)
        _n = sum(1 for m in _enriched if m.get("sigma_to_breach") is not None)
        # ALWAYS report coverage, and SHOUT when it is zero.
        #
        # The old form printed only when _n was non-zero, so the worst case was the quietest:
        # a missing or stale price_cache.json left every market without volatility, every market
        # then failed VOL_UNKNOWN, and the allocator produced $0 with NO explanation on stdout.
        # MEASURED: stripping the vol fields (exactly what a missing cache yields) gives
        # 0 eligible and $0 allocated out of 60 markets. A cycle that silently allocates nothing
        # is indistinguishable from "no opportunities today", which is the same silent-zero
        # failure class as the counter that read 0 for a passing suite.
        _tot = len(_enriched)
        print("  [vol] sigma computed for %d/%d markets" % (_n, _tot), flush=True)
        if _n == 0 and _tot:
            _cp = _cache_path if os.path.exists(_cache_path) else "(missing)"
            print("  [vol] WARNING: NO market has volatility. Every market will fail "
                  "VOL_UNKNOWN and the allocator will allocate nothing. Check the price "
                  "cache: %s  entries=%d" % (_cp, len(_cache) if isinstance(_cache, dict) else 0),
                  flush=True)
        elif _tot and _n < _tot * 0.5:
            print("  [vol] WARNING: coverage under 50%% (%d/%d). Markets without price "
                  "history are rejected as VOL_UNKNOWN, so low coverage silently shrinks the "
                  "eligible set." % (_n, _tot), flush=True)
        stamped = _enriched
    except Exception as _e:
        print("  [vol skipped: %s]" % str(_e)[:60])

    screen = [ls.screen_market(m) for m in stamped]
    counts = {}
    for r in screen:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("  %s" % counts, flush=True)
    flagged = [r for r in screen if r["verdict"] != "REAL"]
    print("  %d flagged" % len(flagged), flush=True)

    # --- REASON (optional, isolated, labelled) ---
    reason_txt, reason_note = None, "not requested"
    pmeta = None
    if do_reason:
        prompt = triage_prompt(flagged, len(screen), markets=screen)
        pmeta = prompt_meta(prompt, flagged, len(screen))
        print("[reason] asking %s (prompt %s, %d chars) ..."
              % (MODEL, PROMPT_VERSION, pmeta["prompt_chars"]), flush=True)
        reason_txt, reason_note = llm_triage(prompt)
        if reason_note:
            print("  NOT USED: %s" % reason_note, flush=True)
        else:
            print("  %d chars" % len(reason_txt), flush=True)

    # --- COMMIT (immutable) ---
    prov = dict(prov)
    prov["screen_verdicts"] = counts
    prov["flagged_count"] = len(flagged)
    prov["reason"] = {
        "requested": do_reason,
        "model": MODEL if do_reason else None,
        "host": MODEL_HOST if do_reason else None,
        "used": bool(reason_txt),
        "note": reason_note,
    }
    if pmeta:
        prov["reason"]["prompt_version"] = pmeta["prompt_version"]
        prov["reason"]["prompt_sha256"] = pmeta["prompt_sha256"]
    # The initiator is recorded on EVERY run, not only when --reason is used, because it is what
    # started the cycle in either case. Without this the run history shows what the model said
    # but not what the orchestrator was told, and the two prompts then have different audit
    # strength for no good reason.
    _ometa = orchestrator_meta()
    prov["orchestrator"] = {
        "version": _ometa["orchestrator_version"],
        "sha256": _ometa["orchestrator_sha256"],
        "chars": _ometa["orchestrator_chars"],
    }
    note = "reason phase %s" % ("included" if reason_txt else "absent")

    # write_run() needs the model artefacts to already exist so meta.json can checksum them.
    # Create the directory first, drop the optional files in, then let write_run fill the rest.
    run = provenance.run_dir_utc()

    # Write the allocation into the run BEFORE write_run checksums it, so meta.json covers
    # allocator.json. It cannot be produced earlier because it needs screen.json, which does
    # not exist until write_run runs -- so this is written from the in-memory `screen` rows.
    # Simulation only: this records targets, it does not move funds.
    try:
        import allocator as _al
        _cap = float(os.environ.get("AEGIS_CAPITAL_USD", "1000000"))
        _res = _al.allocate(stamped, screen,
                            {m.get("market_id"): (m.get("oracle_type") or "Unknown") for m in stamped},
                            {}, capital_usd=_cap,
                            sigma_hint={m.get("market_id"): m.get("sigma_to_breach") for m in stamped})
        _res["run_dir"] = os.path.basename(run)
        json.dump(_res, open(os.path.join(run, "allocator.json"), "w"), indent=1)
        print("[allocate] %d positions, $%s of $%s (capital=%s)"
              % (_res["n_selected"], format(int(_res["allocated_usd"]), ","),
                 format(int(_res["capital_usd"]), ","), format(int(_cap), ",")), flush=True)
    except Exception as _e:
        print("  [allocator skipped: %s]" % str(_e)[:70], flush=True)
    if pmeta:
        json.dump(pmeta, open(os.path.join(run, "prompt.json"), "w"), indent=1)
    # Full initiator text, so a future reader can diff what the orchestrator was told without
    # reconstructing it from a git revision of this file.
    json.dump(orchestrator_meta(), open(os.path.join(run, "orchestrator.json"), "w"), indent=1)
    if reason_txt:
        json.dump({"model": MODEL, "host": MODEL_HOST, "text": reason_txt,
                   "prompt_version": PROMPT_VERSION,
                   "generated_at": provenance._iso()},
                  open(os.path.join(run, "reason.json"), "w"), indent=1)
    provenance.write_run(stamped, screen, prov, note=note, into=run)

    print("[commit] %s" % os.path.relpath(run, HERE), flush=True)

    # --- VERIFY (replay the run we just wrote) ---
    ok, a, b = provenance.verify_run(run)
    print("[verify] replay: %s (%d rows)" % ("REPRODUCES EXACTLY" if ok else "DRIFT", a), flush=True)
    print("  elapsed %.1fs" % (time.time() - t0), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

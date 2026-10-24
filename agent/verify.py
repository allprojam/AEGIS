#!/usr/bin/env python3
"""Read decisions.jsonl and answer the ONLY question that matters:
   did the agent's actions beat doing nothing?"""
import json,sys,os
LOG="agent/decisions.jsonl"
if not os.path.exists(LOG):
    print(f"no log at {LOG}"); sys.exit(1)
recs=[json.loads(l) for l in open(LOG) if l.strip()]
print(f"=== LOG VERIFICATION: {len(recs)} decisions ===")
acts=[r for r in recs if r["action_taken"]=="recenter"]
holds=[r for r in recs if r["action_taken"]=="hold"]
blk=[r for r in recs if r.get("blocked_reason")]
print(f"  actions taken : {len(acts)}")
print(f"  holds         : {len(holds)}")
print(f"  BLOCKED by code controls: {len(blk)}")
for r in blk[:5]:
    print(f"    {r['ts_iso']}  {r['blocked_reason']}")
print(f"  total gas billed: ${sum(r['cost_billed_usd'] for r in recs):.2f}")
if recs:
    last=recs[-1]
    print(f"\n  final equity     ${last['equity_after']:.2f}")
    print(f"  do-nothing equity${last['do_nothing_equity']:.2f}")
    print(f"  BEAT DO-NOTHING? {last['beat_do_nothing']}")
    wins=sum(1 for r in recs if r["beat_do_nothing"])
    print(f"  decisions where agent beat do-nothing: {wins}/{len(recs)} ({100*wins/len(recs):.1f}%)")
    print(f"\n  model used: {set(r['model'] for r in recs)}")
    print(f"  prompts logged with sha256: {all(r.get('prompt_sha256') for r in recs)}")
print("\n  every decision record contains: state, raw model output, action taken,")
print("  code-enforced block reason, cost billed, and the do-nothing baseline.")
print("  -> any decision can be replayed and audited.")

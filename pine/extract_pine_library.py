import json, os, re
recs = json.load(open("pine/library/raw.json"))
srcs = [r for r in recs if (r.get("scriptSource") or "").strip()]
os.makedirs("pine/library/src", exist_ok=True)
C = 5.0  # bps round trip, our real number

def friction_avgwin(w, avgloss_bps, c=C):
    return ((1-w)*avgloss_bps + c)/w

rows = []
for r in srcs:
    s = r["scriptSource"]; name = r.get("scriptName","")
    sid = r["scriptIdPart"]
    open(f"pine/library/src/{sid}.pine","w").write(s)
    low = s.lower()
    lengths = [int(x) for x in re.findall(r"\b(?:sma|ema|wma|hma|rma|atr|rsi|stoch)\s*\(\s*[^,]+,\s*(\d+)", low)]
    atr_mult = [float(x) for x in re.findall(r"atr[^)]*\)\s*\*\s*([\d.]+)", low)]
    has_sec = "security(" in low or "request.security" in low
    lookahead_ok = ("lookahead" in low) or not has_sec
    rows.append({
        "id": sid, "name": name[:56], "author": (r.get("author") or {}).get("username"),
        "likes": r.get("agreeCount",0), "len": len(s),
        "maxMA": max(lengths) if lengths else 0,
        "minMA": min(lengths) if lengths else 0,
        "atrMult": max(atr_mult) if atr_mult else 0,
        "sec": has_sec, "la_ok": lookahead_ok,
        "comm": bool(re.search(r"commission", low)),
        "exit": "strategy.exit" in s, "close": "strategy.close" in s,
        "shorts": bool(re.search(r"strategy\.(short|entry)\s*\([^)]*strategy\.short", s)),
        "req_win_when_40": round(friction_avgwin(0.40, 30),1),
    })
rows.sort(key=lambda x: (-x["likes"]))
print(f"{'likes':>6}{'maxMA':>6}{'atrX':>6}{'sec':>4}{'laOK':>5}{'comm':>5}{'exit':>5}  name")
for x in rows:
    print(f"{x['likes']:>6}{x['maxMA']:>6}{x['atrMult']:>6.1f}{str(x['sec']):>4}{str(x['la_ok']):>5}{str(x['comm']):>5}{str(x['exit']):>5}  {x['name']}")
json.dump(rows, open("pine/library/screen.json","w"), indent=1)
print("\nfriction math (C=5bps): required avg WIN in bps, at 30bps avg loss")
for w in (0.35,0.40,0.45,0.50,0.55):
    print(f"   win rate {w:.0%} -> need {friction_avgwin(w,30):.1f} bps avg win  (GPU said 124 at 50bps: it used 10x our cost)")

import sys, json, glob
rows=[]
for f in glob.glob("logs/paper-ticks-*.jsonl"):
    for l in open(f):
        try: rows.append(json.loads(l))
        except: pass
print("ticks:", len(rows))
for d in rows[-6:]:
    h=d["signals"]["hull"]; m=d["signals"]["macd_bb"]
    print(f"{d['ts']} | dex {d['dex']['price']:>9.2f} {d['dex']['venue']:<12} | "
          f"HMA1 {h.get('HMA1')} HMA2 {h.get('HMA2')} | MACDBB {m.get('line')} U {m.get('upper')} B {m.get('lower')} | "
          f"{d['events']} | pos {d['position']}")
print("--- trades ---")
for f in glob.glob("logs/paper-trades-*.jsonl"):
    for l in open(f):
        t=json.loads(l); print(" ", t["ts"], t["action"], t.get("px"), t.get("net_usd",""), t.get("reason",""))

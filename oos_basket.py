#!/usr/bin/env python3
"""PRE-REGISTERED out-of-sample transfer test.

E2 was developed on BTC and ETH. Its parameters (14/100, BB 2.0, 1h, long-only) were
chosen with knowledge of that data. This script freezes those parameters COMPLETELY and
runs them on assets never used in development. Nothing is tuned here.

Pass criteria, fixed BEFORE looking at results:
  PASS = positive AND both H1 and H2 positive AND >= 15 trades AND t >= 1.0
"""
import numpy as np, pandas as pd, math, glob, os
import verify_e2 as V

FAST, SLOW, BBK = 14, 100, 2.0      # FROZEN

def evaluate(d):
    if len(d) < SLOW * 3: return None
    ent, ext, f = V.signals(d, fast=FAST, slow=SLOW, bb_k=BBK)
    eq, tr = V.method_trades(d, ent, ext)
    c = d.close.to_numpy()
    bh = 100*(c[-1]/c[0]-1)
    if len(tr) < 3:
        return {"ret": 100*(eq-1), "bh": bh, "n": len(tr), "t": float('nan'),
                "win": None, "bars": None, "worst": None, "h1": None, "h2": None}
    r = np.array([c[j]/c[i]-1 for i, j in tr])
    t = r.mean()/(r.std(ddof=1)/math.sqrt(len(r))) if r.std(ddof=1) > 0 else float('nan')
    mid = len(d)//2
    h1 = evaluate_slice(d.iloc[:mid].reset_index(drop=True))
    h2 = evaluate_slice(d.iloc[mid:].reset_index(drop=True))
    return {"ret": 100*(eq-1), "bh": bh, "n": len(tr), "t": t,
            "win": float((r>0).mean()), "bars": float(np.mean([j-i for i,j in tr])),
            "worst": float(r.min()*100), "h1": h1, "h2": h2}

def evaluate_slice(d):
    if len(d) < SLOW * 3: return None
    ent, ext, f = V.signals(d, fast=FAST, slow=SLOW, bb_k=BBK)
    eq, tr = V.method_trades(d, ent, ext)
    return 100*(eq-1)

if __name__ == "__main__":
    files = sorted(glob.glob("bars_*_1h_3y.csv"))
    print(f"PRE-REGISTERED OOS TEST  params frozen: {FAST}/{SLOW}, BB {BBK}, 1h, long only")
    print(f"PASS = positive AND H1>0 AND H2>0 AND n>=15 AND t>=1.0\n")
    print(f"{'asset':<12}{'bars':>7}{'ret%':>9}{'B&H%':>9}{'n':>5}{'win':>6}{'bars':>7}{'worst':>8}{'t':>6}{'H1':>8}{'H2':>8}  verdict")
    passes = 0; total = 0
    for f in files:
        name = os.path.basename(f).replace("bars_","").replace("_1h_3y.csv","").upper()
        d = pd.read_csv(f).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        r = evaluate(d)
        if not r or r["n"] < 3: 
            print(f"{name:<12}{len(d):>7}  -- insufficient ({r['n'] if r else 0} trades)"); continue
        total += 1
        h1 = r["h1"] if r["h1"] is not None else float('nan')
        h2 = r["h2"] if r["h2"] is not None else float('nan')
        ok = (r["ret"]>0 and h1>0 and h2>0 and r["n"]>=15 and r["t"]>=1.0)
        passes += ok
        v = "PASS" if ok else "fail"
        print(f"{name:<12}{len(d):>7}{r['ret']:>9.1f}{r['bh']:>9.1f}{r['n']:>5}{r['win']:>6.2f}"
              f"{r['bars']:>7.0f}{r['worst']:>8.1f}{r['t']:>6.2f}{h1:>8.1f}{h2:>8.1f}  {v}")
    print(f"\nPASSED {passes}/{total} unseen assets")

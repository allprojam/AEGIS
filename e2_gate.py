"""E2 against the gate that rejected all 179 earlier candidates: H1/H2 split + per-year."""
import numpy as np, pandas as pd, math
from verify_e2 import signals, method_trades

def perf(d):
    ent, ext, f = signals(d)
    if len(d) < 150: return None
    eq, tr = method_trades(d, ent, ext)
    if len(tr) < 1: return {"ret": 0, "n": 0, "t": float('nan'), "bars": 0}
    c = d.close.to_numpy()
    r = np.array([c[j]/c[i]-1 for i,j in tr])
    t = r.mean()/(r.std(ddof=1)/math.sqrt(len(r))) if len(r) > 2 and r.std(ddof=1) > 0 else float('nan')
    return {"ret": 100*(eq-1), "n": len(tr), "t": t,
            "bars": float(np.mean([j-i for i,j in tr])), "win": float((r>0).mean())}

for path, tag in (("bars_btc_1h_3y.csv","BTC"), ("bars_eth_1h_365d.csv","ETH")):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d["dt"] = pd.to_datetime(d.time, unit="s")
    mid = len(d)//2
    print(f"\n========== {tag} ==========")
    print(f"{'slice':<16}{'bars':>7}{'ret%':>9}{'n':>5}{'win':>6}{'bars':>7}{'t':>7}{'vs B&H':>9}")
    for lab, sl in (("FULL", d), ("H1", d.iloc[:mid]), ("H2", d.iloc[mid:])):
        sl = sl.reset_index(drop=True)
        p = perf(sl); bh = 100*(sl.close.iloc[-1]/sl.close.iloc[0]-1)
        if p: print(f"{lab:<16}{len(sl):>7}{p['ret']:>9.1f}{p['n']:>5}{(p.get('win') or 0):>6.2f}"
                    f"{(p.get('bars') or 0):>7.0f}{p['t']:>7.2f}{p['ret']-bh:>+9.1f}")
    print("  --- by calendar year ---")
    for y in sorted(d.dt.dt.year.unique()):
        sl = d[d.dt.dt.year==y].reset_index(drop=True)
        p = perf(sl); bh = 100*(sl.close.iloc[-1]/sl.close.iloc[0]-1)
        if p: print(f"{y:<16}{len(sl):>7}{p['ret']:>9.1f}{p['n']:>5}{(p.get('win') or 0):>6.2f}"
                    f"{(p.get('bars') or 0):>7.0f}{p['t']:>7.2f}{p['ret']-bh:>+9.1f}")

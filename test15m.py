"""E2 on 15m -- the timeframe the user's chart is actually on, and untested until now.
Same frozen params: 14/100, BB 2.0, long only. No tuning."""
import numpy as np, pandas as pd, math
import verify_e2 as V
print("E2 frozen params on 15m (long only). buy & hold shown for reference.")
print(f"{'asset':<12}{'bars':>7}{'days':>6}{'ret%':>9}{'B&H%':>9}{'n':>5}{'win':>6}{'bars':>7}{'worst':>8}{'t':>6}{'H1':>8}{'H2':>8}")
for path, tag in (("bars_btc_15m_180d.csv","BTC 15m"), ("bars_btc_5m_180d.csv","BTC 5m")):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    ent, ext, f = V.signals(d, fast=14, slow=100, bb_k=2.0)
    eq, tr = V.method_trades(d, ent, ext)
    c = d.close.to_numpy(); bh = 100*(c[-1]/c[0]-1)
    days = (d.time.iloc[-1]-d.time.iloc[0])/86400
    if len(tr) > 2:
        r = np.array([c[j]/c[i]-1 for i,j in tr])
        t = r.mean()/(r.std(ddof=1)/math.sqrt(len(r)))
        mid = len(d)//2
        e1,_ = V.method_trades(d.iloc[:mid].reset_index(drop=True), *V.signals(d.iloc[:mid].reset_index(drop=True))[:2])
        e2,_ = V.method_trades(d.iloc[mid:].reset_index(drop=True), *V.signals(d.iloc[mid:].reset_index(drop=True))[:2])
        print(f"{tag:<12}{len(d):>7}{days:>6.0f}{100*(eq-1):>9.1f}{bh:>9.1f}{len(tr):>5}"
              f"{(r>0).mean():>6.2f}{np.mean([j-i for i,j in tr]):>7.0f}{r.min()*100:>8.1f}{t:>6.2f}"
              f"{100*(e1-1):>8.1f}{100*(e2-1):>8.1f}")
    else:
        print(f"{tag:<12}{len(d):>7}{days:>6.0f}{100*(eq-1):>9.1f}{bh:>9.1f}{len(tr):>5}  (too few trades)")

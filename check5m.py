import numpy as np, pandas as pd, math
import verify_e2 as V
for path, tag in (("bars_btc_5m_180d.csv","BTC 5m 180d"),("bars_cb_5m_180d.csv","ETH 5m 180d")):
    try:
        d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    except Exception:
        print(tag, "skip"); continue
    ent, ext, f = V.signals(d)
    eq, tr = V.method_trades(d, ent, ext)
    bh = 100*(d.close.iloc[-1]/d.close.iloc[0]-1)
    c = d.close.to_numpy()
    if tr and len(tr) > 2:
        r = np.array([c[j]/c[i]-1 for i, j in tr])
        t = r.mean()/(r.std(ddof=1)/math.sqrt(len(r)))
        print(f"{tag}: bars {len(d)}  ret {100*(eq-1):+.1f}%  n={len(tr)}  win {(r>0).mean():.2f}  "
              f"bars {np.mean([j-i for i,j in tr]):.0f}  worst {r.min()*100:.1f}%  t={t:.2f}  "
              f"vs B&H {100*(eq-1)-bh:+.1f}pp")
    else:
        print(f"{tag}: {len(tr)} trades")

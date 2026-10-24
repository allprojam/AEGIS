"""How much trend does the 14/100 CROSS entry miss?
Measure: episodes where the 14 is above the 100, and whether price ever closes below
the 100 during them. Cross-entry can only fire after a prior cross, so shallow
pullbacks (never touching the 100) are invisible to it."""
import numpy as np, pandas as pd
for path, tag in (("bars_btc_1h_3y.csv","BTC 3y 1h"), ("bars_eth_1h_365d.csv","ETH 1y 1h")):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    c = d.close
    f, s = c.rolling(14).mean(), c.rolling(100).mean()
    up = (f > s).to_numpy(); below = (c < s).to_numpy()
    # walk episodes of f>s
    eps=[]; i=0; n=len(d)
    while i < n:
        if not up[i] or np.isnan(s[i]): i+=1; continue
        j=i
        while j+1<n and up[j+1]: j+=1
        eps.append((i,j)); i=j+1
    deep = [e for e in eps if below[e[0]:e[1]+1].any()]
    shallow = [e for e in eps if not below[e[0]:e[1]+1].any()]
    def span(e): return e[1]-e[0]+1
    tot = sum(span(e) for e in eps)
    print(f"\n===== {tag} =====  bars with 14>100: {up.sum()} ({100*up.sum()/n:.0f}% of series)")
    print(f"  trend episodes          : {len(eps)}")
    print(f"  DEEP (price went <100)  : {len(deep):>3}  = {sum(span(e) for e in deep):>6} bars")
    print(f"  SHALLOW (never <100)    : {len(shallow):>3}  = {sum(span(e) for e in shallow):>6} bars")
    if tot:
        print(f"  -> {100*sum(span(e) for e in shallow)/tot:.0f}% of uptrend bars are inside episodes")
        print(f"     that the CROSS entry cannot see (no 100-cross ever formed)")
    # how often does a fresh cross happen at all?
    cr = ((f>s)&(f.shift()<=s.shift())).sum()
    print(f"  fresh 14/100 cross-ups over the whole series: {cr}")

"""Is the walk-forward collapse overfitting, or just a weaker period?
Fair test: run the FIXED params (14,100,2.0) over the SAME out-of-sample window the
walk-forward covered (bars 9000 -> end), so both cover identical dates."""
import numpy as np, pandas as pd
import walkforward as WF

d = pd.read_csv("bars_btc_1h_3y.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
c = d.close.to_numpy(); n = len(c)
ent, ext = WF.arrays(d, 14, 100, 2.0)

print("Same-window comparison (bars 9000 -> end):\n")
eq_fixed, nt = WF.sim(c, ent, ext, 9000, n)
bh = c[-1]/c[9000] - 1
print(f"  FIXED params (14,100,2.0), one continuous run : {100*(eq_fixed-1):+8.1f}%   ({nt} trades)")
print(f"  WALK-FORWARD (re-chosen each fold)            : {100*(0.0):+8.1f}%   (see below)")
print(f"  buy & hold from bar 9000                      : {100*bh:+.1f}%")
print()
print("  -> if WALK-FORWARD << FIXED on the same bars, the params matter and the")
print("     headline number is partly a parameter-selection artefact.")
print()
# also: what would the BEST single param set have done on the OOS window?
import itertools
best=None
A = {q: WF.arrays(d, *q) for q in WF.GRID}
for p in WF.GRID:
    e1,e2 = A[p]
    eq,_ = WF.sim(c, e1, e2, 9000, n)
    if best is None or eq>best[0]: best=(eq,p)
print(f"  BEST of {len(WF.GRID)} param sets chosen WITH HINDSIGHT on this window: {100*(best[0]-1):+.1f}%  {best[1]}")
print(f"  -> that is the number you get if you tune on the test set; it is not achievable live.")

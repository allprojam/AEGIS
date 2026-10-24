import pandas as pd, numpy as np
s = pd.read_csv("logs/kelt_180_results.csv")
n = len(s)
p1 = (s.H1_net > 0).mean(); p2 = (s.H2_net > 0).mean(); both = ((s.H1_net>0)&(s.H2_net>0)).mean()
print(f"cells: {n}")
print(f"positive in H1: {p1:.1%}   positive in H2: {p2:.1%}   positive in BOTH: {both:.1%}")
print(f"if the halves were independent, expected BOTH = {p1*p2:.1%}  ->  {p1*p2*n:.1f} cells")
print(f"observed BOTH = {both*n:.0f} cells")
print(f"correlation(H1_net, H2_net) = {s.H1_net.corr(s.H2_net):+.3f}")
print(f"correlation(H1_n,   H2_n)   = {s.H1_n.corr(s.H2_n):+.3f}   (do the same configs even trade?)")
print(f"\nmedian net full period: {s.net.median():.2f}   mean: {s.net.mean():.2f}")
print(f"best cell net {s.net.max():.2f}   worst {s.net.min():.2f}")
# how much of the best cell's profit comes from its single best trade?
best = s.sort_values('net', ascending=False).iloc[0]
print(f"\nbest cell: klen={best.klen} atrlen={best.atrlen} dev={best.dev} exit={best['exit']}")
print(f"   net ${best.net:.2f} on {best.n:.0f} trades = ${best.net/best.n:.2f}/trade")
print(f"   win {best.win:.3f}  avgWin {best.aw}bps vs avgLoss {best.al}bps  (loss is {abs(best.al/best.aw):.1f}x the win)")
print(f"   avg hold {best.bars:.0f} bars = {best.bars*5/60:.1f} hours   maxDD ${best.dd:.2f} = {abs(best.dd)/250:.1%} of notional")
# sanity: expected value per trade in bps
ev = best.win*best.aw + (1-best.win)*best.al
print(f"   EV per trade = {ev:+.1f} bps   x{best.n:.0f} trades = {ev*best.n/10000*250:+.2f} USD  (matches net)")
print("\n--- split-half nets for the best cell ---")
print(f"   H1 {best.H1_net:+.2f} ({best.H1_n:.0f} trades)   H2 {best.H2_net:+.2f} ({best.H2_n:.0f} trades)")

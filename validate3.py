import pandas as pd
from pine_port import compute
df = pd.read_csv("bars_tv.csv")
d = compute(df)
L, P = d.iloc[-1], d.iloc[-2]
print("n=%d  usable=%d" % (len(d), int(d.hma3.notna().sum())))
print("--- LIVE (forming) bar, direct from the chart ---")
print(f"  port  HMA1={L.hma1:.2f} HMA2={L.hma2:.2f} HMA3={L.hma3:.2f}")
print(f"  chart HMA1=2687.43 HMA2=2686.72 HMA3=2685.99")
print(f"  diff  {L.hma1-2687.43:+.3f} {L.hma2-2686.72:+.3f} {L.hma3-2685.99:+.3f}")
print(f"  MACD-BB port line={L.bbmacd:.3f} (chart 0.82)")
print("--- last CLOSED bar, and the earlier consistent read ---")
print(f"  closed HMA1={P.hma1:.2f} HMA2={P.hma2:.2f} HMA3={P.hma3:.2f} | MACD-BB={P.bbmacd:.3f}")
print(f"  earlier live HMA1=2687.43 HMA2=2686.72 HMA3=2685.99 (chart, ~1h before) ")

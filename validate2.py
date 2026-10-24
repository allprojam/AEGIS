import pandas as pd
from pine_port import compute
df = pd.read_csv("bars_ethusd_5m.csv")
# append the chart's currently-forming bar (read live): t=1791070200 o=2687.34 c=2687.42
live = pd.DataFrame([{"time":1791070200,"open":2687.34,"high":2687.64,"low":2687.30,
                      "close":2687.42,"volume":0.0}])
dfa = pd.concat([df, live], ignore_index=True)
d = compute(dfa)
L = d.iloc[-1]
print("with the forming bar appended (n=%d):" % len(d))
print(f"  port  HMA1={L.hma1:.2f} HMA2={L.hma2:.2f} HMA3={L.hma3:.2f}")
print(f"  chart HMA1=2687.43 HMA2=2686.72 HMA3=2685.99")
print(f"  HMA1 diff={L.hma1-2687.43:+.3f}  HMA2 diff={L.hma2-2686.72:+.3f}  HMA3 diff={L.hma3-2685.99:+.3f}")
print(f"  MACD-BB line={L.bbmacd:.3f} (chart 0.82)")
print(f"  bsm_avg={L.bsm_avg:.4f} sdev={L.bsm_sdev:.4f} upper={L.banda_supe:.3f} lower={L.banda_inf:.3f}  (chart 0.75 / 0.14)")

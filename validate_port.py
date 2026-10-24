import pandas as pd
from pine_port import compute
df = pd.read_csv("bars_ethusd_5m.csv")
d = compute(df)
last = d.iloc[-1]; prev = d.iloc[-2]
print("bars:", len(d), " usable after warmup:", d["hma3"].notna().sum())
print("--- my port, LAST BAR (unfinished) ---")
print(f"  HMA1={last.hma1:.2f} HMA2={last.hma2:.2f} HMA3={last.hma3:.2f}")
print(f"  MACD-BB line={last.bbmacd:.3f} upper={last.banda_supe:.3f} lower={last.banda_inf:.3f}")
print("--- my port, PREV (last CLOSED) bar ---")
print(f"  HMA1={prev.hma1:.2f} HMA2={prev.hma2:.2f} HMA3={prev.hma3:.2f}")
print(f"  MACD-BB line={prev.bbmacd:.3f} upper={prev.banda_supe:.3f} lower={prev.banda_inf:.3f}")
print("--- chart said (live, unfinished) ---")
print("  HMA1=2687.43 HMA2=2686.72 HMA3=2685.99 | MACD-BB line=0.82 upper=0.75 lower=0.14")

import pandas as pd
d = pd.read_csv("bars_cb_5m_180d.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
mid = len(d)//2
for tag, h in (("H1", d.iloc[:mid]), ("H2", d.iloc[mid:]), ("FULL", d)):
    a, b = h.close.iloc[0], h.close.iloc[-1]
    hi, lo = h.close.max(), h.close.min()
    print(f"{tag:5} {pd.to_datetime(h.time.iloc[0],unit='s').date()} -> {pd.to_datetime(h.time.iloc[-1],unit='s').date()}  "
          f"close {a:8.2f} -> {b:8.2f}  buy&hold {100*(b/a-1):+6.2f}%   range {lo:.0f}-{hi:.0f}")
print("\nDaily vol (5m returns, annualised):")
r = d.close.pct_change().dropna()
print(f"   5m stdev {r.std()*100:.3f}%   daily ~{r.std()*(288**0.5)*100:.2f}%")

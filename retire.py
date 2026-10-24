import numpy as np
from math import erfc, sqrt, log
print("=== 1. WHAT DOES $150/WEEK FOR 30 YEARS REQUIRE? ===")
W=150.0; YR=W*52
print(f"   $150/wk = ${YR:,.0f}/yr, ${YR*30:,.0f} nominal over 30y")
for r in (0.066,0.05,0.04,0.03):
    print(f"     perpetual at {r*100:.1f}%: need ${YR/r:>11,.0f}")
for r in (0.066,0.05,0.04):
    c=YR*(1-(1+r)**-30)/r
    print(f"     30y depletion at {r*100:.1f}%: need ${c:>11,.0f}")

print("\n=== 2. WHAT CDP ACTUALLY DELIVERS (measured 6.68%, capacity-limited) ===")
for cap in (10000,25000,50000,118182):
    inc=cap*0.066
    print(f"   ${cap:>7,} -> ${inc:>7,.0f}/yr = ${inc/52:>6.2f}/wk   ({100*inc/YR:>5.1f}% of goal)")
print("   capacity ~$25k (exit liquidity) -> $31.7/wk = 21% of the goal")

print("\n=== 3. THE APS ENGINE ===")
SIG=2.365; DD=0.603
print(f"   APS vol {SIG*100:.1f}% ann, max DD {DD*100:.1f}%")
print(f"   ALL 20 APS pools combined TVL: $214,200")
print(f"   the APS/USDt0 pool: $85,163")
need=118182
for start in (25000,50000):
    m=need/start
    print(f"   ${start:,} -> ${need:,} needs {m:.1f}x = {log(m)/log(2):.1f} doublings")

print("\n=== 4. SURVIVAL OVER 30 YEARS ===")
for bar in (0.50,0.70,0.80,0.90,0.95):
    z=-log(1-bar)/SIG
    p=min(1.0,2*(0.5*erfc(z/sqrt(2))))
    print(f"   P(touch -{int(bar*100)}% at some point in 30y) = {p*100:>5.1f}%")
print("\n   and the -60.3% drawdown happened in ONE 100-day window already.")

print("\n=== 5. THE HONEST COMPARISON ===")
rows=[("Aave USDC (Base)",4.68,None),("Morpho USDC",4.4,None),
      ("Enosys CDP SP",6.68,25000),("Solana LST",4.83,None),("APS (governance)",None,None)]
print(f"   {'venue':<22}{'yield':>8}{'capacity':>12}{'income on $25k':>16}")
for n,y,c in rows:
    cap=f"${c:,}" if c else "large"
    inc=f"${25000*y/100/52:,.2f}/wk" if y else "?"
    print(f"   {n:<22}{(f'{y:.2f}%' if y else 'n/a'):>8}{cap:>12}{inc:>16}")

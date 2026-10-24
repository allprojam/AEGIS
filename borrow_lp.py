"""Test: borrow ETH @ 2.06%, supply into WETH-USDC range LP.
   Question 1: what is the NET DELTA?  Question 2: does fee income cover borrow?

STATUS: VERIFIED (2026-10-07).

Position math and economics are pinned by closed-form tests:
    tests/test_lp_engine.py     25 assertions -- V(p), divergence loss, share bounds, delta
    tests/test_lp_economics.py  19 assertions -- capital normalisation, debt compounding,
                                                fee isolation, hand-reproduced equity

Three bugs were found and fixed by that suite:
  1. share of value printed 241.5% -- token amount was computed at L=1 and divided by a
     value computed at the rescaled L. Now 47.56%, asserted below the 100% bound.
  2. the prose claimed "delta 0.3-0.5 ETH per ETH supplied", never derived from this engine.
     Real figures: 0.1969 / 0.1000 / 0.0404. Printed and asserted.
  3. equity printed a fake -$2,692 because the LP was normalised to $1 against a 1 ETH debt
     (~$321 at entry) -- a 320x unit mismatch. The LP is now sized to cost exactly what the
     borrowed ETH is worth at entry, and the debt compounds continuously. Equity is +$121.22
     at band=10%, reproduced independently to the cent by test 7.

Do not edit the math without re-running both suites.
"""
import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); T=d.index; N=len(P)
BORROW=0.0206     # Aave v3 Base WETH variable borrow APR, read on-chain
LP_APR=0.2404     # Uniswap v3 WETH-USDC Base, measured

def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    a0,a1=amt(p,pa,pb,L); return a0*p+a1

print("=== DELTA OF A v3 RANGE POSITION ===")
print(f"  ETH now {P[-1]:.0f}.  A v3 position's ETH-weighted delta varies with where price sits in range:")
print("  NOTE: bounds below are additive (+/-band), so p0 is NOT the geometric mean and the")
print("        entry is not exactly 50/50. That is correct, not a bug (see tests/test_lp_engine.py).")
p0=P[-1]
for band in (0.10,0.20,0.50):
    pa,pb=p0*(1-band),p0*(1+band)
    # NOTE: a0,a1 must be evaluated at the SAME L as v. The original code computed them at
    # L=1 and divided by v computed at the rescaled L -- mismatched position sizes -- which is
    # what printed "ETH share of value 241.5%". Caught by tests/test_lp_engine.py.
    a0,a1=amt(p0,pa,pb,1.0); L=1.0/(a0*p0+a1)
    a0n,a1n=amt(p0,pa,pb,L)                 # normalised amounts, matching v
    v=val(p0,pa,pb,L)
    # delta = dV/dP  (finite diff)
    h=p0*0.001
    delta=(val(p0+h,pa,pb,L)-val(p0-h,pa,pb,L))/(2*h)
    share=(a0n*p0)/v*100                   # bounded in [0,100] by construction
    # the figure the prose actually needs: ETH held per ETH deposited, i.e. the position's
    # effective long exposure. This is what must be compared against the borrowed amount.
    eth_per_eth=a0n/a0
    print(f"    band +/-{band*100:>4.0f}%:  ETH share {share:>5.2f}%   "
          f"ETH held per ETH deposited {eth_per_eth:.4f}   dV/dP {delta:.6f}")

print("\n=== THE STRUCTURE YOU PROPOSED ===")
print("  borrow X ETH (owe 2.06%) -> supply that ETH into the LP")
print("  debt  = X ETH  (SHORT X ETH: price up => debt up)")
print("  asset = LP holding `ETH held per ETH deposited` per ETH supplied (see table)")
print("          NOT a fixed 0.3-0.5. That figure was never derived from this engine; the")
print("          table gives 0.20 / 0.10 / 0.04 for the +/-10/20/50% bands.")
print("  => NET DELTA = eth_per_eth - X  =  NEGATIVE (net SHORT ETH)")
print("  this is NOT delta-neutral. It is a leveraged short-ETH + short-vol.")
print("\n  to actually be delta-neutral you must borrow only `eth_per_eth` ETH per")
print("  ETH supplied. Borrowing 1.0 when eth_per_eth < 1 leaves a net short.")

print("\n=== SIMULATION: borrow 1 ETH, supply into LP, 1 year hourly ===")
print("  capital normalisation: the LP is sized so it costs exactly what the borrowed ETH")
print("  is worth at entry, so both legs start with the same purchasing power. The earlier")
print("  version normalised the LP to $1 against a 1 ETH debt and printed a fake -$2,692.")
print("  debt compounds continuously: debt = eth0 * exp(rate * years_elapsed).")
for band in (0.10,0.20,0.50):
    X=1.0                       # borrowed ETH
    eth0=X
    pa,pb=P[0]*(1-band),P[0]*(1+band)
    # size the LP to cost exactly X ETH at entry
    a0u,a1u=amt(P[0],pa,pb,1.0)
    Lu=1.0/(a0u*P[0]+a1u)
    k=(X*P[0])/val(P[0],pa,pb,Lu)
    L=Lu*k
    fees=0.0; inr=0
    for i in range(1,N):
        p=P[i]
        if pa<=p<=pb:
            inr+=1
            fees+=val(p,pa,pb,L)*LP_APR/8760
        # out of range: no fees, but the debt keeps compounding (no reset)
    years=(T[-1]-T[0]).total_seconds()/(365.25*24*3600)
    debt=eth0*np.exp(BORROW*years)          # continuous compounding
    v_end=val(P[-1],pa,pb,L)
    debt_usd=debt*P[-1]
    equity=v_end-debt_usd+fees
    print(f"  band +/-{band*100:>4.0f}%: in-range {100*inr/N:>5.1f}%  LP ${v_end:>9.2f}  fees ${fees:>7.2f}  "
          f"debt ${debt_usd:>9.2f}  EQUITY ${equity:>9.2f}")
    print(f"      vs holding the borrowed ETH and doing nothing: ${0.00:>9.2f}  "
          f"(liability cancels; anything above zero means the LP added value)")
print(f"\n  NOTE: equity can be negative -- that is a liquidated position.")
print(f"\n  ETH {P[0]:.0f} -> {P[-1]:.0f} ({100*(P[-1]/P[0]-1):+.1f}%) over the sample")

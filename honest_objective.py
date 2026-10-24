import pandas as pd, numpy as np
d=pd.read_csv("bars_eth_1h_365d.csv").drop_duplicates("time").sort_values("time")
d["dt"]=pd.to_datetime(d.time,unit="s"); d=d.set_index("dt")
P=d.close.to_numpy(float); N=len(P)
lr=np.concatenate([[0.0],np.log(P[1:]/P[:-1])])
APR=0.2404; GAS=0.05
def amt(p,pa,pb,L):
    if p<=pa: return L*(1/np.sqrt(pa)-1/np.sqrt(pb)),0.0
    if p>=pb: return 0.0,L*(np.sqrt(pb)-np.sqrt(pa))
    sp=np.sqrt(p); return L*(1/sp-1/np.sqrt(pb)),L*(sp-np.sqrt(pa))
def val(p,pa,pb,L):
    e,u=amt(p,pa,pb,L); return e*p+u

print("=== CAN ANY AGENTIC POLICY BEAT 'DO NOTHING'? (walk-forward) ===")
print("  'do nothing' = static +/-10% band for the whole window")
print("  policies tested as a function of trailing vol (the one clustering signal)")
W=168
def simulate(policy, s, e, p0idx):
    win=P[s:e]
    if len(win)<200: return None
    cap=1000.0; w=0.10
    if policy=="static": pa,pb=win[0]*(1-w),win[0]*(1+w)
    else:
        v=np.std(lr[max(0,p0idx-W):p0idx])*np.sqrt(24)
        w=float(np.clip(policy*v,0.02,0.60)); pa,pb=win[0]*(1-w),win[0]*(1+w)
    a0,a1=amt(win[0],pa,pb,1.0); L=cap/(a0*win[0]+a1)
    fees=0.0; act=0; inr=0
    for i in range(1,len(win)):
        p=win[i]
        if pa<=p<=pb: inr+=1; fees+=val(p,pa,pb,L)*APR/8760
        else:
            cap=val(p,pa,pb,L); pa,pb=p*(1-w),p*(1+w)
            a0,a1=amt(p,pa,pb,1.0); L=cap/(a0*p+a1); act+=1
    end=val(win[-1],pa,pb,L) if pa<=win[-1]<=pb else cap
    return end+fees-act*GAS

blocks=[(i,min(i+1500,N)) for i in range(0,N-1500,1500)]
print(f"\n  {'block':<24}{'static':>9}{'volX1':>9}{'volX2':>9}{'volX4':>9}{'ETH':>9}")
tot={ "static":0,"1":0,"2":0,"4":0 }
for s,e in blocks:
    lbl=f"  {str(d.index[s].date())}..{str(d.index[e-1].date())}"
    vals=[]
    for pol in ("static",1.0,2.0,4.0):
        v=simulate(pol,s,e,s)
        vals.append(v if v else np.nan)
    eth=1000*P[e-1]/P[s]
    for k,v in zip(("static","1","2","4"),vals): tot[k]+=v
    print(f"{lbl:<24}{vals[0]:>9.0f}{vals[1]:>9.0f}{vals[2]:>9.0f}{vals[3]:>9.0f}{eth:>9.0f}")
print(f"\n  total over all blocks (start 1000 each): static {tot['static']:.0f}   "
      f"volX1 {tot['1']:.0f}   volX2 {tot['2']:.0f}   volX4 {tot['4']:.0f}")
print("\n  NOTE: these are independent 1500h windows, each starting at 1000.")
print("  The comparison is: does the vol-scaled policy beat static WITHIN each window?")
print(f"  blocks where vol-scaled(4) beat static:")
wins=0; tot_b=0
for s,e in blocks:
    a=simulate("static",s,e,s); b=simulate(4.0,s,e,s)
    if a and b:
        tot_b+=1; wins+= b>a
print(f"    {wins} of {tot_b}")

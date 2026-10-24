"""Engle-Granger cointegration, implemented directly (no statsmodels needed)."""
import numpy as np, pandas as pd, itertools, glob, os

def load(cur):
    d=pd.read_csv(f"fx/daily_{cur}.csv")
    d["dt"]=pd.to_datetime(d.time,unit="s").dt.normalize()
    return d.groupby("dt").close.last().rename(cur)

def ols(y,X):
    X=np.column_stack([np.ones(len(X)),X])
    b,*_=np.linalg.lstsq(X,y,rcond=None)
    e=y-X@b
    return b,e

def adf_tstat(e, lags=1):
    """ADF on residual: de = a + rho*e_{t-1} + sum phi_i de_{t-i} + u"""
    de=np.diff(e); e1=e[:-lags-1] if lags>0 else e[:-1]
    n=len(de)-lags
    Y=de[lags:]
    cols=[e1[:n]]
    for i in range(1,lags+1):
        cols.append(de[lags-i:-i][:n])
    X=np.column_stack([np.ones(n)]+cols)
    b,res=ols(Y,X)
    s2=res@res/(n-X.shape[1])
    XtX_inv=np.linalg.pinv(X.T@X)
    se=np.sqrt(s2*XtX_inv[1,1])
    return b[1]/se

print("=== ENGLE-GRANGER COINTEGRATION on FX majors (daily, full history) ===")
print("critical values (2 vars, large n): 1% -3.90 | 5% -3.34 | 10% -3.04\n")
curs=[os.path.basename(f).replace("daily_","").replace(".csv","") for f in glob.glob("fx/daily_*.csv")]
curs=sorted(curs)
data={c:load(c) for c in curs}
px=pd.DataFrame(data).dropna(how="all")
print(f"panel: {px.shape[0]:,} days x {px.shape[1]} currencies")
print(f"{'pair':<12}{'ADF t':>9}{'5%?':>7}{'half-life(d)':>14}")
res=[]
for a,b in itertools.combinations(px.columns,2):
    s=px[[a,b]].dropna()
    if len(s)<1000: continue
    ly=np.log(s[a]); lx=np.log(s[b])
    beta,resid=ols(ly.values,lx.values)
    t=adf_tstat(resid,1)
    # half-life via AR(1) on residual
    r=resid[1:]; rl=resid[:-1]
    bb,*_=np.linalg.lstsq(np.column_stack([np.ones(len(rl)),rl]),r,rcond=None)
    lam=bb[1]; hl=np.log(0.5)/np.log(abs(lam)) if 0<abs(lam)<1 else np.inf
    res.append((f"{a}/{b}",t,hl,beta))
for name,t,hl,beta in sorted(res,key=lambda x:x[1]):
    flag="YES" if t<-3.34 else ("~10%" if t<-3.04 else "no")
    print(f"  {name:<10}{t:>9.2f}{flag:>7}{hl:>14.1f}")
print("\n  (a genuine cointegrating pair should show ADF t < -3.34 AND a finite, sensible half-life)")

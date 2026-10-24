"""Engle-Granger cointegration. Fixed: the design matrix must not contain two intercepts."""
import numpy as np

def _fit(y, X):
    """OLS with an intercept. X must NOT contain a constant column."""
    Xd = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    r = y - Xd @ b
    return b, r

def adf_tstat(e, p=1):
    """de_t = a + rho*e_{t-1} + sum phi_i de_{t-i} + u ; return t on rho.
    e_{t-1} is column index 0 of X, so it is coefficient index 1 after the intercept."""
    e = np.asarray(e, float)
    d = np.diff(e)
    N = len(e); m = N - 1 - p
    Y = d[p:p+m]
    regs = [e[p:p+m]]
    for i in range(1, p+1):
        regs.append(d[p-i:p-i+m])
    X = np.column_stack(regs)                 # NO ones here
    b, r = _fit(Y, X)
    s2 = r @ r / (m - X.shape[1] - 1)         # -1 for the intercept
    se = np.sqrt(s2 * np.linalg.pinv(X.T @ X)[0, 0])
    return b[1] / se

def halflife(e):
    r, rl = e[1:], e[:-1]
    b, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(rl)), rl]), r, rcond=None)
    lam = b[1]
    return np.log(0.5)/np.log(abs(lam)) if 0 < abs(lam) < 1 else np.inf

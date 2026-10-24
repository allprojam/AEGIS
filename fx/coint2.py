"""Corrected Engle-Granger. The earlier version had an off-by-one in the lag alignment."""
import numpy as np

def ols(y, X):
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b, y - X @ b

def adf_tstat(e, p=1):
    """ADF: de_t = a + rho*e_{t-1} + sum_i phi_i de_{t-i} + u.  Returns t on rho."""
    e = np.asarray(e, float)
    d = np.diff(e)
    N = len(e)
    m = N - 1 - p
    Y = d[p:p+m]
    cols = [e[p:p+m]]                       # e_{t-1}
    for i in range(1, p+1):
        cols.append(d[p-i:p-i+m])          # de_{t-i}
    X = np.column_stack([np.ones(m)] + cols)
    b, r = ols(Y, X)
    s2 = r @ r / (m - X.shape[1])
    se = np.sqrt(s2 * np.linalg.pinv(X.T @ X)[1, 1])
    return b[1] / se

def halflife(e):
    r, rl = e[1:], e[:-1]
    X = np.column_stack([np.ones(len(rl)), rl])
    b, *_ = np.linalg.lstsq(X, r, rcond=None)
    lam = b[1]
    return np.log(0.5)/np.log(abs(lam)) if 0 < abs(lam) < 1 else np.inf

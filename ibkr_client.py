#!/usr/bin/env python3
"""Thin client for the IBKR Client Portal Gateway running on this VPS.

The gateway is a local Java REST proxy; it holds the authenticated session and forwards to
IBKR. This module never stores credentials -- authentication is done by the USER in a browser
against the gateway, which is the only way IBKR permits it.

Endpoints used (all under https://127.0.0.1:5000/v1/api):
  POST /iserver/auth/status     session state
  POST /tickle                  keep-alive (call every 60-120s; session dies if idle)
  GET  /portfolio/accounts      account list
  GET  /portfolio/{acct}/summary  NAV / cash
  GET  /trsrv/secdef?symbol=... contract lookup (-> conid)
  GET  /iserver/secdef/strikes  option strikes
  POST /iserver/reply/{id}      answer an IBKR security challenge
"""
import time
import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Prefer the Tailscale Serve HTTPS URL: it presents a REAL, publicly-trusted certificate,
# so clients need no verify=False and browsers show no warning. Falls back to the
# gateway's self-signed HTTPS if Tailscale is not up.
import os
_CANDIDATES = [
    "https://srv1619135.tailf16ee8.ts.net/v1/api",
    "https://127.0.0.1:5000/v1/api",
]
BASE = _CANDIDATES[0]
VERIFY = True
_last_tickle = 0.0


def _get(path, **kw):
    r = requests.get(f"{BASE}{path}", verify=VERIFY, timeout=20, **kw)
    return r.status_code, (r.json() if r.text.strip().startswith(("{", "[")) else r.text)


def _post(path, **kw):
    r = requests.post(f"{BASE}{path}", verify=VERIFY, timeout=20, **kw)
    return r.status_code, (r.json() if r.text.strip().startswith(("{", "[")) else r.text)


def status():
    """Session state. authenticated+connected both True means usable."""
    return _post("/iserver/auth/status")


def tickle(force=False):
    """Keep the session alive. The gateway also expires after ~24h regardless."""
    global _last_tickle
    if force or (time.time() - _last_tickle) > 90:
        _last_tickle = time.time()
        return _post("/tickle")
    return None


def accounts():
    return _get("/portfolio/accounts")


def summary(account_id):
    return _get(f"/portfolio/{account_id}/summary")


def secdef(symbol, sec_type="STK"):
    return _get(f"/trsrv/secdef?symbol={symbol}&secType={sec_type}")


def strikes(conid, sectype="OPT", month=None, exchange="SMART"):
    q = f"/iserver/secdef/strikes?conid={conid}&sectype={sectype}&exchange={exchange}"
    if month:
        q += f"&month={month}"
    return _get(q)


def orders_live():
    return _get("/iserver/account/orders")


if __name__ == "__main__":
    print("gateway health check")
    code, body = status()
    print(f"  HTTP {code}  {body}")
    if code == 401:
        print("\n  The gateway is RUNNING but NOT authenticated.")
        print("  Authenticate in a browser (one-time, per ~24h):")
        print("    https://srv1619135.tailf16ee8.ts.net   <- VALID CERT, no warning")
        print("    (or https://100.88.95.39:5000 and accept the self-signed warning)")
        print("  Accept the self-signed cert, log in, approve the IBKR Mobile push.")
        print("  Then re-run this script.")

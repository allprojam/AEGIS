#!/usr/bin/env python3
"""Order-path validation with ZERO risk: /orders/whatif previews cost & commission and
places NOTHING. This is how we test execution plumbing on a live account safely."""
import json
import requests, urllib3
import ibkr_client as ib
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
B = ib.BASE

ACCT = "U29378445"
def whatif(order):
    r = requests.post(f"{B}/iserver/account/{ACCT}/orders/whatif",
                      json={"orders": [order]}, timeout=30)
    try: return r.status_code, r.json()
    except: return r.status_code, r.text[:300]

print("=== whatif: fractional SPY buy $6 ===")
c, b = whatif({"conid": 756733, "orderType": "MKT", "side": "BUY", "quantity": 0.00775, "tif": "DAY"})
print(c, json.dumps(b)[:700] if isinstance(b,(dict,list)) else b)

print("\n=== whatif: fractional TLT buy $4 ===")
c, b = whatif({"conid": 15547841, "orderType": "MKT", "side": "BUY", "quantity": 0.052117, "tif": "DAY"})
print(c, json.dumps(b)[:700] if isinstance(b,(dict,list)) else b)

print("\n=== whatif: 1 whole share TLT (to compare whole vs fractional) ===")
c, b = whatif({"conid": 15547841, "orderType": "MKT", "side": "BUY", "quantity": 1, "tif": "DAY"})
print(c, json.dumps(b)[:700] if isinstance(b,(dict,list)) else b)

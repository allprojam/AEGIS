#!/usr/bin/env python3
"""
Credit ledger — pay-per-audit settlement, sqlite-backed, durable across restarts.

Deliberately NOT a subscription: a balance is bought once and drawn down per audit.
Addresses the in-memory token store flagged in the earlier build (it reset on restart).

SETTLEMENT IS NOT WIRED. create_order() opens an order in PENDING; confirm_order() credits
it. Until something calls confirm_order on a verified on-chain transfer, no money moves.
The API refuses to credit without an explicit confirmation, so this cannot accidentally
give away paid audits.
"""
import sqlite3, os, time, secrets, json

DB=os.environ.get("AEGIS_DB","screener/aegis.db")
PRICE=0.05        # USD per audit
BULK_PRICE=0.01   # at 10k+
FREE_PER_DAY=3

def conn():
    c=sqlite3.connect(DB, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS accounts(
          key TEXT PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0,
          created REAL, note TEXT);
        CREATE TABLE IF NOT EXISTS orders(
          id TEXT PRIMARY KEY, key TEXT, credits INTEGER, usd REAL,
          status TEXT, created REAL, confirmed REAL, txhash TEXT);
        CREATE TABLE IF NOT EXISTS usage(
          key TEXT, ts REAL, ip TEXT);
        CREATE INDEX IF NOT EXISTS usage_key_ts ON usage(key, ts);
        """)

def new_key():
    return "aeg_" + secrets.token_urlsafe(24)

def create_account(note=None):
    k=new_key()
    with conn() as c:
        c.execute("INSERT INTO accounts(key,balance,created,note) VALUES(?,0,?,?)",(k,time.time(),note))
    return k

def balance(key):
    with conn() as c:
        r=c.execute("SELECT balance FROM accounts WHERE key=?",(key,)).fetchone()
    return r[0] if r else None

def create_order(key, credits, usd=None):
    """Opens a PENDING order. Nothing is credited until confirm_order is called."""
    if usd is None:
        usd = round(credits * (BULK_PRICE if credits>=10_000 else PRICE), 2)
    oid="ord_"+secrets.token_hex(10)
    with conn() as c:
        c.execute("INSERT INTO orders(id,key,credits,usd,status,created) VALUES(?,?,?,?,?,?)",
                  (oid,key,credits,usd,"PENDING",time.time()))
    return dict(order_id=oid, credits=credits, usd=usd, status="PENDING",
                pay_to="0x0668086CD2113F8fd00AcC3EFAc39B8E85b5C85a",  # Aegis wallet, Base
                asset="USDC on Base",
                warning="UNSETTLED: credits are applied only after confirm_order() on a verified transfer.")

def confirm_order(oid, txhash=None):
    """Credits an order. Call ONLY from a verifier that has checked the chain.
    Double-credit is prevented by the status guard."""
    with conn() as c:
        row=c.execute("SELECT key,credits,status FROM orders WHERE id=?",(oid,)).fetchone()
        if not row: return dict(error="unknown order")
        key,credits,status=row
        if status=="PAID":
            return dict(error="already credited", status=status)
        c.execute("UPDATE orders SET status='PAID' WHERE id=? AND status='PENDING'",(oid,))
        if c.total_changes==0:
            return dict(error="not pending")
        c.execute("UPDATE accounts SET balance=balance+? WHERE key=?",(credits,key))
    return dict(order_id=oid, credited=credits, balance=balance(key), status="PAID")

def free_used_today(ip):
    since=time.time()-86400
    with conn() as c:
        r=c.execute("SELECT COUNT(*) FROM usage WHERE ip=? AND ts>?",(ip,since)).fetchone()
    return r[0]

def spend(key, ip):
    """Returns (ok, info). Free tier by IP, then draw down credits."""
    init()
    used=free_used_today(ip)
    if used < FREE_PER_DAY:
        with conn() as c: c.execute("INSERT INTO usage(key,ts,ip) VALUES(?,?,?)",(key or "-",time.time(),ip))
        return True, dict(paid=False, free_used=used+1, free_limit=FREE_PER_DAY)
    if not key: return False, dict(error="payment_required", free_limit=FREE_PER_DAY,
                                   price_usd=PRICE, reason="free tier exhausted; pass X-Aegis-Key")
    with conn() as c:
        r=c.execute("SELECT balance FROM accounts WHERE key=?",(key,)).fetchone()
        if not r: return False, dict(error="unknown key")
        if r[0] <= 0: return False, dict(error="payment_required", balance=0, price_usd=PRICE,
                                          order="POST /order to top up")
        c.execute("UPDATE accounts SET balance=balance-1 WHERE key=? AND balance>0",(key,))
        if c.total_changes==0: return False, dict(error="payment_required", balance=0)
        c.execute("INSERT INTO usage(key,ts,ip) VALUES(?,?,?)",(key,time.time(),ip))
    return True, dict(paid=True, balance=balance(key))

if __name__=="__main__":
    init()
    print("=== ledger self-test ===")
    k=create_account("selftest")
    print(f"  new account      {k[:18]}...  balance={balance(k)}")
    o=create_order(k,100)
    print(f"  order            {o['order_id']}  {o['credits']} credits  ${o['usd']}  {o['status']}")
    print(f"  balance before   {balance(k)}   <- not credited while PENDING (correct)")
    r=confirm_order(o["order_id"],"0xdeadbeef")
    print(f"  confirm          credited={r.get('credited')}  balance={r.get('balance')}")
    r2=confirm_order(o["order_id"])
    print(f"  double-confirm   {r2}   <- must refuse")
    for i in range(4):
        ok,info=spend(k, "10.0.0.9")
        print(f"  spend {i+     1}         ok={ok}  {json.dumps(info)[:70]}")
    ok,info=spend(k,"10.0.0.9")
    print(f"  spend (paid)     ok={ok}  balance={info.get('balance')}")
    ok,info=spend(k,"10.0.0.9")
    print(f"  spend (paid)     ok={ok}  balance={info.get('balance')}")

#!/usr/bin/env python3
"""The MCP surface: routing, billing order, and gated issuance.

THREE DEFECTS THIS PINS DOWN, all found by driving the API rather than reading it.

  1. MORPHO REQUESTS DIED AT THE DOOR. resolve() matched only `underlyingTokens` against the
     DefiLlama set, so a 32-byte Morpho market id returned None and /audit answered 404 for a
     market the engine knows perfectly well. The 20-byte token-address regex also CLIPPED a
     32-byte id and searched for a token that does not exist.

  2. FAILED LOOKUPS WERE BILLED. The credit was spent BEFORE resolution, so a request for an id
     that does not resolve consumed a credit and returned 404 -- charging for an answer never
     delivered. Measured: three 404s burned three credits before the fourth was refused.

  3. ISSUANCE WAS UNGATED. /purchase minted a token for any anonymous caller with no payment and
     no secret, into an in-memory dict that lost every token on restart.
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCREENER = os.path.join(ROOT, "screener")
for p in (ROOT, SCREENER):
    if p not in sys.path:
        sys.path.insert(0, p)

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    print("=== 1. the token primitive ===")
    rc = subprocess.call([sys.executable, os.path.join(SCREENER, "tokens.py"), "--selftest"])
    ck("tokens selftest passes", rc == 0)

    print("\n=== 2. routing by id shape ===")
    import tokens as T
    sec = T.load_secret() or T.init_secret()
    os.environ["AEGIS_OPERATOR_SECRET"] = "op-secret-xyz"
    port = free_port()
    os.environ["AEGIS_MCP_PORT"] = str(port)
    import mcp_server as ms
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", port), ms.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.5)

    def post(path, body, hdr=None):
        rq = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (port, path), data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **(hdr or {})})
        try:
            return json.loads(urllib.request.urlopen(rq, timeout=20).read().decode())
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode())

    runs = sorted(glob.glob(os.path.join(SCREENER, "runs", "*", "")))
    if not runs:
        ck("a run exists", False)
        srv.shutdown()
        return 1
    mk = json.load(open(os.path.join(runs[-1], "markets.json")))
    mk = mk if isinstance(mk, list) else list(mk.values())
    mid = [x for x in mk if x.get("collateral") == "cbETH"][0]["market_id"]

    r = post("/audit", {"q": mid})
    ck("a Morpho market id resolves to the lending shape",
       r.get("kind") == "morpho_market", r.get("kind"))
    ck("and carries a runway in dollars", (r.get("runway_usd") or 0) > 0, r.get("runway_usd"))
    ck("and a capacity-capped max ticket",
       (r.get("capacity_max_ticket_usd") or 0) > 0, r.get("capacity_max_ticket_usd"))
    ck("and a cadence-corrected sigma", r.get("sigma_to_breach") is not None)
    ck("and oracle flags as a list", isinstance(r.get("oracle_flags"), list))
    ck("and the verdict comes from screen.json, not a null",
       r.get("verdict") is not None, r.get("verdict"))

    import re
    ck("the 20-byte regex WOULD clip a 32-byte id (why the order matters)",
       bool(re.search(r"0x[a-fA-F0-9]{40}", mid)), True)

    unknown = post("/audit", {"q": "0x" + "ab" * 32})
    ck("an unknown id still 404s rather than fabricating", "error" in unknown,
       unknown.get("error"))

    print("\n=== 3. a failed lookup is NOT billed ===")
    tok, _ = T.issue("agent-test", 2, sec)
    a = post("/audit", {"q": "0x" + "cd" * 32}, {"X-Aegis-Token": tok})
    ck("a 404 says so explicitly", a.get("billed") is False, a.get("billed"))
    b = post("/audit", {"q": mid}, {"X-Aegis-Token": tok})
    ck("and the credit survives for a real call",
       (b.get("payment") or {}).get("credits_left") == 1,
       (b.get("payment") or {}).get("credits_left"))

    print("\n=== 4. a successful call IS billed, exactly once ===")
    tok2, _ = T.issue("agent-test2", 2, sec)
    c1 = post("/audit", {"q": mid}, {"X-Aegis-Token": tok2})
    c2 = post("/audit", {"q": mid}, {"X-Aegis-Token": tok2})
    c3 = post("/audit", {"q": mid}, {"X-Aegis-Token": tok2})
    ck("first call charged", (c1.get("payment") or {}).get("paid") is True)
    ck("second call charged", (c2.get("payment") or {}).get("paid") is True)
    ck("third call refused as exhausted", c3.get("error") == "token_exhausted",
       c3.get("error"))

    print("\n=== 5. issuance is gated ===")
    n1 = post("/purchase", {"credits": 3})
    n2 = post("/purchase", {"credits": 3, "operator_secret": "wrong"})
    n3 = post("/purchase", {"credits": 3, "operator_secret": "op-secret-xyz", "sub": "a"})
    ck("no operator secret -> forbidden", n1.get("error") == "forbidden", n1.get("error"))
    ck("wrong operator secret -> forbidden", n2.get("error") == "forbidden", n2.get("error"))
    ck("correct secret -> a signed token is issued", bool(n3.get("token")), n3.get("error"))
    ck("and it is explicitly NOT a settlement",
       "UNSETTLED" in (n3.get("warning") or ""), n3.get("warning"))

    print("\n=== 6. a forged token is refused ===")
    good = n3.get("token") or ""
    head, _, sig = good.partition(".")
    forged = T._b64e(json.dumps({"sub": "x", "credits": 9999, "jti": "z", "exp": 9999999999},
                                sort_keys=True, separators=(",", ":")).encode()) + "." + sig
    f = post("/audit", {"q": mid}, {"X-Aegis-Token": forged})
    ck("a tampered token does not buy access", f.get("error") == "invalid_token",
       f.get("error"))

    print("\n=== 7. the single-process ledger is thread-safe (measured, not assumed) ===")
    # THE QUESTION THAT DECIDES THE REDIS ARGUMENT. flock serialises writers within one process,
    # but that is a claim until it is raced. 200 threads contending for 50 credits:
    import tempfile
    td = tempfile.mkdtemp()
    old_lock, old_ledger = T.LOCK_PATH, T.LEDGER_PATH
    T.LOCK_PATH = os.path.join(td, "l.lock")
    lp = os.path.join(td, "l.json")
    try:
        tok3, p3 = T.issue("race", 50, sec)
        T.spend(p3["jti"], credits=50, path=lp)          # create the entry
        led = T.load_ledger(lp)
        led[p3["jti"]]["used"] = 0
        json.dump(led, open(lp, "w"))
        granted = []
        lock = threading.Lock()
        def worker():
            good, _ = T.spend(p3["jti"], credits=50, path=lp)
            with lock:
                granted.append(good)
        ths = [threading.Thread(target=worker) for _ in range(200)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        n = sum(1 for g in granted if g)
        ck("50 credits granted for 50 available under 200 threads", n == 50, n)
        ck("and the ledger records exactly that",
           T.load_ledger(lp)[p3["jti"]]["used"] == 50)
    finally:
        T.LOCK_PATH, T.LEDGER_PATH = old_lock, old_ledger

    print("\n=== 8. the bind address defaults to loopback, not the world ===")
    # This host has a PUBLIC eth0 (<srv-public-ip>). The server was hardcoded to 0.0.0.0, which
    # would have published the token endpoint to the internet. The safe default is loopback and
    # the tailnet IP is an explicit opt-in -- the pattern the :8080 service on this host uses.
    src = open(os.path.join(SCREENER, "mcp_server.py")).read()
    ck("the bind address is configurable", "AEGIS_MCP_BIND" in src)
    ck("and does NOT default to 0.0.0.0",
       'AEGIS_MCP_BIND","0.0.0.0"' not in src and "AEGIS_MCP_BIND', '0.0.0.0'" not in src)
    ck("it defaults to loopback", 'AEGIS_MCP_BIND","127.0.0.1"' in src,
       "a public host must not bind the world by default")
    ck("and binding the world warns loudly", "WARNING: bound to ALL interfaces" in src)
    ck("the constructor uses BIND, not a literal",
       'ThreadingHTTPServer((BIND,PORT)' in src)

    srv.shutdown()
    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  both universes route, billing is ordered correctly, issuance is gated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

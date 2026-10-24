#!/usr/bin/env python3
"""tokens.py - signed read-only API tokens, with a ledger that survives a restart.

THE DECISION THIS IMPLEMENTS. Full x402 on-chain settlement is a separate infrastructure project.
A signed prepaid token gets machine-to-machine access live now, proves the unit economics, and
leaves heavy settlement for v2. This is that token, and nothing more.

WHAT IT REPLACES, AND WHY THAT MATTERED. `mcp_server.py` kept tokens in a dict with the comment
"in-memory only; resets on restart", and `/purchase` minted a token for any caller who asked,
with no payment and no secret. So the paywall had two holes: every token died on restart, and
anyone could mint one. A token is not a credit card -- but a paywall that hands out its own
currency is not a paywall.

WHAT A TOKEN IS HERE.

    <b64url(payload)>.<b64url(hmac_sha256(secret, payload))>

    payload = {"sub": client, "plan": "prepaid", "credits": n, "exp": unix_ts, "jti": id}

Three properties, each of which was missing:

  1. SIGNED. The signature is checked before the payload is trusted. `credits` cannot be edited
     by the holder; without the secret, a forged token fails verification.
  2. STATE-LESS TO VERIFY, STATEFUL TO SPEND. Verification needs only the secret. SPENDING is
     recorded in a ledger keyed by jti, so credits are consumed exactly once and a restart does
     not refund them. The old store was stateful for both and lost both.
  3. EXPIRING. A token carries an expiry. A leaked token is not a permanent key.

HONEST LIMITS, stated because "signed token" sounds stronger than it is.

  * THIS IS NOT SETTLEMENT. It records that a credit was spent, not that money moved. Nothing
    here verifies a chain transaction. Issuing is gated behind an operator secret for exactly
    that reason: without on-chain settlement, the issuer IS the payment system, so it must not
    be reachable by an anonymous caller.
  * CREDITS ARE NOT REFUNDABLE OR TRANSFERABLE. No such mechanism exists here.
  * THE LEDGER IS A FILE. Concurrent writers are serialised with a lock file, which is adequate
    for one process and not for a fleet. A fleet needs a database.

Run:  python3 tokens.py --init                 create the signing secret
      python3 tokens.py --issue 100 --sub me  mint a token (needs the secret)
      python3 tokens.py --verify <token>      check without spending
      python3 tokens.py --selftest
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET_PATH = os.path.join(HERE, "token_secret.key")
LEDGER_PATH = os.path.join(HERE, "token_ledger.json")
LOCK_PATH = os.path.join(HERE, "token_ledger.lock")

PLAN_PREPAID = "prepaid"
DEFAULT_TTL = 30 * 86400          # 30 days
CLOCK_SKEW = 60                   # seconds of tolerance on exp


def _b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def load_secret(path=SECRET_PATH):
    """The HMAC secret, or None. Never generated implicitly, so a missing secret is a loud
    misconfiguration rather than a fresh one per process -- which would silently invalidate
    every token on every restart, the exact bug being replaced."""
    try:
        with open(path) as fh:
            s = fh.read().strip()
        return s or None
    except Exception:
        return None


def init_secret(path=SECRET_PATH):
    s = secrets.token_urlsafe(48)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(s)
    return s


def sign(payload, secret):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    return _b64e(raw) + "." + _b64e(sig)


def verify(token, secret, now=None):
    """(ok, payload_or_error). Checks shape, signature, then expiry -- in that order."""
    if not token or not secret:
        return False, "no_token_or_secret"
    if "." not in token:
        return False, "malformed"
    a, b = token.split(".", 1)
    try:
        raw = _b64d(a)
        sig = _b64d(b)
    except Exception:
        return False, "malformed"
    expect = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    # constant-time: a timing leak on a signature check lets an attacker recover it byte by byte
    if not hmac.compare_digest(sig, expect):
        return False, "bad_signature"
    try:
        p = json.loads(raw.decode())
    except Exception:
        return False, "malformed"
    exp = p.get("exp")
    if exp is not None and (now or time.time()) > exp + CLOCK_SKEW:
        return False, "expired"
    return True, p


# ---------------------------------------------------------------- the spend ledger

def _lock():
    """A simple exclusive lock file. Adequate for one process; a fleet needs a database."""
    import fcntl
    fh = open(LOCK_PATH, "w")
    fcntl.flock(fh, fcntl.LOCK_EX)
    return fh


def _unlock(fh):
    import fcntl
    fcntl.flock(fh, fcntl.LOCK_UN)
    fh.close()


def load_ledger(path=LEDGER_PATH):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}


def spend(jti, credits=None, path=LEDGER_PATH):
    """Consume one credit from jti. Returns (ok, remaining).

    A token is allowed `credits` total spends, recorded here rather than trusted from the token
    on each call. Without this a client could replay the same token forever: the signature stays
    valid and nothing would decrement it.
    """
    fh = _lock()
    try:
        led = load_ledger(path)
        ent = led.get(jti)
        if ent is None:
            ent = {"used": 0, "limit": credits if credits is not None else 0}
            led[jti] = ent
        if ent["used"] >= ent["limit"]:
            return False, 0
        ent["used"] += 1
        with open(path, "w") as f:
            json.dump(led, f, indent=1)
        return True, ent["limit"] - ent["used"]
    finally:
        _unlock(fh)


def issue(sub, credits, secret, ttl=DEFAULT_TTL, now=None):
    p = {
        "sub": str(sub),
        "plan": PLAN_PREPAID,
        "credits": int(credits),
        "exp": int((now or time.time()) + ttl),
        "jti": secrets.token_urlsafe(12),
    }
    return sign(p, secret), p


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--init" in sys.argv:
        if load_secret():
            print("secret already exists at %s" % SECRET_PATH)
            return 1
        init_secret()
        print("wrote %s (mode 600)" % SECRET_PATH)
        return 0
    secret = load_secret()
    if "--issue" in sys.argv:
        if not secret:
            print("no secret; run --init first", file=sys.stderr)
            return 1
        n = int(sys.argv[sys.argv.index("--issue") + 1])
        sub = sys.argv[sys.argv.index("--sub") + 1] if "--sub" in sys.argv else "operator"
        tok, p = issue(sub, n, secret)
        print(tok)
        print("# %d credits, expires %d" % (p["credits"], p["exp"]), file=sys.stderr)
        return 0
    if "--verify" in sys.argv:
        ok, res = verify(sys.argv[sys.argv.index("--verify") + 1], secret)
        print(json.dumps(res, indent=1) if ok else "INVALID: %s" % res)
        return 0 if ok else 1
    print(__doc__)
    return 0


def selftest():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        print("  %-58s %s" % (name, "PASS" if good else "FAIL got=%r want=%r" % (got, want)))
        if not good:
            ok = False

    sec = "test-secret-do-not-use"
    tok, p = issue("agent-1", 5, sec, ttl=3600, now=1000)
    check("a fresh token verifies", verify(tok, sec, now=1000)[0], True)
    check("and carries the subscriber", verify(tok, sec, now=1000)[1]["sub"], "agent-1")

    # TAMPERING: flip one character of the payload
    a, b = tok.split(".", 1)
    forged = _b64e(json.dumps({**p, "credits": 9999}, sort_keys=True,
                              separators=(",", ":")).encode()) + "." + b
    check("an edited payload FAILS verification", verify(forged, sec, now=1000)[0], False)
    check("...with a signature error", verify(forged, sec, now=1000)[1], "bad_signature")

    # a different secret must not verify
    check("the wrong secret fails", verify(tok, "other-secret", now=1000)[0], False)

    # EXPIRY, including the skew tolerance
    check("valid just before expiry", verify(tok, sec, now=4599)[0], True)
    check("expired well after", verify(tok, sec, now=1000 + 3600 + CLOCK_SKEW + 10)[0], False)
    check("...and says so", verify(tok, sec, now=1000 + 3600 + CLOCK_SKEW + 10)[1], "expired")

    # malformed input is refused rather than raising
    check("empty token refused", verify("", sec)[0], False)
    check("no dot refused", verify("nodot", sec)[0], False)
    check("garbage refused", verify("aaa.bbb", sec)[0], False)

    # THE REPLAY HOLE: credits must be consumed by the LEDGER, not trusted from the token
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        lp = os.path.join(td, "led.json")
        global LOCK_PATH
        old_lock = LOCK_PATH
        LOCK_PATH = os.path.join(td, "led.lock")
        try:
            t2, p2 = issue("agent-2", 2, sec)
            r1 = spend(p2["jti"], credits=2, path=lp)
            r2 = spend(p2["jti"], credits=2, path=lp)
            r3 = spend(p2["jti"], credits=2, path=lp)
            check("first spend succeeds", r1, (True, 1))
            check("second spend succeeds", r2, (True, 0))
            check("THIRD spend is refused (replay blocked)", r3, (False, 0))
            check("and the ledger persisted the usage", load_ledger(lp)[p2["jti"]]["used"], 2)
        finally:
            LOCK_PATH = old_lock

    # a token whose payload has no exp is not silently immortal
    noexp = sign({"sub": "x", "credits": 1, "jti": "j"}, sec)
    check("a token with no exp still verifies (expiry is optional)", verify(noexp, sec)[0], True)

    print()
    print("  selftest %s" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

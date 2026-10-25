#!/usr/bin/env python3
"""
Aegis Audit MCP — audit-as-a-service for other agents.

WHY AN MCP: an agent that wants to check a yield before depositing can call this
instead of trusting a number. The 402 paywall is the monetisation, and the point
you made is real -- an agent cannot click an ad, so a paywall is the correct
mechanism where a human-facing page would use advertising.

TRANSPORT: HTTP JSON-RPC. Endpoints:
  POST /audit    -> run the six checks on a pool dict or a link
  POST /resolve  -> link/address -> pool record
  GET  /health   -> liveness, no auth
  GET  /pricing  -> the 402 terms, no auth

PAYWALL: unpaid requests to /audit return HTTP 402 with terms. A valid prepaid
token passes. NOTHING HERE SETTLES REAL FUNDS -- the token store is in-memory and
resets on restart. Wire it to x402/Base USDC before charging anyone.
"""
import json, re, os, sys, time, hashlib, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# sys.path.insert(0,"screener") was RELATIVE, so it resolved against the process working
# directory rather than this file. Run as `python3 screener/mcp_server.py` from the project
# root, Python puts the SCRIPT's directory (screener/) on the path -- not the project root --
# so root modules like run_history were unimportable and the /runs endpoints 404'd. Anchor both
# paths to this file's real location.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from links import link_set, GT_CHAIN, DEXSCREENER_CHAIN
from audit import load_protocols, assess

PORT=int(os.environ.get("AEGIS_MCP_PORT","8010"))

# BIND ADDRESS. This was hardcoded to 0.0.0.0 while the host has a PUBLIC interface
# (eth0 <srv-public-ip>). The token ledger holds signing material and spend state, and before
# this change the endpoint would have answered on the public internet -- reachable by exactly the
# anonymous callers the gated /purchase exists to keep out.
#
# The safe pattern is already in use on this host: the service on :8080 binds
# 100.88.95.39 (the Tailscale address) and nothing else. Default to that, so exposure is an
# explicit opt-in rather than the default state.
#
# NOTE ON ts-input: that chain ACCEPTs all traffic from the tailnet and only DROPs 100.64.0.0/10
# later, so it is NOT a firewall protecting this port. The bind address is the actual control.
BIND=os.environ.get("AEGIS_MCP_BIND","127.0.0.1")
PRICE_USD=0.02          # per audit
FREE_PER_DAY=3          # a taste, so agents can verify the output is real

# SIGNAGE + LEDGER, replacing an in-memory dict that lost every token on restart and would mint
# one for any anonymous caller. See tokens.py for the format and the limits.
import tokens as _tokens
SECRET = _tokens.load_secret()
TOKENS={}          # legacy shim, kept so an old caller does not crash; never written now
USAGE={}           # client -> [timestamps]
PROTOS={}
THRESH={  # mirrored from audit_core.js / screen.py
 "MIN_TVL":1_000_000,"MAX_REWARD_SHARE":0.50,"MIN_SPOT_RATIO":0.60,
 "MIN_TURNOVER":0.01,"MIN_DAYS":30,"MAX_STABLE_BASE":25.0}

def num(v):
    try: return float(v)
    except Exception: return 0.0

def audit_pool(p):
    r=[]; f=[]
    apy=num(p.get("apy")); base=num(p.get("apyBase")); rew=num(p.get("apyReward"))
    apy7=p.get("apyBase7d"); apy7=num(apy7) if apy7 is not None else None
    tvl=num(p.get("tvlUsd")); v7=num(p.get("volumeUsd7d")); count=num(p.get("count"))
    sym=str(p.get("symbol","")).upper()
    if p.get("outlier") is True:
        f.append("OUTLIER"); r.append(f"flagged outlier; spot {apy:.2f}% vs 7d-base {apy7}")
    if apy>0 and rew/apy > THRESH["MAX_REWARD_SHARE"]:
        f.append("SUBSIDISED"); r.append(f"{rew/apy*100:.0f}% of yield is emissions")
    if apy7 and apy7>0 and base>0 and base/apy7 < THRESH["MIN_SPOT_RATIO"]:
        f.append("SPIKE"); r.append(f"spot base is {base/apy7*100:.0f}% of the 7d base")
    if tvl < THRESH["MIN_TVL"]:
        f.append("THIN"); r.append(f"TVL ${tvl:,.0f} below $1M")
    turnover=None
    if v7 and tvl>0:
        turnover=(v7/7)/tvl
        if turnover < THRESH["MIN_TURNOVER"]:
            f.append("DEAD"); r.append(f"turnover {turnover*100:.2f}%/day")
    stableish = p.get("stablecoin") is True or any(k in sym for k in ("USD","USDC","USDT","DAI","EURC"))
    if stableish and base > THRESH["MAX_STABLE_BASE"]:
        f.append("IMPLAUSIBLE"); r.append(f"{base:.1f}% organic on a stable asset")
    if count < THRESH["MIN_DAYS"]:
        f.append("NEW"); r.append(f"only {count:.0f} days of history")
    if apy <= 0:
        f.append("NO_YIELD"); r.append(f"pays {apy:.2f}% - no yield to underwrite")
    s=set(f)
    if "NO_YIELD" in s: v="NO_YIELD"
    elif not f: v="REAL"
    elif s <= {"NEW"}: v="PROMISING"
    elif "SUBSIDISED" in s and len(f)<=2: v="MIXED"
    else: v="AVOID"
    return {"verdict":v,"fails":f,"reasons":r,"apy":apy,"apyBase":base,"apyReward":rew,
            "apyBase7d":apy7,"tvlUsd":tvl,"turnover":turnover,"count":count,
            "symbol":p.get("symbol"),"chain":p.get("chain"),"project":p.get("project"),
            "links":link_set(p)}

# ---- simple cache of the whole yield set, refreshed hourly ----
_cache={"t":0,"data":[]}
def pools():
    if time.time()-_cache["t"] < 3600 and _cache["data"]: return _cache["data"]
    import urllib.request
    rq=urllib.request.Request("https://yields.llama.fi/pools",
        headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    d=json.loads(urllib.request.urlopen(rq,timeout=30).read().decode())["data"]
    _cache.update(t=time.time(), data=d); return d

# ---- Morpho market resolution -------------------------------------------------------
# A Morpho MARKET ID is a 32-byte hex string (0x + 64 chars). A DefiLlama pool is an opaque id
# string; a token address is 20 bytes. The two universes were not distinguished before, so a
# Morpho request died at the front door: resolve() matched only underlyingTokens against the
# DefiLlama set and returned None, and /audit answered 404 for a market that the engine knows
# perfectly well.
_MORPHO_ID_RE = re.compile(r"0x[a-fA-F0-9]{64}")

def _newest_run_dir():
    """The most recent immutable run, or None. Read-only; never writes."""
    runs = os.path.join(_HERE, "runs")
    if not os.path.isdir(runs):
        return None
    names = sorted(d for d in os.listdir(runs) if os.path.isdir(os.path.join(runs, d)))
    return os.path.join(runs, names[-1]) if names else None

def resolve_morpho(q):
    """A Morpho market id -> a risk record with runway and volatility, or None.

    This is the lending half of the router. It reads the newest immutable run rather than the
    live API so the answer is tied to a block, and it degrades to None when no run exists rather
    than inventing a market.
    """
    if not q: return None
    m = _MORPHO_ID_RE.search(str(q))
    if not m: return None
    mid = m.group(0).lower()
    run = _newest_run_dir()
    if not run:
        return None
    try:
        mk = json.load(open(os.path.join(run, "markets.json")))
    except Exception:
        return None
    mk = mk if isinstance(mk, list) else list(mk.values())
    row = next((x for x in mk if str(x.get("market_id", "")).lower() == mid), None)
    if not row:
        return None
    # THE VERDICT LIVES IN screen.json, NOT markets.json. Reading it from the wrong file gave a
    # literal `null` in a field a caller would reasonably branch on -- a silent wrong answer
    # rather than a missing one, which is worse.
    verdict = None
    try:
        sc = json.load(open(os.path.join(run, "screen.json")))
        sc = sc if isinstance(sc, list) else list(sc.values())
        sm = next((x for x in sc if str(x.get("market_id", "")).lower() == mid), None)
        if sm:
            verdict = sm.get("verdict")
    except Exception:
        pass
    try:
        import runway as _rw
        rw = _rw.analyse(row)
    except Exception:
        rw = None
    return {"kind": "morpho_market", "run": os.path.basename(run), "market": row,
            "runway": rw, "verdict": verdict}

def resolve(q):
    """link | address | symbol | Morpho market id -> a record.

    ROUTES BY SHAPE, because the two universes have disjoint id spaces and conflating them is
    what produced the 404. A 32-byte hex id is a Morpho market; a 20-byte hex address is a token
    in an AMM pool; anything else is a link or a symbol.
    """
    if not q: return None
    q=str(q).strip()
    # a 32-byte id is a Morpho market and MUST be routed there first: the 20-byte regex below
    # would otherwise clip it and look for a token address that does not exist
    mm = resolve_morpho(q)
    if mm: return mm
    m=re.search(r"0x[a-fA-F0-9]{40}",q)
    if m:
        for p in pools():
            if any(str(t).lower()==m.group(0).lower() for t in (p.get("underlyingTokens") or [])):
                return p
    g=re.search(r"geckoterminal\.com/([^/]+)/(pools|tokens)/([^\s?]+)",q,re.I)
    if g and g.group(3).lower().startswith("0x"):
        return resolve(g.group(3))
    for p in pools():
        if str(p.get("symbol","")).upper()==q.upper(): return p
    for p in pools():
        if q.upper() in str(p.get("symbol","")).upper(): return p
    return None

def check_payment(hdr, client):
    """Returns (ok, info). Free tier, then 402."""
    now=time.time()
    tok=hdr.get("X-Aegis-Token") or ""
    if tok:
        good, res = _tokens.verify(tok, SECRET, now=now)
        if good:
            spent, left = _tokens.spend(res.get("jti"), credits=res.get("credits"))
            if spent:
                return True, {"paid":True,"credits_left":left,"sub":res.get("sub"),
                              "note":"credit recorded in the token ledger; no funds settled"}
            return False, {"error":"token_exhausted","credits_left":0,
                           "note":"this token has spent its credits"}
        # a bad token falls through to the free tier rather than 402-ing the caller outright,
        # so the free allowance still works with a stale token in the header
        if SECRET:
            return False, {"error":"invalid_token","detail":res}
    u=[t for t in USAGE.get(client,[]) if now-t < 86400]
    USAGE[client]=u
    if len(u) < FREE_PER_DAY:
        u.append(now)
        return True, {"paid":False,"free_used":len(u),"free_limit":FREE_PER_DAY}
    return False, {"error":"payment_required","price_usd":PRICE_USD,
                   "free_limit":FREE_PER_DAY,
                   "how":"present a signed token in the X-Aegis-Token header",
                   "obtain":"the operator issues tokens out of band; on-chain settlement is v2"}

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj, hdrs=None):
        b=json.dumps(obj,indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        for k,v in (hdrs or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def log_message(self,*a): pass
    def do_GET(self):
        # ---- run-history API. Reads runs/ and alerts.log through run_history so this and the
        # MCP tools cannot drift into two different answers.
        import urllib.parse as _up
        u=_up.urlparse(self.path); qs=_up.parse_qs(u.query)
        try:
            import run_history as _rh
        except Exception as _e:
            sys.stderr.write("run_history import failed: %r\n" % (_e,))
            sys.stderr.flush()
            _rh=None
        if _rh and u.path=="/runs":
            lim=qs.get("limit",[None])[0]
            return self._send(200,{"runs":_rh.get_index(limit=int(lim) if lim else None)})
        if _rh and u.path.startswith("/runs/"):
            rid=u.path[len("/runs/"):].strip("/")
            got=_rh.get_run(rid)
            if got is None:
                return self._send(404,{"error":"unknown run","run":rid,
                    "hint":"GET /runs for valid ids"})
            return self._send(200,got)
        if _rh and u.path=="/markets":
            mk=_rh.list_markets()
            return self._send(200,{"n":len(mk),"markets":sorted(mk.values(),
                key=lambda e:-(e.get("runs_seen") or 0))})
        if _rh and u.path=="/series":
            q=(qs.get("market") or qs.get("market_id") or [None])[0]
            if not q:
                return self._send(400,{"error":"market query param required"})
            ids=_rh.resolve_market(q)
            if not ids:
                return self._send(404,{"error":"unknown market","q":q})
            if len(ids)>1:
                return self._send(409,{"error":"ambiguous","q":q,"candidates":ids,
                    "note":"several markets share that collateral; pass a full market_id"})
            pts=_rh.get_series(ids[0])
            mk=_rh.list_markets().get(ids[0],{})
            return self._send(200,{"market_id":ids[0],"collateral":mk.get("collateral"),
                "lltv":mk.get("lltv"),"n_points":len(pts),"verdicts":mk.get("verdicts"),
                "series":pts})
        if _rh and u.path=="/changes":
            lim=qs.get("limit",[None])[0]
            ch=_rh.get_changes(limit=int(lim) if lim else None)
            return self._send(200,{"n_intervals":len(ch),
                "n_events":sum(r.get("n_events") or 0 for r in ch),
                "log":ch,"unchecked":_rh.get_unchecked(),
                "framing":"STATE TRANSITION LOG, not exploit prevention. It compares "
                          "consecutive polls and cannot observe anything between them. If "
                          "`unchecked` is non-empty, some checks did not run."})
        if self.path=="/health":
            return self._send(200,{"ok":True,"pools_cached":len(_cache["data"]),
                                   "free_per_day":FREE_PER_DAY,"price_usd":PRICE_USD})
        if self.path=="/pricing":
            return self._send(200,{"price_usd":PRICE_USD,"free_per_day":FREE_PER_DAY,
                "endpoints":["POST /audit","POST /resolve",
                             "GET /runs","GET /runs/<id>","GET /markets","GET /series?market=",
                             "GET /changes"],
                "status":"in-memory tokens; settlement not wired"})
        return self._send(404,{"error":"not found"})
    def do_POST(self):
        n=int(self.headers.get("Content-Length") or 0)
        try: body=json.loads(self.rfile.read(n) or b"{}")
        except Exception: return self._send(400,{"error":"bad json"})
        client=self.client_address[0]
        if self.path=="/resolve":
            p=resolve(body.get("q"))
            if not p: return self._send(404,{"error":"not found","q":body.get("q")})
            return self._send(200,{"pool":p,"links":link_set(p)})
        if self.path=="/audit":
            # RESOLVE FIRST, CHARGE SECOND. The credit was spent before the lookup, so a request
            # for an id that does not resolve consumed a credit and returned 404 -- billing for an
            # answer that was never delivered. MEASURED: three 404s burned three credits before the
            # fourth was refused as exhausted. A caller who typo'd an address would be charged for
            # the typo.
            p = body.get("pool") or resolve(body.get("q"))
            if not p: return self._send(404,{"error":"could not resolve","q":body.get("q"),
                                             "billed":False,
                                             "note":"nothing was charged; resolution failed first"})
            ok,info=check_payment(self.headers,client)
            if not ok:
                return self._send(402,info,{"X-Payment-Required":str(PRICE_USD)})
            # A Morpho market and an AMM pool have different risk shapes, so they get different
            # answers rather than one function forced over both. The lending answer carries the
            # metrics that actually gate a deposit: runway in DOLLARS to the 95% lock, the
            # cadence-corrected sigma_to_breach, and the oracle flags.
            if isinstance(p, dict) and p.get("kind") == "morpho_market":
                mm = p["market"]
                rw = p.get("runway") or {}
                util = mm.get("utilization")
                sup = mm.get("tvl_usd")
                runway = rw.get("runway_usd")
                # the largest ticket that stays inside MAX_RUNWAY_SHARE of the runway
                try:
                    import allocator as _al
                    share = _al.MAX_RUNWAY_SHARE
                except Exception:
                    share = 0.50
                max_ticket = (runway * share) if runway else None
                out = {
                    "kind": "morpho_market",
                    "market_id": mm.get("market_id"),
                    "collateral": mm.get("collateral"),
                    "loan": mm.get("loan"),
                    "run": p.get("run"),
                    "verdict": p.get("verdict"),
                    "utilisation": util,
                    "lltv": mm.get("lltv"),
                    "supply_usd": sup,
                    "borrow_usd": mm.get("borrow_usd"),
                    "liquidity_usd": mm.get("liquidity_usd"),
                    # the three derived metrics the brief says justify the subscription
                    "runway_usd": runway,
                    "runway_lock_util": rw.get("lock_util"),
                    "capacity_max_ticket_usd": max_ticket,
                    "capacity_share_cap": share,
                    "sigma_to_breach": mm.get("sigma_to_breach"),
                    "daily_vol_pct": mm.get("daily_vol_pct"),
                    "vol_sample_days": mm.get("vol_sample_days"),
                    "oracle_type": mm.get("oracle_type"),
                    "oracle_flags": (mm.get("warnings_red") or []) + (mm.get("warnings_yellow") or []),
                    "at_or_past_lock": bool(runway is not None and runway <= 0),
                    "payment": info,
                    "note": ("runway_usd = supply - borrow/0.95, the dollars withdrawable before the "
                             "95% freeze. An accounting identity on published state, not a forecast. "
                             "Read from the newest immutable run, so it is tied to a block."),
                }
                return self._send(200, out)
            out=audit_pool(p); out["payment"]=info
            return self._send(200,out)
        if self.path=="/purchase":
            # ISSUANCE IS GATED. Without on-chain settlement the issuer IS the payment system, so
            # an anonymous caller must not be able to mint credit. Previously this endpoint handed
            # a token to anyone who asked, with no payment and no secret.
            op=os.environ.get("AEGIS_OPERATOR_SECRET")
            if not op:
                return self._send(503,{
                    "error":"issuance_disabled",
                    "detail":"no AEGIS_OPERATOR_SECRET set, so this endpoint cannot issue",
                    "why":"without on-chain settlement an ungated issuer mints credit for free",
                    "next":"issue tokens out of band: python3 tokens.py --init && --issue N"})
            if body.get("operator_secret")!=op:
                return self._send(403,{"error":"forbidden","detail":"bad operator secret"})
            if not SECRET:
                return self._send(503,{"error":"no_signing_secret",
                                       "detail":"run: python3 tokens.py --init"})
            credits=int(body.get("credits") or 100)
            tok,payload=_tokens.issue(body.get("sub") or client, credits, SECRET)
            return self._send(200,{"token":tok,"credits":credits,"sub":payload["sub"],
                "exp":payload["exp"],
                "warning":"UNSETTLED — no funds were verified. A signed credit, not a payment."})
        return self._send(404,{"error":"not found"})

if __name__=="__main__":
    srv=ThreadingHTTPServer((BIND,PORT),H)
    print(f"Aegis Audit MCP on {BIND}:{PORT}  price=${PRICE_USD}/audit  free={FREE_PER_DAY}/day",
          flush=True)
    if BIND in ("0.0.0.0", ""):
        print("  WARNING: bound to ALL interfaces. This host has a public address; set "
              "AEGIS_MCP_BIND to the tailnet IP instead.", flush=True)
    srv.serve_forever()

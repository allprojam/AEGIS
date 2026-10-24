#!/usr/bin/env python3
"""mcp_protocol.py - a real MCP server over the existing Aegis functions.

WHY THIS EXISTS. `mcp_server.py` was called an MCP but was not one. Measured: an MCP client
sends {"jsonrpc":"2.0","method":"tools/list"} and got **HTTP 404**. Zero protocol methods were
implemented. It was a hand-rolled HTTP JSON-RPC API with five routes -- useful, but no MCP
client could connect to it, so the claim "MCP for agents" was false.

This implements the protocol properly:
    initialize   -> handshake, capabilities, server info
    tools/list   -> the tool catalogue with JSON Schema for each input
    tools/call   -> invoke a tool, return MCP content blocks

TRANSPORT: MCP over stdio (newline-delimited JSON-RPC), which is what Claude Desktop, Cursor
and most agent frameworks use. Also servable over HTTP POST for clients that prefer it.

EVERY TOOL IS READ-ONLY. There is no tool that writes, signs, or spends. That is not a
limitation to be fixed later -- it is the product.

    python3 mcp_protocol.py            # stdio (an MCP client spawns this)
    python3 mcp_protocol.py --selftest # verify the handshake without a client
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SERVER_NAME = "aegis-risk"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------- tool definitions

TOOLS = [
    {
        "name": "audit_pool",
        "description": (
            "Run the six AMM screen checks on one liquidity pool and return the verdict with "
            "the reasons for each flag. Read-only: it classifies what a yield is MADE OF "
            "(organic fees vs emissions) and does not predict returns. Accepts a pair symbol, "
            "a contract address, or a GeckoTerminal/DexScreener URL."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Pair symbol (e.g. WETH-USDC), 0x address, or an "
                                         "explorer URL."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_markets",
        "description": (
            "List the Morpho Blue lending markets tracked across all recorded runs, with how "
            "many runs each has appeared in and its verdict history."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_market",
        "description": (
            "The full time series for one lending market across every recorded run: "
            "utilisation, LLTV, net APY, TVL, liquidity, sigma-to-breach and bad debt, each "
            "stamped with the run id and the Base block it came from. This is the dataset the "
            "dashboard cannot show. Accepts a market id or a collateral symbol."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {"type": "string",
                           "description": "market_id (0x...), collateral symbol (e.g. cbBTC), "
                                          "or a 0x prefix."}
            },
            "required": ["market"],
        },
    },
    {
        "name": "list_runs",
        "description": ("Index of every immutable recorded run: id, Base block, ingest time, "
                        "market count and verdict breakdown."),
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Newest N runs only."}},
        },
    },
    {
        "name": "get_run",
        "description": ("Every artefact for one run: the 60-market screen, the raw market data, "
                        "the allocation targets and the provenance metadata."),
        "inputSchema": {
            "type": "object",
            "properties": {"run": {"type": "string",
                                   "description": "Run id, e.g. 20261008T003939Z."}},
            "required": ["run"],
        },
    },
    {
        "name": "get_changes",
        "description": (
            "The State Transition Log: what actually changed between consecutive runs -- "
            "verdict downgrades, utilisation crossings, oracle flips. IMPORTANT: this is a "
            "transition log, not an exploit warning. It cannot see events that happen between "
            "polls. Read `unchecked` in the response before treating an empty log as a clean "
            "bill of health."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer",
                                     "description": "Most recent N intervals."}},
        },
    },
    {
        "name": "velocity_alerts",
        "description": (
            "Anomalous-velocity alerts: which ACTIVE markets just made a utilisation move that "
            "is unusual FOR THAT MARKET (a z-score against its own interval-move history), or a "
            "raw move of 5pp or more. This is the real-time signal the dashboard cannot show, "
            "and it is NOT a prediction -- a z-score says 'unlike this market's own recent "
            "behaviour', not 'what happens next'. An empty alerts list is a measurement (nothing "
            "is unusual right now), not a silent failure."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "position_risk",
        "description": (
            "Read-only health & velocity assessment for a leveraged LP position. Given value and "
            "debt in the SAME unit, returns health (= (value-debt)/value, 0.0 means liquidation), "
            "leverage, LTV, and drawdown-to-liquidation (which EQUALS health: the fraction of value "
            "the position can lose before value == debt). Optionally, given a price history and a "
            "vault type (short_eth/long_eth), returns the price-velocity regime (none/warn/alert/"
            "critical) and whether the move is dangerous FOR THAT position. This is measurement, "
            "not advice: no output tells you to sell, exit, or flip. Salvaged from the legacy "
            "daemon's SENSOR layer only; the actuator layer that backtested to -67% was discarded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "number",
                          "description": "Gross position value (USD or numeraire units)."},
                "debt": {"type": "number",
                         "description": "Debt in the SAME unit as value."},
                "vault_type": {"type": "string",
                               "description": "short_eth (hurt by a pump) or long_eth (hurt by a dump)."},
                "price_history": {"type": "array",
                                  "description": "[[ts_iso, price], ...] or [price, ...], oldest first."},
            },
            "required": ["value", "debt"],
        },
    },
]


def _text(obj):
    """MCP requires content blocks, not bare JSON."""
    return [{"type": "text", "text": json.dumps(obj, indent=1, default=str)}]


def _err(msg, code=-32602):
    return {"code": code, "message": str(msg)}


# ---------------------------------------------------------------- tool implementations

def tool_audit_pool(args):
    import mcp_server as ms
    q = args.get("query")
    if not q:
        raise ValueError("query is required")
    p = ms.resolve(q)
    if not p:
        return {"found": False, "query": q,
                "note": "Not in the scanned index. This page carries an upper slice of the "
                        "feed, so absence is a COVERAGE LIMIT, not a verdict about the pool."}
    out = ms.audit_pool(p)
    out["found"] = True
    out["symbol"] = p.get("symbol")
    out["chain"] = p.get("chain")
    return out


def tool_list_markets(args):
    import run_history as rh
    markets = rh.list_markets()
    return {"n": len(markets), "markets": sorted(markets.values(),
                                                 key=lambda e: -(e.get("runs_seen") or 0))}


def tool_get_market(args):
    import run_history as rh
    q = args.get("market")
    if not q:
        raise ValueError("market is required")
    ids = rh.resolve_market(q)
    if not ids:
        return {"found": False, "query": q,
                "note": "Unknown market. Call list_markets to see what is tracked."}
    if len(ids) > 1:
        # do NOT pick one. Several markets share a collateral symbol, and silently choosing
        # would attach real numbers to the wrong market.
        return {"found": False, "ambiguous": True, "query": q,
                "candidates": [{"market_id": i, "collateral": rh.list_markets()[i]["collateral"]}
                               for i in ids],
                "note": "Several markets match that collateral. Pass a full market_id."}
    mid = ids[0]
    pts = rh.get_series(mid)
    mk = rh.list_markets().get(mid, {})
    return {"found": True, "market_id": mid, "collateral": mk.get("collateral"),
            "lltv": mk.get("lltv"), "n_points": len(pts),
            "verdicts": mk.get("verdicts"), "series": pts}


def tool_list_runs(args):
    import run_history as rh
    lim = args.get("limit")
    idx = rh.get_index(limit=int(lim) if lim else None)
    return {"n": len(idx), "runs": idx}


def tool_get_run(args):
    import run_history as rh
    r = args.get("run")
    if not r:
        raise ValueError("run is required")
    got = rh.get_run(r)
    if got is None:
        return {"found": False, "run": r,
                "note": "Unknown or malformed run id. Call list_runs for valid ids."}
    got["found"] = True
    return got


def tool_get_changes(args):
    import run_history as rh
    lim = args.get("limit")
    ch = rh.get_changes(limit=int(lim) if lim else None)
    events = sum(r.get("n_events") or 0 for r in ch)
    return {
        "n_intervals": len(ch),
        "n_events": events,
        "log": ch,
        "unchecked": rh.get_unchecked(),
        "framing": ("STATE TRANSITION LOG, not exploit prevention. It compares consecutive "
                    "polls and cannot observe anything that happens between them. If "
                    "`unchecked` is non-empty, some checks did not run and their silence is "
                    "not evidence of stability."),
    }


def tool_velocity_alerts(args):
    import json as _json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, "velocity.json")) as fh:
            v = _json.load(fh)
    except FileNotFoundError:
        return {"found": False, "note": "velocity.json not built yet. Run "
                                        "`python3 screener/velocity.py`."}
    return {"found": True, "median_interval_hours": v.get("median_interval_hours"),
            "z_threshold": v.get("z_threshold"), "raw_floor": v.get("raw_floor"),
            "counts": v.get("counts"), "alerts": v.get("alerts", []),
            "framing": ("Anomalous-velocity, not a prediction. A flagged market made a move "
                        "unlike its own recent behaviour (z >= threshold) or a raw move >= the "
                        "floor. An empty alerts list is a measurement, not a failure.")}


def tool_position_risk(args):
    import sys
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import position_risk as pr
    value = args.get("value")
    debt = args.get("debt")
    if value is None or debt is None:
        return {"found": False, "note": "value and debt (same unit) are required."}
    ph = args.get("price_history")
    vt = args.get("vault_type")
    out = pr.assess_position(float(value), float(debt), price_history=ph, vault_type=vt)
    out["found"] = True
    return out


HANDLERS = {
    "audit_pool": tool_audit_pool,
    "list_markets": tool_list_markets,
    "get_market": tool_get_market,
    "list_runs": tool_list_runs,
    "get_run": tool_get_run,
    "get_changes": tool_get_changes,
    "velocity_alerts": tool_velocity_alerts,
    "position_risk": tool_position_risk,
}

# ---------------------------------------------------------------- JSON-RPC / MCP

def handle(msg):
    """One JSON-RPC message -> one response dict, or None for a notification."""
    if not isinstance(msg, dict):
        return {"jsonrpc": "2.0", "id": None, "error": _err("message must be an object", -32600)}
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    # notifications carry no id and expect no reply
    notif = mid is None

    def ok(result):
        return None if notif else {"jsonrpc": "2.0", "id": mid, "result": result}

    def fail(code, message):
        return None if notif else {"jsonrpc": "2.0", "id": mid,
                                   "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "Read-only risk intelligence for Base AMM pools and Morpho Blue lending "
                "markets. No tool writes, signs, or spends. audit_pool classifies what a yield "
                "is made of; get_market returns the recorded time series; get_changes is a "
                "state transition log, not an exploit warning."
            ),
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if not fn:
            return ok({"content": _text({"error": "unknown tool: %s" % name}),
                       "isError": True})
        try:
            return ok({"content": _text(fn(args)), "isError": False})
        except Exception as e:
            # a thrown tool must not kill the session: report it as an MCP error result
            return ok({"content": _text({"error": "%s: %s" % (type(e).__name__, e)}),
                       "isError": True})
    if method in ("resources/list", "prompts/list"):
        # declared capabilities do not include these; answer honestly rather than 404ing
        return fail(-32601, "method not supported by this server: %s" % method)
    return fail(-32601, "method not found: %s" % method)


def serve_stdio():
    """Newline-delimited JSON-RPC on stdin/stdout, the MCP stdio transport."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": None,
                 "error": _err("parse error", -32700)}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, default=str) + "\n")
            sys.stdout.flush()


def selftest():
    """Prove the handshake works without needing a client."""
    fails = []
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    ok = r and r.get("result", {}).get("serverInfo", {}).get("name") == SERVER_NAME
    print("  %-46s %s" % ("initialize returns serverInfo", "PASS" if ok else "FAIL"))
    if not ok:
        fails.append("initialize")

    r = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = (r or {}).get("result", {}).get("tools") or []
    ok = len(tools) == len(TOOLS) and all(t.get("inputSchema") for t in tools)
    print("  %-46s %s" % ("tools/list returns %d tools with schemas" % len(tools),
                          "PASS" if ok else "FAIL"))
    if not ok:
        fails.append("tools/list")

    for name in TOOLS:
        r = handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                    "params": {"name": name["name"], "arguments": {}}})
        res = (r or {}).get("result") or {}
        blocks = res.get("content") or []
        ok = bool(blocks) and blocks[0].get("type") == "text"
        print("  %-46s %s" % ("tools/call %s returns content" % name["name"],
                              "PASS" if ok else "FAIL"))
        if not ok:
            fails.append(name["name"])

    r = handle({"jsonrpc": "2.0", "id": 3, "method": "nonsense/method"})
    ok = (r or {}).get("error", {}).get("code") == -32601
    print("  %-46s %s" % ("unknown method returns -32601", "PASS" if ok else "FAIL"))
    if not ok:
        fails.append("unknown method")

    r = handle({"jsonrpc": "2.0", "id": None, "method": "notifications/initialized"})
    print("  %-46s %s" % ("notification produces no reply", "PASS" if r is None else "FAIL"))
    if r is not None:
        fails.append("notification")

    print()
    if fails:
        print("  %d FAILURE(S): %s" % (len(fails), ", ".join(fails)))
        return 1
    print("  MCP handshake verified")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    serve_stdio()

#!/usr/bin/env python3
"""MCP over HTTP for the hosted Aegis endpoint. Thin transport, no business logic.

WHY THIS FILE EXISTS. mcp_protocol.py speaks stdio only. stdio is right for local use: an MCP
client spawns the process and talks over pipes, no network, no auth, no attack surface. But
stdio cannot be hosted, and it cannot be rate limited, because there is no request to count.

So the protocol logic stays in mcp_protocol.handle() and this file only adds what hosting
needs: a socket, peer identification, and limits. One dispatcher, two transports, so they
cannot drift apart.

POST /mcp   JSON-RPC, same bodies as stdio
GET  /health

ORDER OF CHECKS, deliberately:
    1. size    an oversized body is rejected before it is read into memory
    2. auth    unauthenticated callers never reach the limiter's buckets
    3. limit   authenticated callers are metered
    4. dispatch

Auth is optional and off by default, so `python3 mcp_http.py` runs an open endpoint for
local testing. Set MCP_REQUIRE_TOKEN=1 to require a token from screener/tokens.py.
"""
import json
import os
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mcp_protocol
from rate_limit import RateLimiter, DEFAULT_RULES

MAX_BODY = 1 << 20          # 1 MiB. MCP tool calls are small; a large body is a mistake or an attack.
REQUIRE_TOKEN = os.environ.get("MCP_REQUIRE_TOKEN", "0") == "1"
TOKEN_SECRET_PATH = os.path.join(HERE, "screener", "token_secret.key")

_limiter = RateLimiter(DEFAULT_RULES)
_token_secret = None


def _secret():
    """Load the HMAC secret once. Never generated implicitly; a missing secret is loud."""
    global _token_secret
    if _token_secret is None:
        try:
            with open(TOKEN_SECRET_PATH) as fh:
                _token_secret = fh.read().strip() or ""
        except OSError:
            _token_secret = ""
    return _token_secret


def _verify_token(tok):
    """tokens.verify returns (ok, payload_or_error). Returning that tuple directly is a BUG:
    (False, "bad_signature") is a truthy tuple, so every non-empty token would be accepted.
    Unpack it, and return only a payload on success.
    """
    if not tok:
        return None
    try:
        sys.path.insert(0, os.path.join(HERE, "screener"))
        import tokens
        ok, payload = tokens.verify(tok, _secret())
        return payload if ok else None
    except Exception:
        return None


def _client_ip(handler):
    """X-Forwarded-For is only trusted if this process is behind a proxy it controls.

    TRUST_PROXY is explicit and defaults off. Trusting the header by default lets any caller
    set their own identity and walk around the per-IP limit, which is the whole point of it.
    """
    if os.environ.get("TRUST_PROXY", "0") == "1":
        xff = handler.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return handler.client_address[0]


class Handler(BaseHTTPRequestHandler):
    server_version = "AegisMCP/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), fmt % args))

    def _send(self, code, payload, extra=None, close=False):
        body = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        # EARLY REJECTIONS MUST CLOSE THE CONNECTION.
        # On the 401 and 413 paths the request body is deliberately never read. Under HTTP/1.1
        # keep-alive those unread bytes stay in the socket and the next read sees them as a
        # request line, which produced 'Bad request syntax' in the journal. Closing is the only
        # correct answer when a body has been refused but not consumed.
        self.close_connection = close
        if close:
            self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def do_GET(self):
        if self.path.split("?")[0] in ("/health", "/healthz"):
            return self._send(200, {"ok": True, "service": "aegis-mcp", "ts": int(time.time())})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/mcp":
            return self._send(404, {"error": "not found"}, close=True)

        # 1. size, before reading
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"error": "bad Content-Length"})
        if length <= 0:
            return self._send(400, {"error": "empty body"})
        if length > MAX_BODY:
            return self._send(413, {"error": "body too large", "max_bytes": MAX_BODY}, close=True)

        # 2. auth, before metering, so unauthenticated traffic costs no buckets
        tok = None
        if REQUIRE_TOKEN:
            auth = self.headers.get("Authorization") or ""
            tok = auth[7:].strip() if auth.lower().startswith("bearer ") else None
            claims = _verify_token(tok)
            if not claims:
                return self._send(401, {"error": "valid bearer token required"},
                                  {"WWW-Authenticate": 'Bearer realm="Aegis MCP"'}, close=True)

        # 3. limits
        allowed, hdrs, why = _limiter.check(ip=_client_ip(self), token=tok)
        if not allowed:
            return self._send(429, {"error": why}, hdrs)   # body was read, keep-alive is safe

        # 4. dispatch: the same function stdio uses, so transports cannot drift
        try:
            raw = self.rfile.read(length)
            msg = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return self._send(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32700, "message": "parse error: %s" % e}})

        try:
            resp = mcp_protocol.handle(msg)
        except Exception as e:
            return self._send(500, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32603, "message": "internal: %s" % e}})

        if resp is None:                      # notification: no reply by protocol
            self.send_response(202)
            self.send_header("Content-Length", "0")
            for k, v in hdrs.items():
                self.send_header(k, v)
            self.end_headers()
            return
        return self._send(200, resp, hdrs)


def main():
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8051"))
    if REQUIRE_TOKEN and not _secret():
        sys.stderr.write("FATAL: MCP_REQUIRE_TOKEN=1 but no secret at %s\n" % TOKEN_SECRET_PATH)
        return 2
    srv = ThreadingHTTPServer((host, port), Handler)
    sys.stderr.write("aegis-mcp listening on http://%s:%d/mcp (auth=%s)\n"
                     % (host, port, "on" if REQUIRE_TOKEN else "off"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

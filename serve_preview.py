#!/usr/bin/env python3
"""serve_preview.py - static file server that gzips.

WHY THIS EXISTS. report.html is 3.44MB, and 80% of it is one inlined JSON blob. `python3 -m
http.server` sends it uncompressed, so every fetch moves all 3.44MB. The same bytes gzip to
0.48MB -- an 86% reduction for no change to the file, the page, or the architecture.

The alternative fixes (dictionary-encoding the blob, fetching the data at load) all change the
artifact or break the single-file property. This changes NEITHER: the page stays one file with
zero external requests, and the wire payload shrinks by 6x.

Correctness rules that matter here, because a static server that is subtly wrong is worse than
no server:
  * gzip ONLY when the client asked for it (Accept-Encoding). A client that did not ask must
    get plain bytes -- sending gzip regardless breaks curl, wget, and anything scripted.
  * never gzip what is already compressed (png/jpg/woff/gz/zip): it costs CPU and grows the bytes.
  * send Vary: Accept-Encoding so a cache never serves gzip bytes to a client expecting plain.
  * send the UNCOMPRESSED length as Content-Length? No -- when we encode, Content-Length must
    match what we actually send, or the client hangs. We send the encoded length and, correctly,
    drop Accept-Ranges (ranges on a compressed body are a different resource).
  * the symlink must be followed (index.html -> ../report.html). SimpleHTTPRequestHandler
    already does; we keep that behaviour rather than re-implementing path handling.
"""
import gzip, json, os, sys
from urllib.parse import urlparse, parse_qs
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
ROOT = os.path.dirname(os.path.abspath(__file__))

# Already-compressed types. gzipping these adds bytes and burns CPU for nothing.
SKIP = (".gz", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".woff", ".woff2", ".ico", ".mp4")
MIN_BYTES = 1024          # below this the gzip header costs more than it saves


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # ---- /api/chat: deterministic lookup + LLM intent routing, never an invented number ----
    def _chat(self):
        import chat_api
        q = None
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length and length < 1_000_000:
                body = json.loads(self.rfile.read(length).decode() or "{}")
                q = body.get("q") or body.get("question")
        except Exception:
            body = None
        if not q:
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q") or qs.get("question") or [None])[0]
        if not q:
            return {"error": "missing q (query or JSON body)"}
        try:
            r = chat_api.answer(q)
        except Exception as e:
            return {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}
        return r

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/api/chat":
            self._send_json(self._chat())
            return
        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path == "/api/chat":
            self._send_json(self._chat())
            return
        super().do_POST()

    def end_headers(self):
        # a cache must not hand gzip bytes to a client that cannot read them
        if self._gz():
            self.send_header("Vary", "Accept-Encoding")
        super().end_headers()

    def _gz(self):
        ae = self.headers.get("Accept-Encoding", "") or ""
        return "gzip" in ae.lower()

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            # "/" must serve the PAGE, not a directory listing. SimpleHTTPRequestHandler only
            # auto-serves index.html when the directory HAS one; this repo keeps the page in
            # screener/, so "/" listed the project root instead -- 13KB of file names, no
            # dashboard. That is the same class of bug as the stale index.html: the obvious URL
            # did not show the thing it was supposed to show.
            for cand in ("screener/index.html", "index.html", "report.html"):
                full = os.path.join(path, cand)
                if os.path.isfile(full):
                    path = full
                    break
        if not os.path.isfile(path) or path.lower().endswith(SKIP):
            return super().send_head()
        if not self._gz():
            # Serve the RESOLVED path, not self.path. Falling through to super() here re-translates
            # the ORIGINAL self.path -- so "/" reverted to a directory listing for clients that did
            # not send Accept-Encoding, while gzip clients got the page. Two clients, two different
            # documents, from one URL. Same class of bug as the stale index.html.
            keep, self.path = self.path, "/" + os.path.relpath(path, ROOT)
            try:
                return super().send_head()
            finally:
                self.path = keep

        try:
            st = os.stat(path)
            if st.st_size < MIN_BYTES:
                return super().send_head()
            with open(path, "rb") as f:
                raw = f.read()
            body = gzip.compress(raw, 6)
            # only send gzip if it actually helped
            if len(body) >= len(raw):
                return super().send_head()
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            # the body is now opaque; byte ranges would address the WRONG resource
            self.send_header("Accept-Ranges", "none")
            self.end_headers()
            return _Bytes(body)
        except Exception:
            return super().send_head()

    def log_message(self, *a):
        pass              # the preview does not need an access log


class _Bytes:
    """Minimal readable file object so the base class can copy it out."""
    def __init__(self, b):
        self._b = b
        self._i = 0

    def read(self, n=-1):
        if n is None or n < 0:
            out = self._b[self._i:]
            self._i = len(self._b)
        else:
            out = self._b[self._i:self._i + n]
            self._i += len(out)
        return out

    def close(self):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    # Print the port the OS ACTUALLY bound, not the one we asked for. With PORT=0 the kernel picks
    # a free port and the requested value is useless -- a caller that reads this line to find the
    # server would connect to port 0 and fail. Reporting server_address is what makes ephemeral
    # binding usable, and it removes the EADDRINUSE hazard of a hardcoded test port.
    bound = srv.server_address[1]
    print("serving %s on 0.0.0.0:%d (gzip on)" % (ROOT, bound), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

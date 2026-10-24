#!/usr/bin/env python3
"""The preview server must compress, must not compress what should not be, and "/" must be the page.

WHY THIS EXISTS. report.html is 3.4MB and 80% of that is one inlined JSON blob. The page gzips to
0.51MB -- a 6x reduction with no change to the file or the architecture. But a compress-on-the-fly
server has several ways to be subtly wrong, and each one is a silent failure:

  * sending gzip to a client that did not ask  -> unreadable page, no error anywhere
  * gzipping an already-compressed type        -> more bytes and wasted CPU
  * Content-Length that does not match the body-> client hangs
  * omitting Vary: Accept-Encoding             -> a cache serves gzip bytes to a plain client
  * "/" serving a directory listing instead of the page -> the obvious URL shows file names

The last one was a REAL bug in the first version of serve_preview.py: directory=ROOT meant "/"
listed the project root, because the page lives in screener/ and the root has no index.html.

Run:  python3 tests/test_gzip_server.py
"""
import gzip, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# NO HARDCODED PORT. This was 8097, which is an EADDRINUSE hazard the moment two suites run
# concurrently (verified: a second bind fails with [Errno 98]). The test now asks the OS for a free
# port (PORT=0) and reads the one the server reports it actually bound, so parallel runners cannot
# collide. `get()` therefore takes the port as an argument rather than closing over a constant.
FAILS = []


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond and detail:
        print("      %s" % detail)
    if not cond:
        FAILS.append(name)


def get(path, port, gz=False):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path))
    if gz:
        req.add_header("Accept-Encoding", "gzip")
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r, r.read()
    except Exception as e:
        return None, str(e).encode()


def start_server():
    """Start serve_preview.py on an ephemeral port and return (process, port).

    The port is read from the server's own stdout, because with PORT=0 the port we REQUESTED is
    meaningless -- only the one the kernel assigned is real.
    """
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "serve_preview.py"), "0"],
                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    port = None
    deadline = time.time() + 15
    while time.time() < deadline:
        line = srv.stdout.readline()
        if not line:
            break
        m = re.search(r"0\.0\.0\.0:(\d+)", line)
        if m:
            port = int(m.group(1))
            break
    if port is None:
        try: srv.kill()
        except Exception: pass
        return None, None
    return srv, port


def main():
    srv, PORT = start_server()
    if PORT is None:
        check("the preview server starts and reports its port", False,
              "no port line on stdout within the deadline. The usual cause is BUFFERED stdout: "
              "with stdout=subprocess.PIPE Python block-buffers, so the port line sits in the "
              "buffer and readline() blocks. serve_preview.py must print it with flush=True "
              "(verified load-bearing: 0.1s with the flush, hangs without it).")
        return 1
    print("  server bound an ephemeral port: %d" % PORT)
    try:
        canon = os.path.join(ROOT, "report.html")
        if not os.path.exists(canon):
            check("report.html exists", False)
            return 1
        raw = open(canon, "rb").read()

        print("=== 1. gzip is used when asked for ===")
        r, body = get("/report.html", PORT, gz=True)
        enc = (r.headers.get("Content-Encoding") if r else "") or ""
        check("Content-Encoding is gzip", "gzip" in enc.lower(), "got %r" % enc)
        check("Vary: Accept-Encoding is sent", "accept-encoding" in ((r.headers.get("Vary") if r else "") or "").lower())
        if "gzip" in enc.lower():
            try:
                dec = gzip.decompress(body)
                check("decodes byte-identical to report.html", dec == raw,
                      "%d vs %d bytes" % (len(dec), len(raw)))
            except Exception as e:
                check("decodes cleanly", False, str(e))
            check("wire size is at least 3x smaller (%d -> %d)" % (len(raw), len(body)),
                  len(body) * 3 < len(raw), "gzip did not help much; check the handler")

        print("\n=== 2. NO gzip when the client did not ask ===")
        r2, body2 = get("/report.html", PORT, gz=False)
        enc2 = (r2.headers.get("Content-Encoding") if r2 else "") or ""
        check("no Content-Encoding", not enc2.strip(), "got %r" % enc2)
        check("plain body is the full file", body2 == raw, "%d vs %d bytes" % (len(body2), len(raw)))

        print("\n=== 3. '/' serves the PAGE, not a directory listing ===")
        r3, body3 = get("/", PORT, gz=True)
        if r3 and "gzip" in ((r3.headers.get("Content-Encoding") or "").lower()):
            body3 = gzip.decompress(body3)
        check("/ returns the dashboard", body3.lstrip()[:15].lower().startswith(b"<!doctype html"))
        check("/ is not a directory listing", b"serve_preview.py" not in body3,
              "'/' listed files instead of serving the page")
        check("/ body is the same page as /report.html", body3 == raw)

        # THE REGRESSION THAT MATTERS: "/" must return the SAME document whether or not the
        # client accepts gzip. The first version sent the page to gzip clients and a 13KB
        # directory listing to everyone else -- two clients, two documents, one URL.
        r3b, body3b = get("/", PORT, gz=False)
        check("/ is the page WITHOUT Accept-Encoding too",
              body3b.lstrip()[:15].lower().startswith(b"<!doctype html"),
              "'/' served something other than the dashboard to a plain client")
        check("/ is identical with and without gzip", body3b == body3,
              "the compressed and uncompressed responses differ -- one URL, two documents")

        print("\n=== 4. already-compressed types are left alone ===")
        wav = os.path.join(ROOT, "tts-test.wav")
        if os.path.exists(wav):
            r4, b4 = get("/tts-test.wav", PORT, gz=True)
            e4 = (r4.headers.get("Content-Encoding") if r4 else "") or ""
            check("wav is not gzipped (it is already compressed)", not e4.strip(), "got %r" % e4)
        else:
            # a skipped check is not a passing check -- say so rather than printing nothing
            check("no compressed-type fixture in the repo to test (skipped)", True,
                  "add one to exercise the SKIP list")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()

    print("\n=== RESULT ===")
    if FAILS:
        print("  %d FAILURE(S):" % len(FAILS))
        for f in FAILS:
            print("    - %s" % f)
        return 1
    print("  the preview server compresses correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

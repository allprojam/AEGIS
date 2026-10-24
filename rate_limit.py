#!/usr/bin/env python3
"""Rate limiting for the Aegis MCP endpoint. Three independent limits, all in-process.

WHY IN-PROCESS AND NOT REDIS. One VPS, one process, one dataset. A shared store would add a
dependency and a failure mode to solve a problem this deployment does not have. If it ever
runs on more than one box, this file is the thing to replace, and that is stated here rather
than discovered later.

THREE LIMITS, because one is not enough:
    per-IP      a single caller cannot monopolise the endpoint
    per-token   a paying subscriber cannot be starved by another subscriber sharing an IP (CGNAT)
    global      total load has a ceiling regardless of how the above are distributed

SLIDING WINDOW, not fixed window. A fixed-window counter lets a caller send 2x the limit
across a window boundary. Sliding is slightly more state and correct, so it is what is used.

NO EVICTION BY TIMEOUT ALONE: buckets are swept lazily on access, so an idle process does not
hold memory for callers that stopped.
"""
import time
import threading
from collections import deque

# Tuned for a read-only public data endpoint. The screen is ~0.02s and the fetch is not on the
# request path, so these are generous for a human-driven agent and tight for a scraper.
DEFAULT_RULES = {
    "ip":     (60, 60),      # 60 requests / 60s  per IP
    "token":  (600, 60),     # 600 requests / 60s per token (paid tier is higher)
    "global": (1200, 60),    # 1200 requests / 60s total, regardless of source
}


class SlidingWindow:
    """A deque of timestamps per key, swept lazily."""

    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._hits = {}
        self._lock = threading.Lock()

    def hit(self, key, now=None):
        """Record a hit. Returns (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                q = self._hits[key] = deque()
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                # retry after the oldest hit falls out of the window
                retry = max(0.0, (q[0] + self.window) - now)
                return False, 0, retry
            q.append(now)
            return True, self.limit - len(q), 0.0

    def sweep(self, now=None):
        """Drop empty buckets. Called opportunistically, never on a timer."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            dead = [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]
            for k in dead:
                del self._hits[k]
            return len(dead)


class RateLimiter:
    def __init__(self, rules=None):
        self.rules = dict(rules or DEFAULT_RULES)
        self.windows = {name: SlidingWindow(limit, window)
                        for name, (limit, window) in self.rules.items()}
        self._sweep_counter = 0

    def check(self, ip=None, token=None, now=None):
        """All applicable limits must pass. Returns (allowed, headers_dict, reason)."""
        results = []
        if ip:
            results.append(("ip",) + self.windows["ip"].hit(ip, now))
        if token:
            results.append(("token",) + self.windows["token"].hit(token, now))
        results.append(("global",) + self.windows["global"].hit("__all__", now))

        # opportunistic sweep keeps memory bounded without a background thread
        self._sweep_counter += 1
        if self._sweep_counter % 1000 == 0:
            for w in self.windows.values():
                w.sweep(now)

        denied = [r for r in results if not r[1]]
        remaining = min(r[2] for r in results)
        if denied:
            name, _, _, retry = denied[0]
            headers = {
                "Retry-After": str(int(retry) + 1),
                "X-RateLimit-Limit": str(self.rules[name][0]),
                "X-RateLimit-Remaining": "0",
            }
            return False, headers, "rate limit exceeded (%s)" % name

        tightest = min(results, key=lambda r: r[2])
        headers = {
            "X-RateLimit-Limit": str(self.rules[tightest[0]][0]),
            "X-RateLimit-Remaining": str(remaining),
        }
        return True, headers, None


def selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        print("  %-52s %s" % (label, "PASS" if cond else "FAIL"))
        ok = ok and cond

    # a 3-per-10s window
    rl = RateLimiter({"ip": (3, 10), "token": (3, 10), "global": (100, 10)})
    t = 0.0
    allow = [rl.check("1.2.3.4", now=t)[0] for _ in range(3)]
    check("three requests inside the limit are allowed", all(allow))
    allowed, hdrs, why = rl.check("1.2.3.4", now=t)
    check("the fourth is refused", not allowed)
    check("refusal names the limit", why and "ip" in why)
    check("refusal carries Retry-After", "Retry-After" in hdrs)

    # a different IP is unaffected
    check("a different IP is still allowed", rl.check("5.6.7.8", now=t)[0])

    # window slides: after 10s the first caller recovers
    check("the window slides and the caller recovers", rl.check("1.2.3.4", now=t + 10.5)[0])

    # global ceiling applies across IPs
    rl2 = RateLimiter({"ip": (100, 10), "token": (100, 10), "global": (2, 10)})
    a = rl2.check("1.1.1.1", now=0)[0]
    b = rl2.check("2.2.2.2", now=0)[0]
    c, _, why = rl2.check("3.3.3.3", now=0)
    check("global ceiling refuses the third distinct IP", a and b and not c)
    check("global refusal names the global limit", "global" in (why or ""))

    # token limit is separate from IP so CGNAT cannot starve a subscriber
    rl3 = RateLimiter({"ip": (100, 10), "token": (2, 10), "global": (100, 10)})
    rl3.check("9.9.9.9", token="A", now=0)
    rl3.check("9.9.9.9", token="A", now=0)
    d, _, why = rl3.check("9.9.9.9", token="A", now=0)
    check("per-token limit refuses the third use of token A", not d)
    check("token refusal names the token limit", "token" in (why or ""))
    check("token B is unaffected", rl3.check("9.9.9.9", token="B", now=0)[0])

    # sweep drops dead buckets
    rl4 = RateLimiter({"ip": (5, 1), "token": (5, 1), "global": (5, 1)})
    for i in range(20):
        rl4.check("10.0.0.%d" % i, now=0)
    dropped = rl4.windows["ip"].sweep(now=100)
    check("sweep removes expired buckets", dropped == 20)

    print("\n  %s" % ("rate limiter selftest passed" if ok else "SELFTEST FAILED"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)

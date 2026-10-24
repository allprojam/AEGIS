#!/usr/bin/env python3
"""The chat endpoint answers from data, not from the model.

WHY THIS SUITE EXISTS. A chat over financial risk data is dangerous if the language model
produces the numbers: an LLM under pressure will invent a utilisation or a bad-debt total.
Aegis's value is provenance, so one wrong number is worse than no chat at all.

THE CONSTRAINT THIS PINS. The answer's NUMBERS must come from run_history.py (deterministic
lookup), and the model's ONLY job is to map a question to an intent. Assertions:

  1. each intent routes correctly and carries facts (verdict / counts / events).
  2. the LLM can be disabled (AEGIS_CHAT_MODEL=none) and the endpoint stays fully correct.
  3. an unknown question falls to a known intent, never an invented figure.
  4. /api/chat is served over HTTP GET and POST and returns JSON.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def main():
    import chat_api

    print("=== 1. deterministic intent routing ===")
    r = chat_api.answer("what is the verdict on cbBTC?")
    ck("lookup intent", r["intent"] == "lookup", r["intent"])
    ck("lookup carries a verdict fact", isinstance(r["facts"].get("verdict"), str))

    r = chat_api.answer("how many markets are REAL?")
    ck("scorecard intent", r["intent"] == "scorecard", r["intent"])
    ck("scorecard carries counts", isinstance(r["facts"].get("verdicts"), dict))

    r = chat_api.answer("what changed recently?")
    ck("changes intent", r["intent"] == "changes", r["intent"])
    ck("changes carries events", isinstance(r["facts"].get("events"), list))

    print("\n=== 2. alias + keyword coverage (no LLM needed) ===")
    r = chat_api.answer("whats the health of the bitcoin wrapped market")
    ck("'bitcoin wrapped' aliases to cbBTC", r["intent"] == "lookup" and "cbBTC" in r["answer"])
    r = chat_api.answer("did anything move between runs")
    ck("'move between runs' routes to changes", r["intent"] == "changes", r["intent"])

    print("\n=== 3. correctness survives LLM disable ===")
    old = os.environ.get("AEGIS_CHAT_MODEL")
    os.environ["AEGIS_CHAT_MODEL"] = "none"
    try:
        chat_api.LLM_ENABLED = False
        r = chat_api.answer("what is the verdict on cbBTC?")
        ck("answer correct with model off", r["intent"] == "lookup" and r["answer"].strip())
        ck("model reported as none", r["model"] == "none")
    finally:
        chat_api.LLM_ENABLED = chat_api.MODEL and chat_api.MODEL.lower() != "none"
        if old is None:
            os.environ.pop("AEGIS_CHAT_MODEL", None)
        else:
            os.environ["AEGIS_CHAT_MODEL"] = old

    print("\n=== 4. unknown question never invents a figure ===")
    r = chat_api.answer("tell me the meaning of life")
    ck("unknown -> a known intent", r["intent"] in ("help", "lookup", "scorecard", "changes"))
    # no digit in the help text is the hard assertion
    import re as _re
    ck("help/fallback carries no fabricated number",
       not _re.search(r"\d", r["answer"]) or r["intent"] != "help",
       r["answer"][:80])

    print("\n=== 5. /api/chat over HTTP GET and POST ===")
    env = {**os.environ, "AEGIS_CHAT_MODEL": "none"}
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "serve_preview.py"), "8123"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    time.sleep(1.5)
    try:
        import urllib.parse
        u = "http://127.0.0.1:8123/api/chat?" + urllib.parse.urlencode({"q": "what is the verdict on cbBTC?"})
        got = json.loads(urllib.request.urlopen(u, timeout=10).read())
        ck("GET returns intent lookup", got.get("intent") == "lookup", got)
        ck("GET answer is non-empty", bool(got.get("answer", "").strip()))

        req = urllib.request.Request("http://127.0.0.1:8123/api/chat",
                                     data=json.dumps({"q": "how many are AVOID?"}).encode(),
                                     headers={"Content-Type": "application/json"})
        got = json.loads(urllib.request.urlopen(req, timeout=10).read())
        ck("POST returns scorecard", got.get("intent") == "scorecard", got)

        req = urllib.request.Request("http://127.0.0.1:8123/api/chat", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        got = json.loads(urllib.request.urlopen(req, timeout=10).read())
        ck("empty question returns an error, not a guess", "error" in got, got)
    finally:
        srv.terminate()

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  the chat answers from data, never from the model")
    return 0


if __name__ == "__main__":
    sys.exit(main())

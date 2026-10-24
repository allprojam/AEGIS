#!/usr/bin/env python3
"""chat_api.py - a chat surface over Aegis data that cannot hallucinate a number.

WHY THIS EXISTS. A chat over financial risk data is dangerous if the language model is the
thing that produces the figures: an LLM under pressure to answer will invent a utilisation or
a bad-debt total. Aegis's whole value is provenance and honesty, so one wrong number in a chat
answer does more damage than the feature is worth.

THE RULE THIS ENFORCES, therefore, is the inverse of a generic chatbot:

    * the NUMBERS always come from run_history.py (deterministic JSON lookup), never from the
      model;
    * the model's ONLY job is to map a question to an intent when the deterministic keyword
      route does not match. The answer sentence is built from a template over the retrieved
      facts, so it cannot drift.

The LLM is therefore OPTIONAL and OPT-IN: with AEGIS_CHAT_MODEL=none the endpoint is a pure
deterministic lookup and still fully correct. With a model set, varied phrasings that miss the
keywords still route correctly, but the model never writes a digit.
"""
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

MODEL = os.environ.get("AEGIS_CHAT_MODEL", "llama3:latest").strip()
OLLAMA_URL = os.environ.get("AEGIS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
LLM_TIMEOUT = float(os.environ.get("AEGIS_CHAT_LLM_TIMEOUT", "15"))
LLM_ENABLED = MODEL and MODEL.lower() != "none"


def _rh():
    import run_history
    return run_history


_LOOKUP_WORDS = ("verdict", "what is", "what's", "how is", "status", "utilis", "utiliz",
                 "apy", "supplied", "liquidity", "lltv", "bad debt", "market")
_SCORECARD_WORDS = ("how many", "scorecard", "count", "real or caution or avoid",
                    "breakdown", "summary", "totals", "distribution")
_CHANGES_WORDS = ("changed", "change", "what happened", "transition", "downgrade",
                  "upgrade", "moved", "move", "between runs", "flip", "alert", "recent")
_DEX_WORDS = ("fee", "fees", "pool", "pools", "volume", "dex", "aerodrome", "uniswap",
              "slipstream", "cbbtc pool", "which pool", "highest fee", "most fees",
              "liquidity range", "fee tier")


def _keyword_intent(q):
    ql = q.lower()
    if any(w in ql for w in _CHANGES_WORDS) and not any(w in ql for w in ("cb", "btc", "ltc", "eth")):
        return "changes"
    if any(w in ql for w in _DEX_WORDS):
        return "dex"
    if any(w in ql for w in _SCORECARD_WORDS):
        return "scorecard"
    if any(w in ql for w in _LOOKUP_WORDS):
        return "lookup"
    return None


def _llm_classify(q):
    if not LLM_ENABLED:
        return None
    prompt = (
        "Classify this user question into exactly one intent token: "
        "lookup, scorecard, changes, or help. Reply with only that one word.\n\n"
        "Question: %s" % q
    )
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 8, "temperature": 0},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL + "/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        r = json.loads(urllib.request.urlopen(req, timeout=LLM_TIMEOUT).read())
        tok = (r.get("response") or "").strip().lower()
        for word in ("lookup", "scorecard", "changes", "dex", "help"):
            if word in tok:
                return word
    except Exception:
        pass
    return None


def classify(q):
    q = str(q or "").strip()
    if not q:
        return "help"
    k = _keyword_intent(q)
    if k:
        return k
    m = _llm_classify(q)
    return m or "help"


def _latest_index():
    idx = _rh().get_index(limit=1)
    return idx[0] if idx else None


def _fmt_usd(x):
    try:
        x = float(x or 0)
    except (TypeError, ValueError):
        return "$0"
    if abs(x) >= 1e9:
        return "$%.2fB" % (x / 1e9)
    if abs(x) >= 1e6:
        return "$%.1fM" % (x / 1e6)
    if abs(x) >= 1e3:
        return "$%.0fK" % (x / 1e3)
    return "$%.0f" % x


def _fmt_pct(x):
    try:
        return "%.1f%%" % (float(x or 0) * 100)
    except (TypeError, ValueError):
        return "n/a"


def _fmt_apy(x):
    try:
        return "%.2f%%" % float(x or 0)
    except (TypeError, ValueError):
        return "n/a"


_ALIASES = {
    "wrapped bitcoin": "cbBTC", "bitcoin wrapped": "cbBTC", "wrapped btc": "cbBTC",
    "wrapped ether": "cbETH", "wrapped eth": "cbETH",
    "wrapped litecoin": "cbLTC", "wrapped ltc": "cbLTC",
}


def retrieve_lookup(q):
    rh = _rh()
    ql = q.lower()
    toks = re.findall(r"0x[0-9a-fA-F]{6,64}", q)
    toks += re.findall(r"\b(?:cb)?(BTC|ETH|LTC|USD|USDC|DAI|ZEC|SOL|AVAX|LINK|DOT|XRP|DOGE)\b", q, re.I)
    for phrase, sym in _ALIASES.items():
        if phrase in ql:
            toks.insert(0, sym)
    matched = []
    for t in toks:
        matched = rh.resolve_market(t)
        if matched:
            break
    if not matched:
        for t in sorted(set(re.findall(r"[A-Za-z]{2,8}", q)), key=len, reverse=True):
            matched = rh.resolve_market(t)
            if matched:
                break
    if not matched:
        return {"found": False, "question": q, "ambiguity": "no market matched the question"}
    if len(matched) > 1:
        syms = sorted({(_market_symbol(m) or m[:10]) for m in matched})
        return {"found": False, "question": q, "ambiguity": "ambiguous: %d markets (%s)"
                % (len(matched), ", ".join(syms))}
    mid = matched[0]
    series = rh.get_series(mid)
    if not series:
        return {"found": False, "question": q, "ambiguity": "market recorded but no series"}
    latest = series[-1]
    return {
        "found": True,
        "market_id": mid,
        "collateral": latest.get("collateral") or _market_symbol(mid),
        "verdict": latest.get("verdict"),
        "utilization": latest.get("utilization"),
        "net_apy": latest.get("net_apy"),
        "tvl_usd": latest.get("tvl_usd"),
        "liquidity_usd": latest.get("liquidity_usd"),
        "lltv": latest.get("lltv"),
        "bad_debt_usd": latest.get("bad_debt_usd"),
        "realized_bad_debt_usd": latest.get("realized_bad_debt_usd"),
        "fails": latest.get("fails") or [],
        "reasons": latest.get("reasons") or [],
        "run": latest.get("run"),
    }


def _market_symbol(mid):
    ms = _rh().list_markets()
    e = ms.get(mid)
    return (e or {}).get("collateral")


def retrieve_scorecard():
    idx = _latest_index()
    if not idx:
        return {"found": False, "ambiguity": "no runs recorded"}
    return {"found": True, "run": idx["run"], "block": idx["block"],
            "n_markets": idx["n_markets"], "verdicts": idx["verdicts"] or {}}


def retrieve_changes(q):
    rh = _rh()
    m = re.search(r"(\d+)\s*(?:last|recent|changes|events|transitions)", q.lower())
    limit = int(m.group(1)) if m else 5
    changes = rh.get_changes(limit=limit)
    events = []
    for rec in changes:
        for e in rec.get("events") or []:
            events.append({
                "detail": e.get("detail"),
                "kind": e.get("kind"),
                "severity": e.get("severity"),
                "collateral": e.get("collateral"),
                "block": rec.get("block"),
                "logged_at": rec.get("logged_at"),
            })
    latest = _latest_index()
    return {"found": True, "run": latest.get("run") if latest else None,
            "n_intervals": len(changes), "n_events": len(events), "events": events}


def _phrase_lookup(f):
    if not f["found"]:
        return ("I could not match a market to that question. Try a collateral symbol like "
                "cbBTC, cbLTC or cbETH, or a 0x market id." + (
                    " (%s)" % f.get("ambiguity") if f.get("ambiguity") else ""))
    parts = ["%s is %s." % (f["collateral"], f["verdict"])]
    parts.append("utilisation %s, net APY %s." % (_fmt_pct(f["utilization"]), _fmt_apy(f["net_apy"])))
    parts.append("%s supplied, %s liquidity." % (_fmt_usd(f["tvl_usd"]), _fmt_usd(f["liquidity_usd"])))
    if f.get("lltv") is not None:
        parts.append("LLTV %.0f%%." % (float(f["lltv"]) * 100))
    bd = float(f.get("bad_debt_usd") or 0)
    rbd = float(f.get("realized_bad_debt_usd") or 0)
    if bd or rbd:
        parts.append("bad debt: %s outstanding, %s realised." % (_fmt_usd(bd), _fmt_usd(rbd)))
    if f.get("fails"):
        parts.append("flags: %s." % ", ".join(f["fails"]))
    return " ".join(parts)


def _phrase_scorecard(f):
    if not f["found"]:
        return "No runs are recorded yet, so there is no scorecard to report."
    v = f["verdicts"]
    order = ["REAL", "CAUTION", "AVOID"]
    bits = ["%s: %s" % (k, v.get(k, 0)) for k in order]
    return ("Across %d markets in the newest run, %s." % (f["n_markets"], ", ".join(bits)))


def _phrase_changes(f):
    if not f["found"]:
        return "No transition log to report."
    if not f["events"]:
        return "No changes in the last %d intervals." % f["n_intervals"]
    head = "%d change(s) across %d intervals:" % (f["n_events"], f["n_intervals"])
    lines = []
    for e in f["events"][:5]:
        lines.append("- %s" % (e["detail"] or e["kind"] or "event"))
    return head + "\n" + "\n".join(lines)


def _load_dex():
    """DEX fee ranking from screener/dex_pools.json (written by dex_pools.py)."""
    import screener.dex_pools as dex_pools
    d = dex_pools.load()
    return d or {"pools": [], "top_fee_pool": None}


def retrieve_dex(q):
    d = _load_dex()
    ql = q.lower()
    pools = d.get("pools", [])
    # filter by a token/venue mentioned in the question, if any
    syms = re.findall(r"\b(cbbtc|aero|weth|usdc|usdt|dai|btc|eth)\b", ql)
    if syms:
        pools = [p for p in pools
                 if any(s in p.get("name", "").lower() for s in syms)]
    return {"found": True, "count": len(pools), "pools": pools[:10],
            "top_fee_pool": d.get("top_fee_pool"),
            "note": d.get("note", "")}


def _phrase_dex(f):
    if not f.get("pools"):
        return "No DEX pool fee data is recorded. Run screener/dex_pools.py to build the feed."
    lines = []
    top = f.get("top_fee_pool")
    if top:
        lines.append("Top pool by 24h fee: %s (%s/day fees, %s volume @ %.2f%%)." % (
            top["name"], _fmt_usd(top["fee_24h_usd"]),
            _fmt_usd(top["volume_24h_usd"]), top["fee_tier"] * 100))
    for p in f["pools"]:
        lines.append("- %s: %s/day fees (%s vol @ %.2f%%, %s liquidity)." % (
            p["name"], _fmt_usd(p["fee_24h_usd"]),
            _fmt_usd(p["volume_24h_usd"]), p["fee_tier"] * 100,
            _fmt_usd(p["reserve_usd"])))
    return "\n".join(lines)


HELP_TEXT = (
    "I answer from Aegis's recorded data, nothing else. You can ask: "
    "'what is the verdict on cbBTC?', 'how many markets are REAL?', or 'what changed?'. "
    "Every number comes from the latest immutable run; I will not invent figures."
)


def phrase(intent, facts):
    return {
        "lookup": _phrase_lookup,
        "scorecard": _phrase_scorecard,
        "changes": _phrase_changes,
        "dex": _phrase_dex,
        "help": lambda f: HELP_TEXT,
    }[intent](facts)


def answer(question):
    intent = classify(question)
    retriever = {"lookup": retrieve_lookup, "scorecard": lambda q: retrieve_scorecard(),
                 "changes": retrieve_changes, "dex": retrieve_dex,
                 "help": lambda q: {"found": True}}[intent]
    facts = retriever(question)
    text = phrase(intent, facts)
    return {
        "answer": text,
        "intent": intent,
        "facts": facts,
        "model": MODEL if LLM_ENABLED else "none",
    }


def selftest():
    fails = []
    def ck(name, cond, detail=""):
        print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
        if not cond:
            fails.append(name)
            if detail:
                print("      " + str(detail))

    r = answer("what is the verdict on cbBTC?")
    ck("lookup intent resolved", r["intent"] == "lookup", r["intent"])
    ck("lookup answer non-empty", bool(r["answer"].strip()))
    ck("lookup returns a verdict fact", isinstance(r["facts"].get("verdict"), str),
        r["facts"].get("verdict"))

    r = answer("how many markets are REAL?")
    ck("scorecard intent resolved", r["intent"] == "scorecard", r["intent"])
    ck("scorecard carries counts", isinstance(r["facts"].get("verdicts"), dict))

    r = answer("what changed recently?")
    ck("changes intent resolved", r["intent"] == "changes", r["intent"])
    ck("changes carries events list", isinstance(r["facts"].get("events"), list))

    r = answer("tell me the meaning of life")
    ck("unknown question falls to a known intent",
       r["intent"] in ("help", "lookup", "scorecard", "changes"), r["intent"])

    old = os.environ.get("AEGIS_CHAT_MODEL")
    os.environ["AEGIS_CHAT_MODEL"] = "none"
    try:
        import chat_api
        chat_api.LLM_ENABLED = False
        r = chat_api.answer("what is the verdict on cbBTC?")
        ck("answer correct with model disabled", r["intent"] == "lookup" and r["answer"].strip())
    finally:
        if old is None:
            os.environ.pop("AEGIS_CHAT_MODEL", None)
        else:
            os.environ["AEGIS_CHAT_MODEL"] = old

    print()
    if fails:
        print("  %d FAILURE(S)" % len(fails))
        return 1
    print("  chat_api selftest passed")
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    for q in sys.argv[1:]:
        r = answer(q)
        print("Q:", q)
        print(r["answer"])
        print()

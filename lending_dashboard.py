#!/usr/bin/env python3
"""Lending screen data for the dashboard, plus the raw JSON export.

Read-only. No predictions. Every figure is a measurement of CURRENT state, and the section is
labelled as such so that nothing here can be read as a forecast.

Numbers are re-derived at build time from lending_screen.json and morpho_markets.json, so the
page cannot drift from the data.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE   # this module lives in the project root alongside the JSON files


def load():
    """Prefer the latest immutable run; fall back to the flat files.

    Reading the latest run is what makes state isolation real: the dashboard never sees a
    half-written file, and every prior run stays on disk as an auditable fact.
    """
    out = {"provenance": None, "run": None}
    try:
        import provenance
        d = provenance.latest_run()
        if d:
            out["run"] = os.path.basename(d)
            out["screen"] = json.load(open(os.path.join(d, "screen.json")))
            out["markets"] = json.load(open(os.path.join(d, "markets.json")))
            meta = json.load(open(os.path.join(d, "meta.json")))
            out["provenance"] = meta.get("provenance")
            out["meta"] = meta
            return out
    except Exception:
        pass
    for key, fn in (("screen", "lending_screen.json"), ("markets", "morpho_markets.json")):
        try:
            out[key] = json.load(open(os.path.join(ROOT, fn)))
        except Exception:
            out[key] = None
    return out


def summary():
    d = load()
    scr = d.get("screen")
    if not scr:
        return None
    markets = {m["market_id"]: m for m in (d.get("markets") or [])}
    counts = {}
    for r in scr:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    reasons = {}
    for r in scr:
        for f in r["fails"]:
            reasons[f] = reasons.get(f, 0) + 1
    # BAD_DEBT fires on unrealised OR realised loss, so the table must show both.
    # A market with $132 realised and $0 unrealised was being omitted from the table
    # while still counting in the rule tally -- the numbers disagreed.
    bd = [r for r in scr if (r.get("bad_debt_usd") or 0) > 0
          or (r.get("realized_bad_debt_usd") or 0) > 0]
    bd.sort(key=lambda r: -((r.get("bad_debt_usd") or 0) + (r.get("realized_bad_debt_usd") or 0)))
    for r in bd:
        m = markets.get(r["market_id"]) or {}
        r["_oracle"] = m.get("oracle")
        r["_collateral_addr"] = m.get("collateral_address")
        r["_warnings_red"] = m.get("warnings_red") or []
        r["_warnings_yellow"] = m.get("warnings_yellow") or []
        r["_liquidity"] = m.get("liquidity_usd")
    return {
        "n": len(scr), "counts": counts, "reasons": reasons, "bad_debt": bd,
        "real": [r for r in scr if r["verdict"] == "REAL"],
        "all": scr,          # every market, for the at-a-glance summary
        "markets": markets,
    }


def render_glance(H, esc):
    """The at-a-glance summary table: every market in six clean columns, dense fields in the
    per-row drawer. This is the landing view -- the screen a curator sees first. It lives in its
    own top-level section (data-section='summary') so the Summary tab can show it alone."""
    s = summary()
    if not s:
        return
    all_m = sorted(s["all"], key=lambda r: -(r.get("tvl_usd") or 0))
    VC = {"REAL": "ok", "CAUTION": "warn", "AVOID": "bad"}
    H.append("<h2 id='sec-summary' class='anchorable'>Markets at a glance</h2>")
    H.append("<div class='sub'>Clean summary, dense drill-down. "
             "The verdict is the one thing a curator needs at a glance; utilisation, size and "
             "net APY are the context. Tap a row for LLTV, bad debt, volatility and the flags "
             "behind it.</div>")
    H.append("<table class='dense'><tr><th>collateral</th><th>verdict</th><th>util</th>"
             "<th>supplied</th><th>net APY</th><th>liquidity</th></tr>")
    for r in all_m:
        v = r.get("verdict") or ""
        _extra = ";".join([
            "LLTV:%s" % ("%.1f%%" % (r["lltv"] * 100) if r.get("lltv") is not None else ""),
            "bad debt:$%s" % (format(int(r.get("bad_debt_usd") or 0), ",")),
            "realised bad debt:$%s" % (format(int(r.get("realized_bad_debt_usd") or 0), ",")),
            "sigma to breach:%s" % ("%.1f daily moves" % r["sigma_to_breach"]
                                    if r.get("sigma_to_breach") is not None else ""),
            "annualised vol:%s" % ("%.1f%%" % r["ann_vol_pct"]
                                   if r.get("ann_vol_pct") is not None else ""),
            "daily vol:%s" % ("%.2f%%" % r["daily_vol_pct"]
                              if r.get("daily_vol_pct") is not None else ""),
            "flags:%s" % (", ".join(r.get("fails") or [])),
            "reasons:%s" % (", ".join(r.get("reasons") or [])),
        ])
        _extra = ";".join(p for p in _extra.split(";") if p.split(":", 1)[-1].strip())
        H.append("<tr%s data-verdict='%s'><td>%s</td><td><span class='pill %s'>%s</span></td>"
                 "<td>%.1f%%</td><td>$%s</td><td class='ok'>%.2f%%</td><td>$%s</td></tr>"
                 % (" data-extra='%s'" % esc(_extra) if _extra else "",
                    esc(v),
                    esc(r.get("collateral")), VC.get(v, "dim"), esc(v),
                    (r.get("utilization") or 0) * 100,
                    format(int(r.get("tvl_usd") or 0), ","),
                    r.get("net_apy") or 0,
                    format(int(r.get("liquidity_usd") or 0), ",")))
    H.append("</table>")


def render(H, esc):
    """Append the lending section to the report. H is the list of HTML fragments."""
    s = summary()
    if not s:
        return
    c = s["counts"]

    H.append("<h2 id='sec-lending' class='anchorable'>Lending markets &mdash; current state risk assessment</h2>")
    H.append("<div class='sub'>Seven structural checks applied to <b>%d</b> USDC-denominated Morpho "
             "Blue markets on Base. <b>Every figure below is a measurement of present state.</b> "
             "Nothing here is a forecast, and no claim is made about what any market will do.</div>" % s["n"])

    n_real = sum(1 for r in s["bad_debt"] if (r.get("realized_bad_debt_usd") or 0) > 0)
    n_out = len(s["bad_debt"]) - n_real
    H.append("<div class='big'>"
             "<div class='card'><div class='n ok'>%d</div><div class='l'>REAL</div></div>"
             "<div class='card'><div class='n warn'>%d</div><div class='l'>CAUTION</div></div>"
             "<div class='card'><div class='n bad'>%d</div><div class='l'>AVOID</div></div>"
             "<div class='card'><div class='n bad'>%d</div><div class='l'>bad debt outstanding</div></div>"
             "<div class='card'><div class='n bad'>%d</div><div class='l'>loss realised</div></div>"
             "</div>" % (c.get("REAL", 0), c.get("CAUTION", 0), c.get("AVOID", 0), n_out, n_real))

    # rule breakdown
    prov = (load() or {}).get("provenance")
    if prov:
        H.append("<div class='sub' style='margin-top:6px'><b>Lending Provenance:</b> Base block "
                 "<code>%s</code> &middot; ingested <code>%s</code> &middot; %d markets &middot; "
                 "sha256 <code>%s</code> &middot; run <code>%s</code>. Each run is written to its "
                 "own immutable directory and replayed to confirm it reproduces exactly.</div>"
                 % (prov.get("block_number"), prov.get("fetched_at"), prov.get("row_count") or 0,
                    (prov.get("content_sha256") or "")[:16], (load() or {}).get("run")))

    ORDER = ("BAD_DEBT", "PROTOCOL_RED", "LOCKED", "OUTLIER", "HIGH_LLTV", "THIN", "NO_YIELD")
    H.append("<h3 style='font-size:13px;margin:16px 0 6px'>What each rule caught</h3>")
    H.append("<table><tr><th>rule</th><th>meaning</th><th>markets</th></tr>")
    MEAN = {
        "BAD_DEBT": "bad debt outstanding or realised &mdash; hard exclusion",
        "PROTOCOL_RED": "Morpho's own RED warning (consumed, not re-derived)",
        "LOCKED": "utilisation above 95% &mdash; depositors cannot exit",
        "OUTLIER": "net APY above 100% &mdash; not a lending rate",
        "HIGH_LLTV": "LLTV above 94.5% &mdash; thin margin against a depeg",
        "THIN": "below $1M supplied",
        "NO_YIELD": "net APY below 0.1%",
    }
    for k in ORDER:
        if s["reasons"].get(k):
            H.append("<tr><td class='dim'>%s</td><td>%s</td><td>%d</td></tr>"
                     % (esc(k), MEAN[k], s["reasons"][k]))
    H.append("</table>")

    # the bad debt table - the hard flags
    if s["bad_debt"]:
        H.append("<h3 style='font-size:13px;margin:18px 0 6px'>Markets carrying bad debt</h3>")
        H.append("<div class='sub' style='margin-bottom:6px'><b>Outstanding</b> is debt owed but "
                 "not yet written off &mdash; it can still be recovered. <b>Realised</b> is loss "
                 "already taken. The two are not interchangeable, and an outstanding balance is "
                 "not a realised loss.</div>")
        H.append("<table><tr><th>collateral</th><th>supplied</th><th>unrealised</th>"
                 "<th>realised</th><th>% lost</th><th>liquidity</th><th>util</th><th>LLTV</th>"
                 "<th>Morpho flags</th></tr>")
        for r in s["bad_debt"]:
            tvl = r.get("tvl_usd") or 0
            bd = r.get("bad_debt_usd") or 0
            rbd = r.get("realized_bad_debt_usd") or 0
            tot = bd + rbd
            pct = (tot / tvl * 100) if tvl else 0
            red = ", ".join(sorted(set(r.get("_warnings_red") or []))) or "-"
            H.append("<tr><td>%s</td><td>$%s</td><td class='bad'>$%s</td><td class='bad'>$%s</td>"
                     "<td class='bad'>%.1f%%</td><td>$%.4f</td><td>%.1f%%</td><td>%.1f%%</td>"
                     "<td class='bad'>%s</td></tr>"
                     % (esc(r.get("collateral")), format(int(tvl), ","), format(int(bd), ","),
                        format(int(rbd), ","), pct,
                        r.get("_liquidity") or 0, (r.get("utilization") or 0) * 100,
                        (r.get("lltv") or 0) * 100, esc(red)))
        H.append("</table>")

    # the markets that pass
    if s["real"]:
        s["real"].sort(key=lambda r: -(r.get("tvl_usd") or 0))
        H.append("<h3 style='font-size:13px;margin:18px 0 6px'>Markets passing all seven checks</h3>")
        H.append("<table><tr><th>collateral</th><th>supplied</th><th>util</th><th>net APY</th>"
                 "<th>LLTV</th><th>liquidity</th></tr>")
        for r in s["real"][:14]:
            # DRAWER TELEMETRY, NOT A REPEAT (dense-table rule). The drawer must add what the
            # row does not show. Carried as data-extra K/V pairs the JS unpacks, so the visible
            # table stays six columns and the risk numbers still reach the reader. Values are
            # rounded to what the row's own precision supports; blank when absent, never 0.
            _extra = ";".join([
                "sigma to breach:%s" % (("%.1f daily moves" % r["sigma_to_breach"])
                                        if r.get("sigma_to_breach") is not None else ""),
                "annualised vol:%s%%" % ("%.1f" % r["ann_vol_pct"] if r.get("ann_vol_pct") is not None else ""),
                "daily vol:%s%%" % ("%.2f" % r["daily_vol_pct"] if r.get("daily_vol_pct") is not None else ""),
                "verdict:%s" % (r.get("verdict") or ""),
                "flags:%s" % (", ".join(r.get("fails") or [])),
                "yellow warnings:%s" % (", ".join(r.get("warnings_yellow") or [])),
            ])
            # strip pairs whose value came out empty, so an absent field renders nothing at all
            _extra = ";".join(p for p in _extra.split(";") if p.split(":", 1)[-1].strip())
            H.append("<tr%s><td>%s</td><td>$%s</td><td>%.1f%%</td><td class='ok'>%.2f%%</td>"
                     "<td>%.1f%%</td><td>$%s</td></tr>"
                     % (" data-extra='%s'" % esc(_extra) if _extra else "",
                        esc(r.get("collateral")), format(int(r.get("tvl_usd") or 0), ","),
                        (r.get("utilization") or 0) * 100, r.get("net_apy") or 0,
                        (r.get("lltv") or 0) * 100, format(int(r.get("liquidity_usd") or 0), ",")))
        H.append("</table>")

    H.append("<div class='sub' style='margin-top:8px'>Raw data: <code>lending_screen.json</code> "
             "and <code>morpho_markets.json</code>. Source: Morpho Blue GraphQL API, chain 8453. "
             "<b>The transfer of rules from AMM pools to lending markets is documented in "
             "<code>PHASE1_RESULTS.md</code>, including which checks do not transfer.</b></div>")

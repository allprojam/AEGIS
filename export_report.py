#!/usr/bin/env python3
"""export_report.py - render one run as a self-contained Forensic Audit tear sheet.

Reads a single runs/<iso>/ and writes ONE static HTML file. No server, no network, no
dependencies beyond the standard library. It renders what the run contains and nothing else:
no projection, no recommendation, no forecast.

    python3 export_report.py                     # newest run -> audits/<iso>.html
    python3 export_report.py runs/<iso>
    python3 export_report.py runs/<iso> -o out.html
    python3 export_report.py --list

DESIGN CONSTRAINTS, each a decision rather than a default:

  1. OFFLINE AND SELF-CONTAINED. No CDN, no fonts, no analytics, no external request of any
     kind. A risk audit that phones home is not an audit. Open the file with no network and
     it renders identically.

  2. OUTSTANDING vs REALISED kept strictly separate. `bad_debt_usd` is debt owed;
     `realized_bad_debt_usd` is loss written off. USR carries $34.8M outstanding and $0
     realised. Collapsing them overstates realised loss by five orders of magnitude -- a bug
     that was live in the dashboard and that this file exists partly to prevent recurring.

  3. THE NON-CLAIM IS IN THE DOCUMENT, not in a covering message. Every number is a
     measurement of present state. The screen reads structure; it cannot read a compromised
     private key. USR is the worked example and is labelled as post-hoc.

  4. VERIFIABLE WITHOUT TRUSTING THIS SCRIPT. The sha256 of each artefact is printed in the
     page, so a reader can hash the run directory and compare. Nothing asks to be believed.
"""
import hashlib, html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
OUTD = os.path.join(HERE, "audits")

ORDER = ("BAD_DEBT", "PROTOCOL_RED", "LOCKED", "OUTLIER", "HIGH_LLTV", "THIN", "NO_YIELD")
MEAN = {
    "BAD_DEBT": "bad debt outstanding or realised &mdash; hard exclusion",
    "PROTOCOL_RED": "Morpho's own RED warning (consumed, not re-derived)",
    "LOCKED": "utilisation above 95% &mdash; depositors cannot exit",
    "OUTLIER": "net APY above 100% &mdash; not a lending rate",
    "HIGH_LLTV": "LLTV above 94.5% &mdash; thin margin against a depeg",
    "THIN": "below $1M supplied",
    "NO_YIELD": "net APY below 0.1%",
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def sha256_file(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except Exception:
        return None


def list_runs():
    if not os.path.isdir(RUNS):
        return []
    return sorted(d for d in os.listdir(RUNS) if os.path.isdir(os.path.join(RUNS, d)))


def load(run):
    d = os.path.join(RUNS, run)
    out = {"run": run, "dir": d}
    for n, k in (("meta.json", "meta"), ("screen.json", "screen"), ("markets.json", "markets")):
        p = os.path.join(d, n)
        if not os.path.exists(p):
            raise SystemExit("run %s is missing %s" % (run, n))
        out[k] = json.load(open(p))
        out["sha_" + n] = sha256_file(p)
    return out


def usd(v):
    return "${:,.0f}".format(v or 0)


def pct(v, places=1):
    return ("%.*f%%" % (places, (v or 0) * 100)) if v is not None else "&mdash;"


def render(r):
    m = r["meta"] if isinstance(r["meta"], dict) else {}
    prov = m.get("provenance") or {}
    scr = r["screen"]
    counts = {}
    for x in scr:
        counts[x.get("verdict")] = counts.get(x.get("verdict"), 0) + 1

    bad = [x for x in scr if (x.get("bad_debt_usd") or 0) > 0
           or (x.get("realized_bad_debt_usd") or 0) > 0]
    bad.sort(key=lambda x: -((x.get("bad_debt_usd") or 0) + (x.get("realized_bad_debt_usd") or 0)))
    tot_out = sum(x.get("bad_debt_usd") or 0 for x in bad)
    tot_real = sum(x.get("realized_bad_debt_usd") or 0 for x in bad)
    hard = [x for x in scr if any(f in ("BAD_DEBT", "PROTOCOL_RED", "LOCKED")
                                  for f in (x.get("fails") or []))]

    thin = []
    for x in scr:
        sg = x.get("sigma_to_breach")
        if sg is not None and sg < 2.0:
            thin.append(x)
    thin.sort(key=lambda x: x.get("sigma_to_breach") or 0)

    H = []
    A = H.append
    A("<!doctype html><html lang=en><head><meta charset=utf-8>")
    A("<meta name=viewport content='width=device-width,initial-scale=1'>")
    A("<title>Aegis Forensic Audit &mdash; %s</title>" % esc(r["run"]))
    A("""<style>
:root{--bg:#0e1116;--fg:#e6edf3;--dim:#8b949e;--line:#21262d;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.wrap{max-width:940px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:30px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:14px;margin:20px 0 6px}
.sub{color:var(--dim);font-size:13px;margin:6px 0}
code{background:#161b22;padding:1px 5px;border-radius:3px;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
.card{flex:1;min-width:110px;background:#161b22;border:1px solid var(--line);border-radius:6px;padding:12px}
.card .n{font-size:24px;font-weight:700;line-height:1.1}
.card .l{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;margin-top:3px}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.banner{border-left:3px solid var(--acc);background:#161b22;padding:12px 14px;border-radius:0 5px 5px 0;margin:14px 0;font-size:13px}
.banner b{color:var(--acc)}
.meta{font-size:12px;color:var(--dim);line-height:1.9}
.meta code{font-size:11px}
.foot{margin-top:36px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--dim)}
</style></head><body><div class=wrap>""")

    A("<h1>Aegis Forensic Audit</h1>")
    A("<div class=sub>Morpho Blue USDC markets on Base &middot; run <code>%s</code> "
      "&middot; %d markets screened</div>" % (esc(r["run"]), len(scr)))

    A("<div class='banner'><b>This is a measurement, not a forecast.</b> Every figure is the "
      "state of these markets at the block below. No claim is made about what any market will "
      "do. The screen reads structure &mdash; reserves, utilisation, oracle provenance, "
      "collateral-to-volatility margin. <b>It cannot read a compromised private key</b>, which "
      "is what broke USR.</div>")

    A("<h2>Executive scorecard</h2>")
    A("<div class=cards>"
      "<div class=card><div class='n ok'>%d</div><div class=l>REAL</div></div>"
      "<div class=card><div class='n warn'>%d</div><div class=l>CAUTION</div></div>"
      "<div class=card><div class='n bad'>%d</div><div class=l>AVOID</div></div>"
      "<div class=card><div class='n bad'>%d</div><div class=l>bad debt outstanding</div></div>"
      "<div class=card><div class='n bad'>%d</div><div class=l>loss realised</div></div>"
      "<div class=card><div class='n'>%d</div><div class=l>hard-flagged</div></div>"
      "</div>" % (counts.get("REAL", 0), counts.get("CAUTION", 0), counts.get("AVOID", 0),
                  sum(1 for x in bad if (x.get("bad_debt_usd") or 0) > 0),
                  sum(1 for x in bad if (x.get("realized_bad_debt_usd") or 0) > 0),
                  len(hard)))

    A("<h2>Provenance</h2>")
    A("<div class=meta>")
    A("block number <code>%s</code><br>" % esc(prov.get("block_number")))
    A("ingested <code>%s</code> &middot; written <code>%s</code><br>"
      % (esc(prov.get("fetched_at") or m.get("fetched_at")), esc(m.get("written_at"))))
    A("source <code>%s</code> &middot; chain <code>%s</code><br>"
      % (esc(prov.get("source_endpoint") or m.get("source_endpoint")),
         esc(prov.get("chain_id") or m.get("chain_id"))))
    A("row count <code>%s</code><br>" % esc(prov.get("row_count") or len(scr)))
    A("</div>")
    A("<h3 style='font-size:13px'>Verifiable checksums</h3>")
    A("<div class=sub>Hash the run directory yourself and compare. This audit does not ask to "
      "be believed.</div>")
    A("<table><tr><th>artefact</th><th>sha256</th></tr>")
    for n in ("markets.json", "screen.json", "meta.json"):
        A("<tr><td><code>%s</code></td><td><code>%s</code></td></tr>"
          % (n, esc(r.get("sha_" + n) or "&mdash;")))
    A("</table>")
    A("<div class=sub>Content sha256 (markets + screen): <code>%s</code></div>"
      % esc((prov.get("content_sha256") or "")[:64]))

    A("<h2>What each rule caught</h2>")
    reasons = {}
    for x in scr:
        for f in (x.get("fails") or []):
            reasons[f] = reasons.get(f, 0) + 1
    A("<table><tr><th>rule</th><th>meaning</th><th class=num>markets</th></tr>")
    for k in ORDER:
        if reasons.get(k):
            A("<tr><td class=dim><code>%s</code></td><td>%s</td><td class=num>%d</td></tr>"
              % (esc(k), MEAN[k], reasons[k]))
    A("</table>")

    if bad:
        A("<h2>Bad debt</h2>")
        A("<div class=sub><b>Outstanding</b> is owed but not written off and may still be "
          "recovered. <b>Realised</b> is loss already taken. They are not interchangeable.</div>")
        A("<table><tr><th>collateral</th><th class=num>supplied</th>"
          "<th class=num>outstanding</th><th class=num>realised</th>"
          "<th class=num>% of supplied</th><th class=num>util</th><th class=num>LLTV</th>"
          "<th>verdict</th></tr>")
        for x in bad:
            tvl = x.get("tvl_usd") or 0
            o = x.get("bad_debt_usd") or 0
            rl = x.get("realized_bad_debt_usd") or 0
            A("<tr><td><b>%s</b></td><td class=num>%s</td><td class=num>%s</td>"
              "<td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
              "<td class=num>%s</td><td class='%s'>%s</td></tr>"
              % (esc(x.get("collateral")), usd(tvl), usd(o), usd(rl),
                 pct((o + rl) / tvl) if tvl else "&mdash;",
                 pct(x.get("utilization")), pct(x.get("lltv")),
                 "bad" if x.get("verdict") == "AVOID" else "warn",
                 esc(x.get("verdict"))))
        A("</table>")
        A("<div class=sub>Total outstanding %s &middot; total realised %s. "
          "<b>The realised figure is the loss actually taken.</b></div>"
          % (usd(tot_out), usd(tot_real)))

    if thin:
        A("<h2>Collateral-to-volatility margin</h2>")
        A("<div class=sub>margin = 1 &minus; LLTV &middot; daily vol = annualised / &radic;365 "
          "&middot; sigma to breach = margin / daily vol. Below 2.0 sigma, a routine daily move "
          "can breach the position before a liquidator acts.</div>")
        A("<table><tr><th>collateral</th><th class=num>LLTV</th><th class=num>margin</th>"
          "<th class=num>daily vol</th><th class=num>sigma to breach</th><th>verdict</th></tr>")
        for x in thin[:14]:
            lv = x.get("lltv") or 0
            A("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td>"
              "<td class=num>%.2f%%</td><td class='num bad'>%.2f</td><td>%s</td></tr>"
              % (esc(x.get("collateral")), pct(lv), pct(1 - lv),
                 x.get("daily_vol_pct") or 0, x["sigma_to_breach"], esc(x.get("verdict"))))
        A("</table>")

    if hard:
        A("<h2>Hard exclusions</h2>")
        A("<div class=sub>Markets failing BAD_DEBT, PROTOCOL_RED or LOCKED, with the reason "
          "the screen recorded.</div>")
        A("<table><tr><th>collateral</th><th class=num>LLTV</th><th class=num>util</th>"
          "<th>why</th></tr>")
        for x in hard[:12]:
            why = "; ".join((x.get("reasons") or [])[:2]) or ", ".join(x.get("fails") or [])
            A("<tr><td><b>%s</b></td><td class=num>%s</td><td class=num>%s</td><td>%s</td></tr>"
              % (esc(x.get("collateral")), pct(x.get("lltv")), pct(x.get("utilization")),
                 esc(why)[:180]))
        A("</table>")

    A("<div class=foot>")
    A("<b>What this audit cannot do.</b> It measures the state of these markets at block "
      "%s. It does not predict losses, and it did not predict the USR exploit, which was a key "
      "compromise rather than a structural failure &mdash; a screen reads structure. "
      "Pool-screen flags do not separate survivors from failures at n=122 (52.4%% vs 43.8%%, "
      "overlapping intervals); that is measured, not assumed.<br><br>" % esc(prov.get("block_number")))
    A("Generated offline from <code>runs/%s/</code> with no network access. "
      "Re-run <code>python3 export_report.py %s</code> to reproduce this file exactly."
      % (esc(r["run"]), esc(r["run"])))
    A("</div>")
    A("</div></body></html>")
    return "\n".join(H)


def main():
    args = list(sys.argv[1:])
    if "--list" in args:
        for d in list_runs():
            print("  %s" % d)
        return 0

    out = None
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    runs = list_runs()
    if not runs:
        print("no runs available")
        return 1
    run = args[0].rstrip("/").split("/")[-1] if args else runs[-1]
    if run not in runs:
        print("run %r not found. available: %s" % (run, ", ".join(runs[-5:])))
        return 1

    r = load(run)
    page = render(r)
    os.makedirs(OUTD, exist_ok=True)
    path = out or os.path.join(OUTD, "%s.html" % run)
    with open(path, "w") as fh:
        fh.write(page)

    scr = r["screen"]
    bad = [x for x in scr if (x.get("bad_debt_usd") or 0) > 0
           or (x.get("realized_bad_debt_usd") or 0) > 0]
    print("wrote %s (%d bytes)" % (path, len(page)))
    print("  run         %s" % run)
    print("  block       %s" % (r["meta"].get("provenance") or {}).get("block_number"))
    print("  markets     %d" % len(scr))
    print("  outstanding %s" % usd(sum(x.get("bad_debt_usd") or 0 for x in bad)))
    print("  realised    %s" % usd(sum(x.get("realized_bad_debt_usd") or 0 for x in bad)))
    print("  self-contained: no external requests")
    return 0


if __name__ == "__main__":
    sys.exit(main())

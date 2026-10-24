#!/usr/bin/env python3
"""Build the deliverable: links, live audit with flags, audit card, pay-per-audit pricing."""
import json, html, time, os, sys, urllib.request, glob
# BOTH paths anchored to this file, never to the cwd. `sys.path.insert(0,"screener")` was
# RELATIVE: run from a different directory it resolved somewhere else, and when it did resolve
# it put screener/ FIRST -- so `import run_history` picked up screener/run_history.py, whose
# __file__ is the symlink and whose HERE therefore resolved to screener/. It then read
# screener/runs instead of the canonical runs/, found 0 changes, and the What-changed table
# silently rendered nothing with no error. Exactly the shadow-tree failure, one level down.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# ROOT FIRST so root modules win; screener/ after, for the tools that only exist there.
for _p in (_ROOT, _HERE):
    while _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)
from links import link_set, _ok_addr
from audit import load_protocols, assess

UA={"User-Agent":"Mozilla/5.0","Accept":"application/json"}
def derive_numbers():
    """Re-derive the two headline numbers from raw data. None if the files are absent."""
    import math
    cohort_f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "structural_backtest_v2.jsonl")
    decay_f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "apy_decay.json")
    if not (os.path.exists(cohort_f) and os.path.exists(decay_f)):
        return None
    cohort = []
    for line in open(cohort_f):
        try:
            cohort.append(json.loads(line))
        except Exception:
            pass
    scored = [r for r in cohort if r["outcome"] in ("FAILED", "IMPAIRED", "SURVIVED")]
    if not scored:
        return None
    bleed = sum(1 for r in scored if r["outcome"] in ("FAILED", "IMPAIRED"))
    decay = json.load(open(decay_f))
    hy = [r for r in decay if (r.get("advertised") or 0) > 8]
    if not hy:
        return None
    beat = sum(1 for r in hy if (r.get("realized") or 0) > (r.get("advertised") or 0))
    rets = sorted(r["retention"] for r in hy if r.get("retention") is not None)
    median_ret = rets[len(rets) // 2] * 100 if rets else 0.0

    def wilson(k, n, z=1.96):
        if n == 0:
            return (0.0, 0.0)
        p = k / n; d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return (max(0.0, c - h), min(1.0, c + h))

    lo, hi = wilson(bleed, len(scored))
    lo2, hi2 = wilson(beat, len(hy))
    return dict(bleed_n=len(scored), bleed_k=bleed, bleed_pct=bleed / len(scored) * 100,
                bleed_lo=lo * 100, bleed_hi=hi * 100,
                hy_n=len(hy), hy_k=beat, hy_pct=beat / len(hy) * 100,
                hy_lo=lo2 * 100, hy_hi=hi2 * 100, median_ret=median_ret)


def esc(x): return html.escape(str(x)) if x is not None else ""

# Chains that get their own tab, plus a grouped catch-all.
# MEASURED REASON: 32 chains clear REAL + >$10M, but 17 of them have 1-2 pools. One tab per
# chain would be a worse data dump than the table it replaced -- 32 buttons to click through,
# most showing a single row. Tabs are generated for chains with >=3 pools, and everything below
# that threshold is reachable through "Other". The counts come from the data, so a chain gaining
# pools earns a tab without a code change.
CHAIN_TAB_MIN = 3

def _chain_tabs(res):
    """Buttons for each chain with enough qualifying pools, plus Other."""
    import collections as _c
    real = [r for r in res if r.get("verdict") == "REAL" and (r.get("tvl") or 0) > 10_000_000]
    cnt = _c.Counter(r.get("chain") for r in real)
    big = [c for c, n in cnt.most_common() if c and n >= CHAIN_TAB_MIN]
    small = sorted(c for c, n in cnt.items() if c and n < CHAIN_TAB_MIN)
    if small:
        big.append("__other__")
    out = []
    for c in big:
        lbl = "Other" if c == "__other__" else c
        slug = "other" if c == "__other__" else str(c).lower()
        out.append("<button class='tab' data-tab='chain:%s' aria-selected='false'>%s "
                   "<span class='dim'>%d</span></button>"
                   % (esc(slug), esc(lbl),
                      len(small) if c == "__other__" else cnt.get(c, 0)))
    return "".join(out)

def pill(word, kind=None):
    """Render a verdict word as a badge. ADDITIVE: the word itself is still present as text,
    so anything that greps for the verdict string keeps working. Purely presentational."""
    k = kind or {"REAL": "ok", "PROMISING": "ok", "MIXED": "warn", "NO_YIELD": "dim",
                 "AVOID": "bad", "CAUTION": "warn"}.get(str(word), "dim")
    return "<span class='pill %s'>%s</span>" % (k, esc(word))
def slim(r, raw):
    L=link_set({**r,"pool":raw.get("pool"),"underlyingTokens":raw.get("underlyingTokens") or []})
    return dict(symbol=r["symbol"], chain=r["chain"], project=r["project"],
        apy=round(r["apy"],2), base=round(r["base"],2), rew=round(r["rew"],2),
        tvl=round(r["tvl"]), count=r["count"], sigma=r.get("sigma"),
        verdict=r["verdict"], fails=r["fails"], reasons=r["reasons"],
        mean30=(raw.get("apyMean30d") if raw else None),
        # Fields the feed publishes and the page was throwing away. Carried so every row can
        # show the full picture rather than four columns: what the yield did over 1/7/30 days,
        # how much actually traded, the impermanent-loss estimate, the reward tokens, and the
        # contract address the reader would inspect.
        apy7=(raw.get("apyBase7d") if raw else None),
        d1=(raw.get("apyPct1D") if raw else None),
        d7=(raw.get("apyPct7D") if raw else None),
        d30=(raw.get("apyPct30D") if raw else None),
        vol1=(round(raw.get("volumeUsd1d") or 0) if raw else None),
        vol7=(round(raw.get("volumeUsd7d") or 0) if raw else None),
        il7d=(raw.get("il7d") if raw else None),
        ilrisk=(raw.get("ilRisk") if raw else None),
        exposure=(raw.get("exposure") if raw else None),
        meta=(raw.get("poolMeta") if raw else None),
        outlier=(raw.get("outlier") if raw else None),
        toks=([t for t in (raw.get("underlyingTokens") or []) if t and len(str(t)) == 42][:2]
              if raw else []),
        links=L)

def screen_pool_view(r):
    """screen.py result row -> the field names the page uses (tvl/rew/base)."""
    return {"verdict":r["verdict"], "symbol":r["symbol"], "project":r["project"],
            "apy":r["apy"], "tvl":r["tvl"], "sigma":r.get("sigma"), "count":r["count"]}

def build(out="report.html"):
    res=json.load(open("screener/results.json"))
    rq=urllib.request.Request("https://yields.llama.fi/pools",headers=UA)
    raw=json.loads(urllib.request.urlopen(rq,timeout=30).read().decode())["data"]
    byk={}
    for p in raw: byk[(p.get("chain"),p.get("project"),p.get("symbol"))]=p
    try: protos=load_protocols()
    except Exception: protos={}
    ar=[]
    try: ar=json.load(open("screener/audit_reads.json"))
    except Exception: pass

    real=[r for r in res if r["verdict"]=="REAL" and r["tvl"]>10_000_000]
    real.sort(key=lambda r:-r["apy"])

    # FLARE COVERAGE, rendered explicitly. Measured: the feed carries 58 Flare pools across 9
    # projects, and the page already embedded 26 of them -- yet only ONE reached this table,
    # because the table is the top 80 by APY of REAL pools above $10M and Flare's APY is
    # modest. Rendering top 200 changes nothing; top 445 shows two. So the APY sort buries an
    # entire ecosystem at any depth.
    #
    # These extra rows are marked data-extra='1' and are NOT part of the top-80 ranking, so the
    # headline numbers stay exactly what they were. The Flare tab reveals them. A pool is only
    # added if it already passed the screen (REAL or MIXED) and clears $1M -- the tab changes
    # what is VISIBLE, never what is judged.
    # ALL qualifying pools, not top-80. Measured: 445 pools clear REAL + >$10M across 32 chains,
    # and the APY sort buried whole ecosystems -- Flare contributed 1 of 96 rendered rows. The
    # rows were already downloaded in `DATA`, so rendering them adds markup (~460KB for all 445)
    # and no data. Chain tabs below select among them.
    import collections as _cc
    _big_chains = {str(c).lower() for c, n in
                   _cc.Counter(r["chain"] for r in real).items()
                   if c and n >= CHAIN_TAB_MIN}
    _top = real
    _seen = {(r["chain"], r["project"], r["symbol"]) for r in _top}
    _flare = [r for r in res
              if str(r.get("chain","")).lower() == "flare"
              and r["verdict"] in ("REAL", "MIXED")
              and r["tvl"] > 1_000_000
              and (r["chain"], r["project"], r["symbol"]) not in _seen]
    _flare.sort(key=lambda r: -r["tvl"])
    rows=[]
    for r in _top + _flare[:24]:
        src=byk.get((r["chain"],r["project"],r["symbol"]),{})
        rows.append((r, assess(r,protos) if protos else {"verdict":"?"}, link_set({**r,"pool":src.get("pool"),"underlyingTokens":src.get("underlyingTokens") or []})))

    # ---- embed: pools worth a lookup, plus an address index ----
    # Embed what a reader might actually look up. NO_YIELD pools pay nothing, so they
    # are only worth carrying when they are large enough to matter (>$5M); carrying all
    # 4,835 of them pushed the page to 5.3MB.
    keep=[r for r in res if r["verdict"] in ("REAL","PROMISING","MIXED")
          or (r["verdict"]=="NO_YIELD" and r["tvl"]>5_000_000) or r["tvl"]>1_000_000]
    keep.sort(key=lambda r:({"REAL":0,"PROMISING":1,"MIXED":2}.get(r["verdict"],3), -r["apy"]))
    embed=[]
    for r in keep:
        src=byk.get((r["chain"],r["project"],r["symbol"]),{})
        embed.append(slim(r,src))
    # Address index. THE POOL ADDRESS MATTERS MOST: it is what a DexScreener or GeckoTerminal
    # URL carries and what most people copy. The previous version indexed only the FIRST
    # underlying token of each pool, so pasting a pool's own address -- the common case --
    # always failed. It also indexed just one of the (usually two) tokens, so pasting the second
    # token of a pair failed too. Now: the pool address plus EVERY valid underlying token.
    addr={}
    n_pool=n_tok=0
    for i,e in enumerate(embed):
        src=byk.get((e["chain"],e["project"],e["symbol"]),{})
        pa=str(src.get("pool") or "").lower()
        if _ok_addr(pa):
            addr.setdefault(pa, i); n_pool+=1
        for t in (src.get("underlyingTokens") or []):
            if _ok_addr(t):
                if str(t).lower() not in addr: n_tok+=1
                addr.setdefault(str(t).lower(), i)
    print(f"  embedding {len(embed):,} pools, {len(addr):,} address index entries"
          f" ({n_pool:,} pool addresses, {n_tok:,} token addresses)")

    vc={}; fc={}
    for r in res:
        vc[r["verdict"]]=vc.get(r["verdict"],0)+1
        for f in r["fails"]: fc[f]=fc.get(f,0)+1
    fc=sorted(fc.items(), key=lambda kv:-kv[1])
    SOTY = derive_numbers()
    ts=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    H=[f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aegis Yield Screen</title>
<style>
body{{font:14px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
margin:0;padding:18px;background:#0d1117;color:#c9d1d9;max-width:1240px}}
h1{{font-size:21px;line-height:1.2;margin:0 0 4px}}h2{{font-size:13px;line-height:1.25;margin:26px 0 8px;color:#8b949e;
text-transform:uppercase;letter-spacing:.07em}}
.sub{{color:#8b949e;font-size:12px;line-height:1.55;margin-bottom:14px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th{{text-align:left;color:#8b949e;font-weight:600;border-bottom:1px solid #21262d;padding:6px 7px}}
td{{padding:6px 7px;border-bottom:1px solid #161b22}}tr:hover td{{background:#161b22}}
a{{color:#58a6ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.big{{display:flex;gap:9px;flex-wrap:wrap;margin:10px 0 6px}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:9px 13px;min-width:88px}}
.card .n{{font-size:18px;font-weight:600}}.card .l{{font-size:11px;color:#8b949e}}
.ok{{color:#3fb950}}.warn{{color:#d29922}}.bad{{color:#f85149}}.dim{{color:#8b949e}}
.note{{background:#161b22;border-left:3px solid #d29922;padding:11px 14px;margin:12px 0;
font-size:13px;border-radius:0 6px 6px 0}}
.tool{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin:16px 0}}
input,button{{font:13px inherit;background:#0d1117;color:#c9d1d9;border:1px solid #30363d;
border-radius:6px;padding:10px 12px}}
input{{width:100%;box-sizing:border-box;margin-bottom:10px}}
button{{background:#238636;border-color:#2ea043;color:#fff;cursor:pointer;font-weight:600}}
button:hover{{background:#2ea043}}
.v{{font-size:15px;font-weight:700;margin:12px 0 3px}}
ul.flags{{margin:8px 0;padding-left:4px;list-style:none}}ul.flags li{{margin:5px 0;font-size:12px}}
.result{{border-top:1px solid #21262d;padding-top:6px;margin-top:6px}}
.price{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}}
.tier{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;flex:1;min-width:210px}}
.tier h3{{margin:0 0 6px;font-size:15px}}.tier .p{{font-size:21px;font-weight:700;color:#3fb950}}
.tier ul{{padding-left:16px;margin:8px 0 0;font-size:12px;color:#8b949e}}

/* ---- modern terminal styling. ADDITIVE ONLY: every class above still exists unchanged,
   because audit_parity.py regexes the rendered HTML and lending_dashboard.py emits its own
   markup. New classes here, nothing renamed. ---- */
:root{{
  --bg:#0b0e14; --panel:#111721; --panel2:#151c28; --line:#20293a;
  --fg:#e6edf3; --dim:#8b96a8; --acc:#58a6ff;
  --ok:#3fb950; --warn:#d29922; --bad:#f85149;
}}
html{{scroll-behavior:smooth;scroll-padding-block-start:64px}}
body{{background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
  Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
h1{{font-weight:650;letter-spacing:-.02em}}
h2{{font-size:12px;color:var(--dim);line-height:1.3;letter-spacing:.1em;text-transform:uppercase;
  margin:34px 0 10px;padding-bottom:8px;border-bottom:1px solid var(--line)}}
a{{color:var(--acc)}}
/* sticky bar */
.topbar{{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:10px 18px;margin:-18px -18px 18px;background:rgba(11,14,20,.88);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
.topbar .brand{{font-weight:650;letter-spacing:-.01em}}
.topbar .stat{{font-size:11px;color:var(--dim);display:flex;align-items:center;gap:5px}}
.topbar .dot{{width:7px;height:7px;border-radius:50%;background:var(--ok);
  box-shadow:0 0 0 3px rgba(63,185,80,.15)}}
/* pill badges */
.pill{{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:999px;
  font-size:11px;font-weight:600;letter-spacing:.03em;white-space:nowrap;
  border:1px solid transparent;line-height:1.7}}
.pill.ok{{background:rgba(63,185,80,.12);color:#56d364;border-color:rgba(63,185,80,.35)}}
.pill.warn{{background:rgba(210,153,34,.12);color:#e3b341;border-color:rgba(210,153,34,.35)}}
.pill.bad{{background:rgba(248,81,73,.12);color:#ff7b72;border-color:rgba(248,81,73,.35)}}
.pill.dim{{background:rgba(139,150,168,.10);color:var(--dim);border-color:rgba(139,150,168,.25)}}
/* cards: rounded, subtle border, soft gradient */
.card{{background:linear-gradient(180deg,var(--panel2),var(--panel));
  border:1px solid var(--line);border-radius:8px;padding:12px 15px;min-width:96px;
  box-shadow:0 1px 0 rgba(255,255,255,.02) inset}}
.card .n{{font-size:21px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}
.card .l{{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;margin-top:2px}}
/* tables */
table{{background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
th{{position:relative;user-select:none}}
th[role=button]:hover{{color:var(--fg);background:rgba(88,166,255,.06)}}
th:focus-visible{{outline:2px solid var(--acc);outline-offset:-2px}}
.sort-arrow{{color:var(--acc);font-weight:700}}
tr:hover td{{background:rgba(88,166,255,.05)}}
td.num,.num{{text-align:right;font-variant-numeric:tabular-nums}}
/* injected per-table filter */
.tfilter{{width:100%;max-width:280px;margin:2px 0 8px;padding:7px 11px;font:13px inherit;
  color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:6px}}
.tfilter:focus{{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(88,166,255,.13)}}
.tfilter::placeholder{{color:var(--dim)}}
/* numeric alignment: tabular figures in a system monospace stack.
   A webfont (Inter/Geist) would be a network fetch; "zero external requests" is asserted by
   the test suite, so figures use the platform mono stack instead. Same alignment benefit,
   no request. */
.num,.dv,.card .n,.pill{{font-variant-numeric:tabular-nums}}
td.num,th.num{{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:12px}}
/* top bar controls */
.spacer{{flex:1}}
#global-search{{padding:6px 11px;font:13px inherit;color:var(--fg);background:var(--panel2);
  border:1px solid var(--line);border-radius:8px;min-width:190px}}
#global-search:focus{{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(88,166,255,.13)}}
.tabs{{display:inline-flex;gap:3px;background:var(--panel2);border:1px solid var(--line);
  border-radius:8px;padding:3px;max-width:100%;overflow-x:auto;flex-wrap:nowrap}}
.tabs::-webkit-scrollbar{{height:5px}}
.tabs::-webkit-scrollbar-thumb{{background:var(--line);border-radius:3px}}
.tab{{font:12px inherit;font-weight:600;color:var(--dim);background:transparent;border:0;
  padding:5px 12px;border-radius:6px;cursor:pointer;white-space:nowrap}}
.tab:hover{{color:var(--fg)}}
.tab.active{{background:rgba(88,166,255,.14);color:var(--acc);
  box-shadow:0 0 0 1px rgba(88,166,255,.3) inset}}
/* watchlist: a pin star per row and the global toggle */
.watch-toggle{{font:12px inherit;font-weight:600;color:var(--dim);background:var(--panel2);
  border:1px solid var(--line);border-radius:8px;padding:5px 11px;cursor:pointer;white-space:nowrap}}
.watch-toggle:hover{{color:var(--fg)}}
.watch-toggle.active{{background:rgba(88,166,255,.14);color:var(--acc);
  box-shadow:0 0 0 1px rgba(88,166,255,.3) inset}}
.watch-count{{font-size:11px;color:var(--dim);white-space:nowrap}}
.pin-cell{{width:28px;padding:2px 4px!important;text-align:center!important}}
.pin-head{{width:28px}}
.pin{{background:transparent;border:0;cursor:pointer;font-size:14px;line-height:1;color:var(--dim);
  padding:2px 4px;border-radius:4px}}
.pin:hover{{color:var(--acc);background:rgba(88,166,255,.12)}}
tr.pinned .pin{{color:var(--acc)}}
tr.pinned td:first-child{{box-shadow:inset 2px 0 0 var(--acc)}}
/* inline monogram badges - no images, so no network request */
.token-badge{{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;
  border-radius:50%;font-size:10px;font-weight:700;margin-right:7px;vertical-align:middle;
  border:1px solid var(--line);flex:0 0 auto;line-height:1}}
td .sym{{vertical-align:middle}}
/* micro-meters for util / LLTV / sigma */
.bar-wrap{{display:inline-block;width:54px;height:5px;background:var(--panel2);border-radius:3px;
  overflow:hidden;margin-left:8px;vertical-align:middle;border:1px solid var(--line)}}
.bar-fill{{display:block;height:100%;border-radius:3px}}
.bar-fill.safe{{background:var(--ok)}}
.bar-fill.warn{{background:var(--warn)}}
.bar-fill.bad{{background:var(--bad)}}
a.off{{color:#3fb950;font-weight:600}}
a.off:hover{{color:#56d364}}
.ocbtn{{font:12px inherit;font-weight:600;color:var(--acc);background:rgba(88,166,255,.10);
  border:1px solid rgba(88,166,255,.32);border-radius:6px;padding:5px 11px;cursor:pointer}}
.ocbtn:hover{{background:rgba(88,166,255,.18)}}
/* bounded scroll window: a 460-row table is a data dump however it is styled */
.scrollwin{{position:relative;border:1px solid var(--line);border-radius:8px;overflow:auto}}
.scrollwin>table{{border:0;border-radius:0;margin:0}}
.scrollwin thead th,.scrollwin tr:first-child th{{position:sticky;top:0;z-index:2;
  background:var(--panel);box-shadow:0 1px 0 var(--line)}}
/* tab strip and row control */
.rowctl{{display:inline-flex;align-items:center;gap:7px;font-size:11px;color:var(--dim)}}
.timectl{{display:inline-flex;align-items:center;gap:8px;font-size:11px;color:var(--dim)}}
.timectl input[type=range]{{width:140px;accent-color:var(--acc);cursor:pointer}}
.rowctl input[type=range]{{width:96px;accent-color:var(--acc);cursor:pointer}}
/* VERDICT SIDEBAR: quick-filter chips for the one column a curator scans for. Sits in the
   topbar so it is reachable from every tab; composes with search/chain/watch/time because
   all five funnel through one visibility executor. */
.vbar{{display:inline-flex;align-items:center;gap:5px;background:var(--panel2);
  border:1px solid var(--line);border-radius:8px;padding:3px}}
.vbar .vl{{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.07em;
  margin:0 3px 0 6px;font-weight:650}}
.vbtn{{font:11px inherit;font-weight:650;letter-spacing:.03em;color:var(--dim);
  background:transparent;border:1px solid transparent;border-radius:6px;padding:5px 10px;
  cursor:pointer;white-space:nowrap}}
.vbtn:hover{{color:var(--fg);background:rgba(88,166,255,.06)}}
.vbtn.active{{background:rgba(88,166,255,.14);color:var(--acc);
  box-shadow:0 0 0 1px rgba(88,166,255,.3) inset}}
.vbtn.vok.active{{background:rgba(63,185,80,.14);color:#56d364;
  box-shadow:0 0 0 1px rgba(63,185,80,.35) inset}}
.vbtn.vwarn.active{{background:rgba(210,153,34,.14);color:#e3b341;
  box-shadow:0 0 0 1px rgba(210,153,34,.35) inset}}
.vbtn.vbad.active{{background:rgba(248,81,73,.14);color:#ff7b72;
  box-shadow:0 0 0 1px rgba(248,81,73,.35) inset}}
/* CSV export: sits with each table's filter box, honours every active filter */
.csvbtn{{font:11px inherit;font-weight:600;color:var(--dim);background:var(--panel2);
  border:1px solid var(--line);border-radius:6px;padding:5px 10px;cursor:pointer;
  margin:2px 6px 8px 0;white-space:nowrap}}
.csvbtn:hover{{color:var(--acc);border-color:rgba(88,166,255,.32)}}
/* SECTION ANCHORS. The .topbar is position:sticky, so an anchor jump would scroll a heading
   flush under it and hide the label the reader jumped to. scroll-margin-top reserves the bar's
   height. Applied per-element rather than via :target so it also works when JS scrolls. */
h2.anchorable{{scroll-margin-top:64px}}
/* the jump strip sits in the sticky bar and stays flat/terminal in style -- no fill, no shadow */
.jump{{display:inline-flex;gap:2px;align-items:center;flex-wrap:wrap}}
.jump a{{color:var(--dim);text-decoration:none;font-size:11px;padding:3px 7px;
  border-radius:6px;border:1px solid transparent}}
.jump a:hover{{color:var(--acc);border-color:var(--line);background:var(--panel2)}}
.jump a:focus-visible{{outline:2px solid var(--acc);outline-offset:1px}}
/* dense transition table: 19 columns, so compress padding and let it scroll */
table.dense{{font-size:11px;display:block;overflow-x:auto;white-space:nowrap}}
table.dense th,table.dense td{{padding:4px 7px;vertical-align:top}}
table.dense th{{font-size:10px}}
/* PINNED FIRST COLUMN (dense-table rule: pin the identifier so a row keeps its anchor while
   the rest scrolls horizontally). display:block/overflow-x was already here; the pin lives on
   the first cell of every row, with a solid background so scrolled-under cells do not show
   through. min-width keeps the identifier readable rather than squeezed. */
table.dense th:first-child,table.dense td:first-child{{position:sticky;left:0;z-index:1;
  background:var(--bg);min-width:88px;box-shadow:inset -1px 0 0 var(--line)}}
/* TRUNCATED ADDRESS CELLS (dense-table rule: addresses are not data). 42 chars of hex per
   row times 100 rows is unreadable; the ticker identifies the market and the full hash is held
   by the tooltip + the basescan link in the same row. Monospace so the 10 glyphs that REMAIN
   stay column-aligned, and dim so it reads as reference data rather than signal. */
td {{font-variant-numeric:tabular-nums}}
.addr{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:10px;
  color:var(--dim);cursor:copy;white-space:nowrap}}
.addr.na{{color:var(--bd)}}
/* SAFETY-BUFFER GAUGE (dense-table rule: threshold bars over raw text). 0.9134 means nothing
   without its denominator; occupancy (share of remaining runway a position consumes) is the
   number that does. Rendered as a 44px bar: green under 50%, amber 50-75%, red past 100% --
   the same thresholds the summary cards state. tabular-nums keeps the label column-aligned. */
.gauge{{display:inline-block;width:44px;height:7px;border-radius:4px;background:rgba(139,150,168,.18);
  vertical-align:middle;margin-right:6px;overflow:hidden}}
.gauge i{{display:block;height:100%;border-radius:4px;background:var(--ok)}}
.gauge.w i{{background:#e3b341}}
.gauge.b i{{background:var(--bad)}}
table.dense code{{background:transparent;padding:0;color:var(--dim)}}
/* progressive disclosure */
tr.expandable{{cursor:pointer}}
tr.expandable td:first-child::before{{content:"\25B8";color:var(--dim);display:inline-block;
  width:12px;font-size:10px;transition:transform .12s}}
tr.expandable.open td:first-child::before{{content:"\25BE"}}
tr.drawer-row>td{{background:#0d131d;padding:0;border-bottom:1px solid var(--line)}}
.drawer{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:2px 18px;
  padding:12px 16px}}
.drow{{display:flex;justify-content:space-between;gap:12px;padding:3px 0;
  border-bottom:1px dotted rgba(139,150,168,.14);font-size:12px}}
.dk{{color:var(--dim);flex:0 0 auto;text-transform:uppercase;font-size:10px;letter-spacing:.05em}}
.dv{{text-align:right;word-break:break-word}}
.dv a{{color:var(--acc)}}
@media(max-width:640px){{.card{{flex:1 1 44%}}table{{font-size:11px}}
  .tabs{{order:9;width:100%}}#global-search{{flex:1}}
  /* TOUCH TARGETS (WCAG 2.5.8): a tap target under 44px is a miss on a phone. The star pin
     and the tab buttons are the two controls a reader taps most; pad them to the minimum
     without changing the pinned font-size scale. */
  .pin,.tab,.watch-toggle{{min-height:44px;min-width:44px}}
  .pin-cell{{min-width:44px}}
/* REFLOW AT 320px (WCAG 1.4.10). The document has four dense tables and a sticky topbar; below
   320px it must not scroll horizontally. minmax(0,1fr) and min-width:0 stop a wide table track
   from forcing the page wider than the viewport -- the commonest cause of horizontal scroll on
   a data page. Verified by measurement below, not by eye. */
@media(max-width:400px){{
  .wrap,.topbar,.tabs{{max-width:100vw}}
  table{{font-size:11px;table-layout:fixed}}
  .tabs{{flex-wrap:wrap;gap:2px}}
  .tab{{padding:3px 5px;font-size:11px}}
  /* the transitions time slider must reflow, not force horizontal scroll at 320px */
  .timectl{{flex-wrap:wrap}}
  .timectl input[type=range]{{width:100%;min-width:0}}
}}
/* MOTION IS OPT-IN (WCAG 2.2 / prefers-reduced-motion). The tabs and row-controls animate a
   transform; under reduced motion the transform is dropped and only the colour change remains,
   so nothing slides or scales. Previously the single transform transition ran unconditionally. */
@media(prefers-reduced-motion:reduce){{
  *{{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
}}
/* CHAT WIDGET. A fixed bottom-right assistant over the data. It answers from the latest run,
   never from the model; the model only routes intent. Fixed so it is visible on every tab. */
.chat-widget{{position:fixed;right:16px;bottom:16px;width:340px;max-width:calc(100vw - 32px);
  background:var(--panel);border:1px solid var(--line);border-radius:8px;
  box-shadow:0 8px 30px rgba(0,0,0,.5);z-index:100;display:flex;flex-direction:column}}
.chat-head{{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;
  border-bottom:1px solid var(--line);cursor:pointer;font-weight:600;font-size:13px}}
.chat-head .chat-sub{{font-weight:400;color:var(--dim);font-size:11px}}
.chat-body{{display:flex;flex-direction:column;gap:8px;padding:10px 12px}}
.chat-log{{max-height:220px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;
  font-size:12px}}
.chat-bubble{{padding:8px 10px;border-radius:8px;line-height:1.45;white-space:pre-wrap}}
.chat-bubble.user{{background:var(--panel2);border:1px solid var(--line);align-self:flex-end;
  max-width:90%}}
.chat-bubble.bot{{background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.3);
  align-self:flex-start;max-width:95%}}
.chat-row{{display:flex;gap:6px}}
.chat-row input{{flex:1;background:var(--panel2);border:1px solid var(--line);border-radius:8px;
  color:var(--txt);padding:8px 10px;font-size:12px;outline:none}}
.chat-row input:focus{{border-color:var(--acc)}}
.chat-row button{{background:var(--acc);color:#0a0e14;border:none;border-radius:8px;padding:0 12px;
  font-size:12px;font-weight:600;cursor:pointer}}
.chat-row button:disabled{{opacity:.5;cursor:default}}
.chat-hint{{font-size:10px;color:var(--dim)}}
.chat-widget.min .chat-body{{display:none}}
</style></head><body>"""]
    # Chat widget: fixed bottom-right, visible on every tab. Answers come from the latest run
    # via /api/chat; the model only routes intent. Rendered once here, wired by JS below.
    H.append(
        "<div class='chat-widget' id='chat-widget'>"
        "<div class='chat-head' id='chat-head'><span>Aegis assistant</span>"
        "<span class='chat-sub' id='chat-toggle'>hide</span></div>"
        "<div class='chat-body'>"
        "<div class='chat-log' id='chat-log'></div>"
        "<div class='chat-row'>"
        "<input id='chat-q' type='text' placeholder='Ask: verdict on cbBTC?' autocomplete='off'>"
        "<button id='chat-btn' type='button'>Ask</button>"
        "</div>"
        "<div class='chat-hint'>Answers from the latest immutable run. The model only routes "
        "your question; it never writes a number.</div>"
        "</div></div>")
    # Sticky status bar. Uses the run id and block already computed for this build, so the
    # reader sees which chain state the page describes without scrolling to the provenance
    # line. Values are escaped; nothing here is a new measurement.
    try:
        _run = (provenance.latest_run() or "").split("/")[-1] if hasattr(provenance, "latest_run") else ""
    except Exception:
        _run = ""
    _blk = ""
    try:
        _mp = os.path.join(provenance.latest_run(), "meta.json")
        if os.path.exists(_mp):
            _blk = str((json.load(open(_mp)).get("provenance") or {}).get("block_number") or "")
    except Exception:
        _blk = ""
    H.append(
        "<div class='topbar'><span class='brand'>Aegis</span>"
        "<span class='stat'><span class='dot'></span>Base Mainnet</span>"
        + ("<span class='stat'>block <code>" + esc(_blk) + "</code></span>" if _blk else "")
        + ("<span class='stat'>run <code>" + esc(_run) + "</code></span>" if _run else "")
        + "<span class='stat'>read-only &middot; no keys &middot; no transactions</span>"
        + "<span class='spacer'></span>"
        # JUMP STRIP. Nine tables and ~11,700 words: a reader landing mid-page has no map. These are
        # plain anchors, not tab switches -- they do not change which section is displayed, they
        # only scroll. That distinction matters: the tabs above HIDE sections with display:none, and
        # scrolling to an anchor inside a hidden container fails silently in every browser. So a
        # jump first makes its target visible (through the same path the tabs use) and then scrolls.
        + "<span class='jump'>"
        + "".join("<a href='#%s' data-jump='%s'>%s</a>" % (i, i, lbl) for i, lbl in (
            ("sec-summary", "Summary"),
            ("sec-watch", "Transitions"),
            ("sec-lending", "Lending"),
            ("sec-pools", "Real Pools"),
            ("sec-coverage", "Coverage"),
            ("sec-stress", "Forward Stress"),
            ("sec-regimes", "Regimes"),
            ("sec-runway", "Runway"),
            ("sec-liqs", "Liquidations"),
            ("sec-premortem", "Pre-Mortem"),
            ("sec-rwa", "RWA"),
            ("sec-pricing", "Pricing"),
            ("sec-method", "Method"),
        ))
        + "</span>"
        + "<input id='global-search' type='search' placeholder='search all tables\u2026' "
        + "aria-label='search all tables'>"
        + "<button id='watch-toggle' class='watch-toggle' aria-pressed='false' title='Show only "
        + "the rows you have pinned'>☆ watchlist</button>"
        + "<span id='watch-count' class='watch-count' aria-hidden='true'></span>"
        + "<span class='tabs'>"
        + "<button class='tab active' data-tab='summary' aria-selected='true'>Summary</button>"
        + "<button class='tab' data-tab='watch' aria-selected='false'>Transitions</button>"
        + "<button class='tab' data-tab='lending' aria-selected='false'>Lending</button>"
        + "<button class='tab' data-tab='soty' aria-selected='false'>Yield State</button>"
        + "<button class='tab' data-tab='scan' aria-selected='false'>Scan</button>"
        + "<button class='tab' data-tab='pools' aria-selected='false'>Real Pools</button>"
        + "<button class='tab' data-tab='coverage' aria-selected='false'>Coverage</button>"
        + "<button class='tab' data-tab='stress' aria-selected='false'>Forward Stress</button>"
        + "<button class='tab' data-tab='regimes' aria-selected='false'>Regimes</button>"
        + "<button class='tab' data-tab='runway' aria-selected='false'>Runway</button>"
        + "<button class='tab' data-tab='liqs' aria-selected='false'>Liquidations</button>"
        + "<button class='tab' data-tab='premortem' aria-selected='false'>Pre-Mortem</button>"
        + "<button class='tab' data-tab='rwa' aria-selected='false'>RWA</button>"
        + "<button class='tab' data-tab='pricing' aria-selected='false'>Pricing</button>"
        + "<button class='tab' data-tab='method' aria-selected='false'>Method</button>"
        + __import__("build_v2")._chain_tabs(res)
        + "<span id='verdict-bar' class='vbar' role='group'"
        + " aria-label='quick verdict filter'>"
        + "<span class='vl'>verdict</span>"
        + "<button type='button' class='vbtn vok' data-verdict-btn='REAL'"
        + " aria-pressed='false' title='Show only markets judged REAL'>REAL</button>"
        + "<button type='button' class='vbtn vwarn' data-verdict-btn='CAUTION'"
        + " aria-pressed='false' title='Show only markets judged CAUTION'>CAUTION</button>"
        + "<button type='button' class='vbtn vbad' data-verdict-btn='AVOID'"
        + " aria-pressed='false' title='Show only markets judged AVOID'>AVOID</button>"
        + "<button type='button' class='vbtn' data-verdict-clear='1'"
        + " title='Clear the verdict filter' aria-label='clear verdict filter'>\u2715</button>"
        + "</span>"
        + "<span class='rowctl'><label for='rowctl' title='How many rows each table shows "
        + "before scrolling'>rows <b id='rownum'>20</b></label>"
        + "<input id='rowctl' type='range' min='10' max='200' step='10' value='20' "
        + "aria-label='rows visible per table'></span>"
        + "</span></div>")
    H.append("<h1>Aegis Yield Screen</h1>")
    H.append(f"<div class='sub'>{len(res):,} pools scanned &middot; {ts} &middot; "
             "<b>classifies what a yield is made of, not what it will return</b></div>")

    # ---- Summary: the landing view. Rendered FIRST so it is what a reader sees before the
    # dense transitions table. Its own top-level section, so the Summary tab shows it alone.
    try:
        import lending_dashboard as _ld
        H.append("<div data-section='summary'>")
        _ld.render_glance(H, esc)
        H.append("</div>")
    except Exception as _e:
        print("  [summary skipped: %s]" % str(_e)[:70])

    # ---- What changed: the State Transition Log, rendered ----
    # alerts.log had accumulated 33 intervals and 21 real events with NO page showing it. The
    # dashboard told you the current state and nothing about movement, which is the thing a
    # curator actually acts on. Reads through run_history so this and the API cannot disagree.
    try:
        import run_history as _rh
        _ch = _rh.get_changes(limit=12)
        _unc = _rh.get_unchecked()
        _tot = sum(r.get("n_events") or 0 for r in _rh.get_changes())
        H.append("<div data-section='watch'><h2 id='sec-watch' class='anchorable'>What changed</h2>")
        H.append("<div class='sub'>State transitions between consecutive runs. <b>This is a "
                 "transition log, not an exploit warning</b> &mdash; it compares polls and "
                 "cannot observe anything that happens between them. Each run is stamped with "
                 "the Base block it came from.</div>")
        H.append("<div class='big'>"
                 "<div class='card'><div class='n'>%d</div><div class='l'>intervals logged</div></div>"
                 "<div class='card'><div class='n %s'>%d</div><div class='l'>transitions seen</div></div>"
                 "</div>" % (len(_rh.get_changes()), "warn" if _tot else "ok", _tot))
        _cur = [u for u in _unc if u.get("state") == "current"]
        _his = [u for u in _unc if u.get("state") != "current"]
        if _cur:
            # an unchecked check must be shown, not hidden: its silence is not stability
            H.append("<div class='sub' style='color:var(--warn)'><b>%d check(s) could not "
                     "run in the last %d intervals:</b> %s. Their silence is <b>not</b> "
                     "evidence of stability.</div>"
                     % (len(_cur), _rh.UNCHECKED_RECENT,
                        esc(", ".join(u["check"] for u in _cur))))
        if _his:
            # REPORTED, NOT SUPPRESSED -- but as history, because that is what it is. The old
            # banner showed a gap that ended 17 hours ago as a live warning, which trains the
            # reader to ignore the banner. Naming the age is the honest middle: the reader can
            # see the detector was blind, and can see it no longer is.
            H.append("<div class='sub' style='color:var(--dim)'>"
                     "Earlier in this log, <b>%s</b> could not run (%s). %s "
                     "Those stretches are excluded from the current assessment.</div>"
                     % (esc(", ".join(u["check"] for u in _his)),
                        esc("; ".join(("last seen %d intervals ago" % u["records_ago"])
                                      for u in _his)),
                        esc("Now running normally. "
                            if not _cur else "")))
        # ENRICHED. The raw log says what changed and the numbers either side; it does not say
        # which venue, what the position was worth, or where to look on-chain. Every row now
        # carries the venue, the contract addresses, the block, the market's size and links.
        ev = [e for e in _rh.get_events() if e.get("kind") != "INTERVAL_UNRELIABLE"]
        # a build that silently renders nothing is the failure mode this whole section exists
        # to avoid, so say how many transitions made it into the page
        print("  [what-changed] %d transitions, %d intervals logged" % (len(ev), len(_ch)))
        if ev:
            H.append("<div class='sub' style='margin-bottom:8px'>Every transition recorded, "
                     "with the venue, the market's size and links to the contracts. A market id "
                     "is a Morpho-internal key, not an address, so the Basescan link opens the "
                     "<b>collateral token</b>; the Morpho link opens the market itself.</div>")
            # TIME SLIDER over the transition history. The row count is small (107) but the
            # reader needs to ask "what happened in the last hour" rather than scan everything.
            # Bounded by the REAL min/max event epoch, computed here, not guessed in JS.
            try:
                _whens = [e.get("logged_at") for e in ev if e.get("logged_at")]
                _epochs = []
                import datetime as _dtm
                for _w in _whens:
                    try:
                        _epochs.append(int(_dtm.datetime.strptime(
                            _w.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                            .replace(tzinfo=_dtm.timezone.utc).timestamp()))
                    except Exception:
                        pass
                if _epochs:
                    _tmin, _tmax = min(_epochs), max(_epochs)
                    _tmin_s = _dtm.datetime.fromtimestamp(_tmin, _dtm.timezone.utc).strftime("%H:%M")
                    _tmax_s = _dtm.datetime.fromtimestamp(_tmax, _dtm.timezone.utc).strftime("%H:%M")
                    H.append("<div class='timectl' style='margin:8px 0 4px'>"
                             "<label for='timectl'>transitions after <b id='tmin'>start</b> "
                             "(<span class='dim'>%s</span> &rarr; <span class='dim'>%s</span>)</label>"
                             "<input id='timectl' type='range' min='%d' max='%d' value='%d' step='60' "
                             "data-tmin='%d' data-tmax='%d' aria-label='filter transitions by time'>"
                             "</div>" % (_tmin_s, _tmax_s, _tmin, _tmax, _tmin, _tmin, _tmax))
            except Exception:
                pass
            H.append("<table class='dense'><tr>"
                     "<th>when (UTC)</th><th>run</th><th>block</th><th>sev</th>"
                     "<th>venue</th><th>market</th><th>transition</th>"
                     "<th class='num'>util from</th><th class='num'>util to</th>"
                     "<th class='num'>&Delta;</th><th class='num'>LLTV</th>"
                     "<th class='num'>borrowed</th><th class='num'>liquidity</th>"
                     "<th class='num'>TVL</th><th>verdict</th><th>flags</th>"
                     "<th>collateral</th><th>oracle</th><th>links</th></tr>")
            for e in ev:
                sev = e.get("severity", "info")
                cls = {"high": "bad", "warn": "warn", "medium": "warn"}.get(sev, "dim")
                f, t = e.get("from"), e.get("to")
                def _p(v):
                    try: return "%.3f%%" % (float(v) * 100)
                    except Exception: return "&mdash;"
                d = "&mdash;"
                try: d = "%+.3f" % ((float(t) - float(f)) * 100)
                except Exception: pass
                lk = []
                if e.get("market_url"):
                    lk.append("<a href='%s' target='_blank' rel='noopener' title='This market on "
                              "Morpho'>morpho</a>" % esc(e["market_url"]))
                if e.get("explorer"):
                    lk.append("<a href='%s' target='_blank' rel='noopener' title='Collateral token "
                              "on Basescan'>basescan</a>" % esc(e["explorer"]))
                ca = e.get("collateral_address")
                # ADDRESSES ARE NOT DATA (dense-table rule). A full 20-byte address is 42
                # characters of noise in a cell the reader scans past; the ticker column
                # already identifies the market. Rendered: 0x34a2…999F. The full hash lives
                # in the tooltip, and the basescan link (which already existed) carries it.
                # One helper, not inline slicing, because the None and "&mdash;" cases both
                # have to fall through without rendering "None".
                def _addr(a):
                    if not a or a == "\u2014":
                        return "<span class='addr na'>&mdash;</span>"
                    a = str(a)
                    show = a[:6] + "\u2026" + a[-4:] if len(a) > 16 else a
                    return ("<span class='addr' title='%s' data-copy='%s' data-full='%s'>%s</span>"
                            % (esc(a), esc(a), esc(a), esc(show)))
                _when = ""
                try:
                    import datetime as _dt
                    _t = e.get("logged_at") or ""
                    if _t:
                        _t2 = _t.replace("Z", "")
                        _when = " data-when='%d'" % int(_dt.datetime.strptime(
                            _t2, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc).timestamp())
                except Exception:
                    _when = ""
                H.append(
                    "<tr%s><td class='dim'>%s</td><td class='dim'>%s</td>"
                    "<td class='num dim'>%s</td><td class='%s'>%s</td>"
                    "<td>%s<br><span class='dim' style='font-size:11px'>%s</span></td>"
                    "<td><b>%s</b><br><span class='dim' style='font-size:11px'>loan %s</span></td>"
                    "<td>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                    "<td class='num %s'>%s</td><td class='num'>%s</td>"
                    "<td class='num'>$%s</td><td class='num'>$%s</td><td class='num'>$%s</td>"
                    "<td>%s</td><td class='dim'>%s</td>"
                    "<td>%s</td>"
                    "<td>%s</td>"
                    "<td class='dim'>%s</td></tr>"
                    % (_when, esc(e.get("logged_at")), esc(e.get("run")), esc(e.get("block")),
                       cls, esc(sev), esc(e.get("venue")), esc(e.get("chain")),
                       esc(e.get("collateral")), esc(e.get("loan")),
                       esc(e.get("detail") or e.get("kind")),
                       _p(f), _p(t), ("bad" if e.get("kind") == "UTIL_CROSSED_90" else ""), d,
                       _p(e.get("lltv")),
                       "{:,.0f}".format(e.get("borrow_usd") or 0),
                       "{:,.0f}".format(e.get("liquidity_usd") or 0),
                       "{:,.0f}".format(e.get("tvl_usd") or 0),
                       pill(e.get("verdict")) if e.get("verdict") else "&mdash;",
                       esc(", ".join(e.get("fails") or []) or "&mdash;"),
                       _addr(ca), _addr(e.get("oracle")),
                       " ".join(lk) or "&mdash;"))
            H.append("</table>")
        else:
            H.append("<div class='sub'>No transitions in the last %d intervals. That is a "
                     "measurement of these polls, not a claim that the detector works.</div>"
                     % len(_ch))
        H.append("</div>")
    except Exception as _e:
        print("  [what-changed skipped: %s]" % str(_e)[:70])

    # ---- Lending markets: current state risk assessment ----
    try:
        import lending_dashboard
        H.append("<div data-section='lending'>")
        lending_dashboard.render(H, esc)
        # ---- ALL lending venues, not just Morpho ----------------------------
        # The tab was named "Morpho Lending" and held 631 pools while the feed carries 2,641
        # Lending-category pools across 82 venues. This table is the whole category; the table
        # above stays because it is the ONLY one with utilisation, LLTV and runway. They are two
        # tables on purpose: see venues.py for why one table would have to leave those columns
        # blank for 2,581 of 2,641 rows.
        try:
            _v = json.load(open(os.path.join(_HERE, "venues.json")))
            _c = _v["counts"]
            H.append("<h3 style='font-size:15px;margin:26px 0 6px'>Every lending venue, not just "
                     "Morpho</h3>")
            H.append("<div class='sub'>The feed carries <b>%d</b> pools in the Lending category "
                     "across <b>%d</b> venues. The tab above shows Morpho because Morpho is the "
                     "only venue here with <b>utilisation, LLTV and runway</b> &mdash; those figures "
                     "come from a per-venue API, not from the aggregate feed. Rather than blank "
                     "those columns for %d of %d rows, here is the full lending universe with the "
                     "columns that DO exist everywhere. Sort any column.</div>"
                     % (_c["lending_pools"], _c["lending_venues"],
                        _c["lending_pools"] - 631, _c["lending_pools"]))
            H.append("<div class='big'>"
              f"<div class='card'><div class='n'>{_c['lending_pools']:,}</div><div class='l'>lending pools</div></div>"
              f"<div class='card'><div class='n'>{_c['lending_venues']}</div><div class='l'>venues</div></div>"
              f"<div class='card'><div class='n ok'>{_c['lending_fitting']}</div><div class='l'>pass the screen</div></div>"
              f"<div class='card'><div class='n dim'>{_c['unmapped_projects']}</div><div class='l'>unmapped projects</div></div>"
              "</div>")
            def thv(label, tip):
                return "<th title='%s'>%s</th>" % (esc(tip), esc(label))
            # class='dense' so the table gets a bounded scroll window. Without it a 400-row
            # table is an unbounded data dump, and test_chain_tabs fails every tall table that
            # lacks one -- which is how this was caught.
            H.append("<table class='dense'><tr>"
                     + thv("venue", "The DefiLlama protocol slug. Category is joined from api.llama.fi/protocols, which matched all pools rather than most.")
                     + thv("chain", "The chain the pool lives on. Lending spans far more chains than Base.")
                     + thv("symbol", "The supplied asset or share token.")
                     + thv("tvl", "Total value supplied to this pool. Size only; it is not exit liquidity.")
                     + thv("apy", "Advertised annual yield, including any reward emissions.")
                     + thv("base", "Organic yield: interest only, excluding token emissions.")
                     + thv("rew", "Yield from token emissions. High reward share means the rate ends when incentives do.")
                     + thv("sigma", "Standard deviation of the YIELD itself, not of the token price. Above 0.30 the income is unstable.")
                     + thv("days", "How many days the pool has been tracked.")
                     + thv("verdict", "The screen's own verdict for this pool, using the same rules applied to the AMM side.")
                     + "</tr>")
            _pools = _v["pools"][:400]
            for _r in _pools:
                _vc = {"REAL": "ok", "PROMISING": "ok", "MIXED": "warn",
                       "AVOID": "bad", "NO_YIELD": "dim"}.get(_r.get("verdict"), "dim")
                H.append("<tr>"
                         "<td><b>%s</b></td><td class='dim'>%s</td><td>%s</td>"
                         "<td>$%s</td><td class='dim'>%s</td><td class='dim'>%s</td>"
                         "<td class='dim'>%s</td><td class='dim'>%s</td>"
                         "<td class='dim'>%s</td><td class='%s'>%s</td></tr>" % (
                    esc(_r.get("venue")), esc(_r.get("chain")), esc(_r.get("symbol")),
                    format(int(_r.get("tvl") or 0), ","),
                    ("%.2f%%" % _r["apy"]) if _r.get("apy") is not None else "&mdash;",
                    ("%.2f%%" % _r["base"]) if _r.get("base") is not None else "&mdash;",
                    ("%.2f%%" % _r["rew"]) if _r.get("rew") is not None else "&mdash;",
                    ("%.3f" % _r["sigma"]) if _r.get("sigma") is not None else "&mdash;",
                    _r.get("count") if _r.get("count") is not None else "&mdash;",
                    _vc, esc(_r.get("verdict"))))
            H.append("</table>")
            H.append("<div class='note'><b>What this table cannot tell you, and why it is a "
                     "separate table.</b> Utilisation, LLTV, runway to the withdrawal lock and "
                     "oracle provenance <b>are not in the aggregate feed</b> &mdash; checked: the "
                     "live response carries 28 fields and none of them is any of those. They come "
                     "from per-venue contract reads. So a single merged table would have to leave "
                     "those columns blank for <b>%d of %d rows</b> or invent them. Two tables with "
                     "an honest scope label beat one table with four empty columns. The venue "
                     "count is <b>%d</b>, and every pool's category was resolved rather than "
                     "guessed.</div>" % (_c["lending_pools"] - 631, _c["lending_pools"],
                                         _c["lending_venues"]))
        except Exception as _ve:
            print("  [all-venues lending table skipped: %s]" % str(_ve)[:70])
        H.append("</div>")
    except Exception as _e:
        print("  [lending section skipped: %s]" % str(_e)[:60])

    # ---- State of DeFi Yield: measured, re-derived at build time ----
    if SOTY:
        s = SOTY
        H.append("<div data-section='soty'><h2>State of DeFi Yield</h2>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n bad'>{s['bleed_pct']:.1f}%</div>"
          "<div class='l'>of pools lost &gt;50% of TVL in 12 months</div></div>"
          f"<div class='card'><div class='n bad'>{s['hy_k']} / {s['hy_n']}</div>"
          "<div class='l'>pools &gt;8% APY that paid what they advertised</div></div>"
          f"<div class='card'><div class='n warn'>{s['median_ret']:.1f}%</div>"
          "<div class='l'>median yield retention</div></div>"
          "</div>")
        H.append(
          f"<div class='note'><b>The APY illusion.</b> Of {s['hy_n']} pools advertising above "
          f"<b>8% APY</b>, <b>{s['hy_k']}</b> delivered the advertised rate over the following 12 "
          f"months. Median retention <b>{s['median_ret']:.1f}%</b>. <i>A yield screen does not predict "
          f"whether a pool survives &mdash; it checks whether the number on the tin is the number "
          f"that gets paid.</i></div>")
        H.append(
          f"<div class='note'><b>The slow bleed.</b> <b>{s['bleed_pct']:.1f}%</b> of indexed pools "
          f"(<b>{s['bleed_k']} of {s['bleed_n']}</b>) lost more than half their liquidity within a "
          f"year &mdash; 95% CI [{s['bleed_lo']:.1f}%, {s['bleed_hi']:.1f}%]. <b>They do not explode. "
          f"They bleed.</b> Under a binary dead-or-alive measure, {s['bleed_k'] - 8} of them would "
          f"still count as <i>survivors</i>, because they keep reporting while holding a fraction "
          f"of the capital.</div>")
        H.append("<div class='sub'>Measured on 122 pools with at least 12 months of history, anchored "
                 "to a point 12 months ago. Method and raw data in <code>BACKTEST_FINDINGS.md</code>. "
                 "These are observations about the index, not predictions about any pool.</div>")

    H.append("</div>")
    H.append("<div data-section='scan'>")
    H.append("""<div class="tool">
<div style="font-size:15px;font-weight:600;margin-bottom:4px">Audit a pool</div>
<div class="sub">Paste a contract address or the pair symbol.
Runs the six checks in your browser.</div>
<input id="q" placeholder="0x833589fC... &nbsp;·&nbsp; dexscreener.com/base/0x... &nbsp;·&nbsp; WETH-USDC">
<button onclick="run()">Run audit</button>
<div id="out"></div>
</div>""")

    H.append("<h2 id='sec-scan' class='anchorable'>What the scan found</h2><div class='big'>")
    for k,c in (("REAL","ok"),("PROMISING","ok"),("MIXED","warn"),("NO_YIELD","warn"),("AVOID","bad")):
        if k in vc: H.append(f"<div class='card'><div class='n {c}'>{vc[k]:,}</div><div class='l'>{k}</div></div>")
    H.append("</div>")
    H.append(f"<div class='note'><b>{vc.get('AVOID',0)/len(res)*100:.1f}% of pools carry at least one structural "
             f"flag.</b> The single largest reason is thin liquidity ({dict(fc).get('THIN',0):,} pools below the "
             f"$1M floor) — yield that cannot be exited at size is not yield.</div>")
    H.append("<h2 id='sec-reject' class='anchorable'>Rejection reasons</h2><div class='big'>")
    for k,c in fc: H.append(f"<div class='card'><div class='n'>{c:,}</div><div class='l'>{k}</div></div>")
    H.append("</div>")

    if ar:
        nread=sum(1 for o in ar if (o.get("read") or {}).get("ok"))
        nolink=sum(1 for o in ar if not o.get("fetchable"))
        H.append("<h2>Audit coverage</h2><div class='big'>"
          f"<div class='card'><div class='n bad'>{nolink}</div><div class='l'>no fetchable audit</div></div>"
          f"<div class='card'><div class='n ok'>{nread}</div><div class='l'>report read</div></div></div>")
        H.append(f"<div class='note'><b>{nolink/len(ar)*100:.0f}% of real-yield pools publish no audit "
                 "link at all</b>, and 55 more point only at Google Drive or Docsend, which block automated "
                 "fetch. This is not a gap in the data source — it is a gap in what these protocols publish."
                 "</div>")

    # Project -> official site, resolved ONCE from the protocol registry. assess() already
    # normalises both sides to alphanumerics (a direct slug join matches only 28%; this reaches
    # 98%), so reuse the same normalisation rather than inventing a second, weaker one.
    import re as _re
    _off = {}
    for _k, _v in (protos or {}).items():
        if isinstance(_v, dict) and _v.get("url"):
            _off.setdefault(_k, _v["url"])

    def _off_url(project):
        """Official site for a project name, or None. Absent is absent -- never guessed."""
        k = _re.sub(r"[^a-z0-9]", "", (project or "").lower())
        if k in _off:
            return _off[k]
        for kk, u in _off.items():
            if kk and len(kk) > 3 and (k.startswith(kk) or kk.startswith(k)):
                return u
        return None

    # SECTION ANCHORS. Nine tables and 11,700 words: a reader landing mid-page has no map. These
    # give each major section a stable id so the jump strip can reach it. `scroll-margin-top`
    # offsets the sticky .topbar -- without it an anchor scrolls the heading flush under the bar
    # and hides the very label you jumped to.
    H.append("</div>")
    H.append(f"<div data-section='pools'><h2 id='sec-pools' class='anchorable'>REAL pools, &gt;$10M TVL, by organic APY ({len(rows)})</h2>")
    H.append("<table class='dense'><tr><th>chain</th><th>project</th><th>symbol</th><th>APY</th><th>base</th>"
             "<th>reward</th><th>TVL</th><th>days</th><th>σ</th><th>stability</th><th>audit</th><th>links</th></tr>")
    for r,a,L in rows:
        av=a.get("verdict","?"); cls={"AUDITED":"ok","UNAUDITED":"bad","THIN":"warn"}.get(av,"dim")
        av_pill = pill(av)   # badge form; the bare verdict word is still inside the span
        sg=r.get("sigma"); sgt=f"{sg:.3f}" if isinstance(sg,(int,float)) else "-"
        st = "very stable" if (isinstance(sg,(int,float)) and sg<0.10) else \
             "stable" if (isinstance(sg,(int,float)) and sg<0.30) else \
             "variable" if (isinstance(sg,(int,float)) and sg<1.0) else "erratic" if isinstance(sg,(int,float)) else "-"
        stc = "ok" if st in ("very stable","stable") else "warn" if st=="variable" else "bad"
        lk=[]
        if L.get("defillama"): lk.append(f"<a href='{esc(L['defillama'])}' target='_blank' rel='noopener'>DL</a>")
        # LABELS STATE WHICH SURFACE EACH LINK OPENS. These carry the underlying TOKEN address
        # (DefiLlama publishes no pool address), so labelling them plainly "GT"/"DS" implied a
        # pool page the URL could not reach. Each anchor now says what it resolves to.
        # OFFICIAL protocol site first: it is the one link that identifies the protocol rather
        # than the token, and it comes from DefiLlama's protocol registry (not guessed).
        if a.get("url"):
            lk.append("<a href='%s' target='_blank' rel='noopener' class='off' title='Official "
                      "site for %s'>official</a>" % (esc(a["url"]), esc(r["project"])))
        # GeckoTerminal / DexScreener pills removed on request. Both pointed at the underlying
        # TOKEN, not the pool (DefiLlama publishes no pool address), so each needed a title
        # disclaiming what it was not -- and "search" was a symbol query that could land on any
        # pool with a similar ticker. Two links whose labels must apologise for themselves are
        # not worth the column. Removing them also drops 736KB from the inlined blob.
        # data-chain lets a tab isolate one ecosystem. The table applies two gates
        # (REAL verdict, >$10M) and sorts by APY, so a whole chain can be present in the data
        # and still be invisible -- 26 Flare rows were embedded while only one reached the
        # table. The tag makes the coverage reachable without weakening either gate.
        _cslug = str(r['chain']).lower()
        _isother = _cslug not in _big_chains
        H.append("<tr data-chain='%s'%s%s>" % (esc(_cslug),
                 "" if (r["chain"], r["project"], r["symbol"]) in _seen else " data-extra-row='1'",
                 " data-other='1'" if _isother else "")
          + f"<td>{esc(r['chain'])[:12]}</td><td>{esc(r['project'])[:20]}</td><td>{esc(r['symbol'])[:16]}</td>"
          f"<td class='ok'>{r['apy']:.2f}%</td><td>{r['base']:.2f}%</td><td class='dim'>{r['rew']:.2f}%</td>"
          f"<td>${r['tvl']/1e6:,.1f}M</td><td class='dim'>{r['count']}</td><td class='dim'>{sgt}</td>"
          f"<td class='{stc}'>{st}</td><td>{av_pill}</td><td class='dim'>{' '.join(lk)}</td></tr>")
    H.append("</table>")

    H.append("</div>")
    # ---- coverage honesty ----
    H.append("<div data-section='coverage'><h2 id='sec-coverage' class='anchorable'>Coverage &mdash; what this page can and cannot audit</h2>")
    n_above=sum(1 for r in res if r["tvl"]>=1_000_000)
    n_thin=sum(1 for r in res if r["tvl"]<100_000)
    H.append("<div class='big'>"
      f"<div class='card'><div class='n'>{len(res):,}</div><div class='l'>pools in the index</div></div>"
      f"<div class='card'><div class='n ok'>{n_above:,}</div><div class='l'>above $1M TVL</div></div>"
      f"<div class='card'><div class='n bad'>{n_thin:,}</div><div class='l'>under $100k &mdash; too small to enter</div></div>"
      f"<div class='card'><div class='n warn'>{len(addr):,}</div><div class='l'>addresses resolve on this page</div></div>"
      "</div>")
    H.append(f"<div class='note'><b>Read the fourth number.</b> {n_thin:,} of these pools "
             f"({n_thin/len(res)*100:.0f}%) hold under $100,000 &mdash; a pool that small cannot absorb a "
             f"meaningful position, so its APY is not available to you at size. That is the single largest "
             f"rejection reason in the scan. The capital concentrates in the <b>{n_above:,} pools above $1M</b>, "
             f"and this page resolves addresses for <b>{len(addr):,}</b> of them &mdash; roughly "
             f"<b>{len(addr)/n_above*100:.0f}%</b>. <b>Paste an address outside that set and this page will "
             f"tell you so</b> rather than guess. The MCP endpoint resolves from the full live feed.</div>")

    H.append("</div>")
    # ---- Forward Stress & Exit Impact ----
    # Two engines, both built because the page could say what IS but not what it COSTS or what
    # might happen NEXT. Every limit is rendered next to the numbers, not buried: a projection
    # presented without its assumptions is the exact failure this project exists to avoid.
    try:
        sf=json.load(open("stress_forward.json"))
    except Exception:
        sf=None
    try:
        ei=json.load(open("exit_impact.json"))
    except Exception:
        ei=None
    if sf:
        c=sf["counts"]
        H.append("<div data-section='stress'><h2 id='sec-stress' class='anchorable'>Forward Stress &mdash; what the current book could do next</h2>")
        H.append("<div class='sub'>Everything above describes the state as it is. This projects it "
                 "forward: for each Morpho market, how likely is the collateral price to fall far "
                 "enough to breach LLTV within 1, 7 and 30 days, given that market's own measured "
                 "volatility. <b>This is a simulation, not a prediction.</b></div>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n'>{c['simulated']}</div><div class='l'>markets simulated</div></div>"
          f"<div class='card'><div class='n warn'>{c['risky_5pct_or_more_30d']}</div><div class='l'>&ge;5% in 30 days</div></div>"
          f"<div class='card'><div class='n bad'>{c['already_past_lltv']}</div><div class='l'>already past LLTV</div></div>"
          f"<div class='card'><div class='n dim'>{c['insufficient_state']}</div><div class='l'>not simulatable</div></div>"
          "</div>")
        # the two directions of error, stated because they point OPPOSITE ways
        H.append("<div class='note'><b>The assumptions, and which way each one leans.</b> "
                 "<b>Markets are simulated independently</b> &mdash; no cross-market correlation, so a "
                 "real cascade is <i>understated</i>. <b>Debt is held constant</b> (interest ignored), so "
                 "breach is slightly <i>understated</i>. <b>A breach counts as a liquidation</b> with no "
                 "liquidator delay, so realised liquidations are an <i>upper bound</i>. "
                 "<b>Terminal-value breach only</b>: a path that dips and recovers mid-window is not "
                 "counted, so first-passage risk is <i>understated</i>. Returns are lognormal at the "
                 "market's own measured daily volatility. <b>Cascading liquidations and depeg contagion "
                 "are NOT modelled</b> &mdash; that needs a cross-market correlation matrix, and this "
                 "repository stores no per-market return series to build one from.</div>")
        if sf.get("risky"):
            # Every header carries a real definition, not the generic "Sorts this column"
            # fallback: test_visual requires it, and a reader meeting "1d" and "margin" cold
            # needs to know what they mean. Definitions teach; they do not restate the label.
            def th(label, tip):
                return "<th title='%s'>%s</th>" % (esc(tip), esc(label))
            H.append("<table><tr>"
                     + th("collateral", "The asset posted as collateral. Its price is what the "
                                        "simulation moves.")
                     + th("LTV", "Loan-to-value now: borrow_usd / collateral_usd at the current "
                                 "oracle price.")
                     + th("LLTV", "Liquidation loan-to-value: the LTV at which the position "
                                  "becomes liquidatable. Set per market by Morpho governance.")
                     + th("margin", "How far the collateral price may fall before LTV reaches "
                                    "LLTV: 1 - LTV/LLTV. A 50% margin means the price can "
                                    "halve before liquidation.")
                     + th("1d", "Modelled probability of breaching LLTV within ONE day. "
                                "Simulation, not a forecast; see the assumptions note.")
                     + th("7d", "Modelled probability of breaching LLTV within SEVEN days.")
                     + th("30d breach", "Modelled probability of breaching LLTV within 30 days. "
                                        "Independent-market lognormal simulation at the market's "
                                        "own measured volatility, so it EXCLUDES cascade risk.")
                     + th("vol source", "Where the volatility number came from. 'recomputed' means "
                                        "the raw price series was re-read and annualised at its "
                                        "true sampling cadence; 'stored' means the older, possibly "
                                        "inflated value had to be used.")
                     + "</tr>")
            for p_ in sf["risky"]:
                h=p_["horizons"]
                # NOTE the argument order: the CSS class %s comes BEFORE the probability it
                # styles. Passing them the other way round is what raised
                # "TypeError: must be real number, not str" -- the class string landed on %.1f.
                cls = "bad" if h["30"]["breach_prob"] >= 0.25 else "warn"
                H.append("<tr><td>%s</td><td class='dim'>%.3f</td><td class='dim'>%.2f</td>"
                         "<td>%.1f%%</td><td class='dim'>%.3f</td><td class='dim'>%.3f</td>"
                         "<td class='%s'>%.1f%%</td><td class='dim'>%s</td></tr>" % (
                    esc(p_.get("collateral")), p_["ltv"], p_["lltv"], 100*p_["margin"],
                    h["1"]["breach_prob"], h["7"]["breach_prob"],
                    cls, h["30"]["breach_prob"],
                    esc(p_.get("vol_source"))))
            H.append("</table>")
        H.append("<div class='note'><b>Every one of these figures was 2.6&times; too high until this "
                 "build.</b> The volatility input annualised its price series with "
                 "<code>sqrt(365)</code> regardless of the feed's actual sampling cadence. The Morpho "
                 "feed returns <b>weekly</b> points for most markets and daily for a few, so weekly "
                 "markets were inflated by exactly <code>sqrt(7)</code>. Measured: cbXRP 150.5% "
                 "&ldquo;annualised&rdquo; against a true 56.9%; <code>cbBTC</code> 5.71%/day against "
                 "2.15%. Correcting it took the set of markets with a &ge;5% 30-day breach chance from "
                 "<b>15 to 2</b>. The same inflated number feeds <code>sigma_to_breach</code>, which "
                 "gates the allocator's volatility rule &mdash; so it was <b>rejecting safe markets for "
                 "being volatile when they were not</b>. <code>test_vol_cadence.py</code> now pins it.</div>")
    H.append("</div>")
    # ---- Market regimes: which markets carry signal ----
    try:
        rgm=json.load(open(os.path.join(_HERE,"regimes.json")))
    except Exception:
        rgm=None
    if rgm:
        c=rgm["counts"]
        H.append("<div data-section='regimes'><h2 id='sec-regimes' class='anchorable'>Which Markets Are Worth Watching</h2>")
        H.append("<div class='sub'>Continuous monitoring of 60 markets is only worth paying for if "
                 "the watching is concentrated. It is, but <b>not the way it first appears</b>: the "
                 "flat markets are not one population, and the largest group of them is the most "
                 "broken rather than the most boring.</div>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n ok'>{c['active']}</div><div class='l'>ACTIVE &mdash; carries signal</div></div>"
          f"<div class='card'><div class='n bad'>{c['frozen']}</div><div class='l'>FROZEN &mdash; pinned at the ceiling</div></div>"
          f"<div class='card'><div class='n dim'>{c['quiescent']}</div><div class='l'>QUIESCENT &mdash; flat and idle</div></div>"
          f"<div class='card'><div class='n warn'>{c['jumps_5pp']}</div><div class='l'>single-interval moves &gt;5pp</div></div>"
          "</div>")
        H.append("<div class='note'><b>A flat utilisation series is two different things, and only "
                 "one of them is boring.</b> Measured across 106 consecutive runs: <b>32 markets sit "
                 "at EXACTLY 1.0000 utilisation and never move.</b> A fully-borrowed market "
                 "physically cannot move &mdash; no unborrowed capital remains to withdraw, so "
                 "utilisation has nowhere to go. Its flatness is the <b>ceiling, not idleness</b>. "
                 "Filing those under &ldquo;dead capital, do not watch&rdquo; would put the most "
                 "broken markets in the set the product tells you to ignore. They are now a "
                 "separate regime, and they need one alert now rather than sampling.</div>")
        H.append("<div class='note'><b>The interval is measured, not assumed.</b> A jump threshold "
                 "means nothing without the window it was measured over. The ledger's actual median "
                 f"spacing is <b>{rgm['median_interval_hours']}h</b>, computed from the run "
                 "timestamps rather than taken from a specification. Claiming a 15-minute window "
                 "without checking would be the <code>sqrt(365)</code> error one level up.</div>")
        def th3(label, tip):
            return "<th title='%s'>%s</th>" % (esc(tip), esc(label))
        H.append("<table><tr>"
                 + th3("collateral", "The asset backing the borrows.")
                 + th3("regime", "ACTIVE means utilisation moves, so the series carries information. QUIESCENT means flat and genuinely idle. FROZEN means flat because it is pinned at the 100% ceiling and cannot move.")
                 + th3("util", "Current utilisation. At 95% the market locks and depositors cannot withdraw.")
                 + th3("range", "Total spread of utilisation across the whole stored history. Under 0.1pp the series carries no signal.")
                 + th3("max move", "Largest single-interval change in utilisation. A large value means a market can move fast enough to matter between alerts.")
                 + th3(">5pp", "How many single intervals moved more than 5 percentage points.")
                 + "</tr>")
        for r in (rgm["active"][:12] + rgm["frozen"][:4]):
            cls = {"ACTIVE": "ok", "FROZEN": "bad", "QUIESCENT": "dim"}.get(r["regime"], "dim")
            H.append("<tr><td>%s</td><td class='%s'>%s</td><td class='dim'>%.4f</td>"
                     "<td>%.1fpp</td><td>%.2fpp</td><td class='dim'>%d</td></tr>" % (
                esc(r.get("collateral")), cls, esc(r["regime"]),
                r.get("utilization") or 0, 100 * r["range"], 100 * r["max_jump"], r["jumps_5pp"]))
        H.append("</table>")

    H.append("</div>")
    # ---- Runway to the withdrawal lock ----
    try:
        ry=json.load(open(os.path.join(_HERE,"runway.json")))
    except Exception:
        ry=None
    if ry:
        c=ry["counts"]
        H.append("<div data-section='runway'><h2 id='sec-runway' class='anchorable'>Runway to the Withdrawal Lock</h2>")
        H.append("<div class='sub'>A Morpho market freezes at <b>95% utilisation</b>: deposits cannot "
                 "be redeemed while borrows occupy the pool. The useful question is not "
                 "&ldquo;what is utilisation&rdquo; but <b>&ldquo;how many dollars can still leave, "
                 "and does my position fit in that gap&rdquo;</b>.</div>")
        # CARDS THAT ACT (dense-table rule: high-priority flags are quick filters, not passive
        # stat boxes). Each pill carries data-cardfilter with the token the table filter already
        # matches on; the click funnels it through the SAME text filter the search box uses, so
        # there is one filtering mechanism, not two. A second click clears (toggle).
        def cardpill(n, label, q=None, kind=None):
            return ("<div class='card %s' %s><div class='n'>%s</div><div class='l'>%s</div></div>"
                    % (kind or "", "data-cardfilter='%s'" % esc(q) if q else "", n, label))
        H.append("<div class='big'>"
          + cardpill(c['with_runway'], "markets with a runway")
          + cardpill(c['at_or_past_lock'], "at or past the lock", "BREACH", "bad")
          + cardpill(c['funded_positions'], "funded positions")
          + cardpill(c['funded_grade_severe_or_worse'], "using &gt;75% of the runway", "SEVERE", "warn")
          + "</div>")
        H.append("<div class='note'><b>Free liquidity is NOT the distance to the lock.</b> "
                 "A market at 91% utilisation has 9% of supply free, but only "
                 "<code>supply &minus; borrow/0.95</code> of room before it freezes &mdash; far "
                 "less. The example that made this concrete, from the run where the cap was "
                 "added: cbZEC at 91.34% had $138,757 free but only $61,730 of runway, the "
                 "allocator had assigned $70,833 &mdash; 1.15x the runway &mdash; and the position "
                 "could not fully exit without pushing the market to the freeze. It passed the old "
                 "depth check because that check compared the target to <i>free liquidity</i>, a "
                 "borrow-side figure. Every funded position is now capped to half the runway, and "
                 "the occupancy column below (with its gauge) reports the bound: today no position "
                 "exceeds 0.6.</div>")
        def th2(label, tip):
            return "<th title='%s'>%s</th>" % (esc(tip), esc(label))
        H.append("<table><tr>"
                 + th2("collateral", "The asset backing the borrows. Its price drives liquidation.")
                 + th2("utilisation", "Borrowed share of supplied capital. At 95% the market locks and depositors cannot withdraw.")
                 + th2("runway$", "Dollars of supply that can still be withdrawn before utilisation reaches 95%: supply - borrow/0.95. An accounting identity on two published numbers, not a forecast.")
                 + th2("target$", "What the allocator assigned to this market after the runway cap.")
                 + th2("occupancy", "Share of the available runway this one position occupies. Above 1.0 the position cannot leave without freezing the market.")
                 + "</tr>")
        for r in ry["funded"][:12]:
            cls = "bad" if r.get("grade") == "BREACH" else ("warn" if r.get("grade") == "SEVERE" else "")
            occ = float(r.get("occupancy") or 0)
            # width clamps at 100% so a BREACHED position renders a full red bar rather than
            # overflowing; the number beside it stays the true value.
            pct = max(0.0, min(100.0, occ * 100))
            H.append("<tr%s><td>%s</td><td class='dim'>%.4f</td><td>%s</td><td>%s</td>"
                     "<td class='%s'><span class='gauge %s'><i style='width:%.0f%%'></i></span>%.2f</td></tr>"
                     % (" data-risk='%s'" % (r.get("grade") or "") if r.get("grade") else "",
                        esc(r.get("collateral")), r.get("utilization") or 0,
                        format(int(r["runway_usd"]), ","), format(int(r["target_usd"]), ","),
                        cls or "dim", cls, pct, r["occupancy"]))
        H.append("</table>")
        H.append("<div class='note'><b>What this is not.</b> It is an arithmetic identity on "
                 "<code>supplyAssetsUsd</code> and <code>utilisation</code> &mdash; those two "
                 "combined, not new information about the market. It says how much room exists "
                 "<i>now</i>, not when it will be used: a market at 89% can sit there indefinitely, "
                 "and one at 60% can gap to the lock in a single block. It is a capacity, not a "
                 "rate. The value is operational &mdash; a dollar budget a risk committee can act "
                 "on, in place of a percentage it has to interpret. Presenting it as new "
                 "discrimination would repeat the exit-slippage error, where a rescaling of TVL was "
                 "briefly presented as a discovery.</div>")

    H.append("</div>")
    H.append("<div data-section='liqs'>")
    # ---- Volatility coverage: the silent path to $0 ----
    # Rendered because a missing or stale price cache produces an EMPTY allocation with no
    # error, which is indistinguishable from a quiet market. The numbers are recomputed here
    # from the artefacts so the page cannot go stale independently of them.
    try:
        _run_dirs=sorted(glob.glob(os.path.join(_HERE,"runs","*","")))
        _mkt=json.load(open(os.path.join(_run_dirs[-1],"markets.json")))
        _mkt=_mkt if isinstance(_mkt,list) else list(_mkt.values())
        _with=sum(1 for m in _mkt if m.get("daily_vol_pct") is not None)
        vol_cov={"total":len(_mkt),"with":_with,"without":len(_mkt)-_with}
        _pc=os.path.join(_HERE,"price_cache.json")
        vol_cov["cache_age_h"]=round((time.time()-os.path.getmtime(_pc))/3600.0,1) if os.path.exists(_pc) else None
        _cc=json.load(open(_pc)) if os.path.exists(_pc) else {}
        vol_cov["series_all_null"]=sum(1 for v in _cc.values() if v and all(p.get("y") is None for p in v))
        vol_cov["series_ok"]=sum(1 for v in _cc.values() if v and all(p.get("y") is not None for p in v))
    except Exception:
        vol_cov=None
    if vol_cov:
        _v=vol_cov
        H.append("<h3 style='font-size:15px;margin:22px 0 6px'>Volatility coverage &mdash; and the silent path to an empty book</h3>")
        H.append("<div class='sub'>Every market must have a volatility figure to be allocatable: "
                 "without one it fails <code>VOL_UNKNOWN</code> and is rejected. So coverage is not "
                 "a detail, it is the width of the investable universe.</div>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n'>{_v['with']}</div><div class='l'>markets with volatility</div></div>"
          f"<div class='card'><div class='n warn'>{_v['without']}</div><div class='l'>without &mdash; rejected</div></div>"
          f"<div class='card'><div class='n bad'>{_v['series_all_null']}</div><div class='l'>cached series, all prices null</div></div>"
          f"<div class='card'><div class='n dim'>{_v['cache_age_h'] if _v['cache_age_h'] is not None else '&mdash;'}</div>"
          f"<div class='l'>price cache age (hours)</div></div>"
          "</div>")
        H.append("<div class='note'><b>An absent or stale price cache produces an EMPTY allocation "
                 "with no error.</b> Measured by stripping the volatility fields &mdash; exactly what "
                 "a missing cache yields &mdash; <b>all 60 markets fail <code>VOL_UNKNOWN</code>, "
                 "0 remain eligible, and $0 of $1,000,000 is deployed.</b> A cycle that silently "
                 "allocates nothing is indistinguishable from a quiet day. The scheduled path "
                 "(<code>aegis_run.py</code>) only <i>reads</i> this cache; "
                 "<code>allocator.py</code>, which refreshes it, is not scheduled anywhere. It now "
                 "prints volatility coverage on every run and shouts when that count is zero, "
                 "rather than printing nothing &mdash; the same silent-zero failure class as the "
                 "counter that read 0 for a passing suite.</div>")
        H.append(f"<div class='note'><b>{_v['series_all_null']} cached price series return a full "
                 f"length of timestamps with EVERY price null</b> (HERMES, HOME, FUSD, RSS, kk). "
                 f"They pass the <code>len(points) &gt;= 10</code> guard because the timestamps are "
                 f"real, then contribute nothing, so the market is rejected as if it had no data. "
                 f"Only {_v['series_ok']} series are fully populated. These markets are now labelled "
                 f"with a <code>vol_reason</code> saying so, because an all-null series is a "
                 f"<i>feed</i> problem worth seeing, not a property of the market.</div>")

    # ---- Portfolio correlation: what diversification actually bought today ----
    try:
        _pcorr=json.load(open(os.path.join(_HERE,"portfolio_corr.json")))
    except Exception:
        _pcorr=None
    if _pcorr and _pcorr.get("names"):
        _n=len(_pcorr["names"]); _sup=_pcorr.get("support") or [[0]*_n for _ in range(_n)]
        _pv=_pcorr.get("portfolio_daily_vol_pct"); _sv=_pcorr.get("standalone_daily_vol_pct")
        _bene=_pcorr.get("correlation_benefit_pct")
        H.append("<h3 style='font-size:15px;margin:22px 0 6px'>Portfolio correlation &mdash; what the "
                 "30% collateral cap actually bought</h3>")
        H.append("<div class='sub'>A pairwise-complete correlation matrix over the eligible "
                 "collaterals' weekly returns, cadence-normalised before any return is taken "
                 "(a weekly return is never annualised as though it were daily &mdash; the error "
                 "test_vol_cadence exists to prevent). Diagonal entries come from each series on "
                 "its own; off-diagonal entries only where the two series share at least "
                 "<b>%d</b> aligned weekly returns, because below that a correlation estimate "
                 "carries more noise than signal. Pairs under that bar are shown as a dot and "
                 "treated as 0 &mdash; the neutral assumption, not a measured one.</div>"
                 % _pcorr.get("min_pair_n"))
        if _pv is not None and _sv is not None:
            _cls = "ok" if (_bene or 0) > 0 else "bad"
            H.append("<div class='big'>"
              f"<div class='card'><div class='n'>{_sv:.2f}%</div><div class='l'>portfolio daily vol if correlations were 0</div></div>"
              f"<div class='card'><div class='n {_cls}'>{_pv:.2f}%</div><div class='l'>actual portfolio daily vol (correlated)</div></div>"
              f"<div class='card'><div class='n {_cls}'>{_bene:+.2f}%</div><div class='l'>what correlation cost</div></div>"
              f"<div class='card'><div class='n {'ok' if _pcorr.get('psd') else 'bad'}'>"
              f"{('%+.3f' % _pcorr['min_eigenvalue']) if _pcorr.get('min_eigenvalue') is not None else '&mdash;'}</div>"
              f"<div class='l'>min eigenvalue (negative &rarr; not a valid risk model)</div></div>"
              "</div>")
        H.append("<div class='note'><b>A negative benefit is the honest number here.</b> Every "
                 "correlation on this page is <i>positive</i> (0.24&ndash;0.75), so holding them "
                 "together makes the book MORE volatile than the same dollars in uncorrelated "
                 "assets would be, not less. The 30% collateral cap bounds WHAT the book can "
                 "concentrate in; it does not, and cannot, make correlated assets diversify. "
                 "This panel is diagnostic: the allocator still sizes from sigma-to-breach and "
                 "the concentration cap, not from this matrix. It is here so the number the cap "
                 "cannot show &mdash; correlation &mdash; is visible next to the numbers it does.</div>")

    # ---- Liquidation feed: the on-chain record, ingested and cross-referenced ----
    try:
        _liq=json.load(open(os.path.join(_HERE,"liquidations.json")))
    except Exception:
        _liq=None
    if _liq and _liq.get("items"):
        _items=_liq["items"]; _s=_liq.get("summary") or {}
        _lk=None
        try:
            import liquidations as _Lmod
            _lk=_Lmod.link_to_runs(_liq)
        except Exception:
            _lk=None
        H.append("<h2 id='sec-liqs' class='anchorable'>Liquidations &mdash; the on-chain record</h2>")
        H.append("<div class='sub'>Every liquidation Morpho Blue emitted on Base since "
                 "<b>%s</b>, ingested from the official API (read-only, no keys), unit-normalised "
                 "per asset decimals. %s</div>"
                 % (time.strftime("%B %Y", time.gmtime(_items[-1]["ts"])) if _items else "",
                    ("%d events stored." % len(_items))))
        _h24=_s.get("h24") or {}; _d7=_s.get("d7") or {}; _d30=_s.get("d30") or {}
        H.append("<div class='big'>"
          f"<div class='card'><div class='n'>{_d30.get('events',0):,}</div><div class='l'>liquidations, 30 days</div></div>"
          f"<div class='card'><div class='n'>{_d7.get('events',0):,}</div><div class='l'>7 days</div></div>"
          f"<div class='card'><div class='n bad'>{_d30.get('bad_events',0)}</div>"
          f"<div class='l'>bad-debt events, 30 days (${'%.2f' % (_d30.get('bad_total') or 0)})</div></div>"
          f"<div class='card'><div class='n'>{'%.0f' % (_d30.get('seized') or 0)}</div>"
          f"<div class='l'>collateral seized, 30d (loan units)</div></div>"
          "</div>")
        # THE COVERAGE PANEL, INCLUDING THE NEGATIVE RESULT
        if _lk:
            _c=_lk.get("coverage") or {}
            _cov=_c.get("events",0)-_c.get("before_first_run",0)
            H.append("<div class='note'><b>Coverage, stated plainly &mdash; including what this "
                     "statistic does NOT show.</b> %d liquidation events have a screen verdict "
                     "recorded before they happened: AVOID %d, CAUTION %d, <b>REAL %d</b>. The "
                     "positive number is small and the negative one is the headline: <b>liquidations "
                     "are the mechanism of a lending market, not its failure</b> &mdash; a healthy "
                     "market with a volatility spike liquidates positions without ever carrying bad "
                     "debt, and this screen was never built to predict that. The signal it claims is "
                     "bad debt, of which this feed records %d events in the last 30 days. Claiming "
                     "the %d REAL-flagged liquidations as misses would be claiming a predictor this "
                     "screen does not have.</div>"
                     % (_cov, _c.get("flagged_avoid",0), _c.get("flagged_caution",0),
                        _c.get("flagged_real",0), _d30.get("bad_events",0), _c.get("flagged_real",0)))
        # FORWARD-TEST SERIES (task B+): the coverage note above is a snapshot; the series
        # makes it a history. Each day is one row, append-only, and the table is what makes the
        # 6/12-month claim auditable: a reader sees the days accumulating, not one recomputed number.
        try:
            _ft=json.load(open(os.path.join(_HERE,"forward_test.json")))
        except Exception:
            _ft=None
        if _ft and _ft.get("days"):
            H.append("<h3 style='font-size:13px;margin:16px 0 4px'>Forward-test coverage, by day</h3>")
            H.append("<div class='sub' style='margin-bottom:6px'>Append-only daily series. Coverage "
                     "began <b>%s</b>; a day is omitted when no covered event occurred, so the rows "
                     "are coverage, not run-history. This is a FORWARD test &mdash; it measures the "
                     "rate at which flagged markets liquidate against unflagged ones, and says "
                     "nothing until the series has grown.</div>" % _ft.get("coverage_started"))
            H.append("<table><tr><th>day</th><th class='num'>covered</th><th class='num'>AVOID</th>"
                     "<th class='num'>CAUTION</th><th class='num'>REAL</th><th class='num'>bad-debt</th></tr>")
            for d in _ft["days"]:
                H.append("<tr><td class='dim'>%s</td><td class='num'>%d</td><td class='num %s'>%d</td>"
                         "<td class='num %s'>%d</td><td class='num'>%d</td><td class='num %s'>%d</td></tr>"
                         % (esc(d["day"]), d["covered"],
                            ("bad" if d["avoid"] else "dim"), d["avoid"],
                            ("warn" if d["caution"] else "dim"), d["caution"],
                            d["real"],
                            ("bad" if d["bad_debt_events"] else "dim"), d["bad_debt_events"]))
            H.append("</table>")
            H.append("<div class='sub' style='margin-top:4px'>Totals: <b>%d</b> covered &middot; "
                     "AVOID %d &middot; CAUTION %d &middot; REAL %d &middot; bad-debt events %d "
                     "($%.2f).</div>"
                     % (_ft["totals"]["covered"], _ft["totals"]["avoid"], _ft["totals"]["caution"],
                        _ft["totals"]["real"], _ft["totals"]["bad_debt_events"],
                        _ft["totals"]["bad_debt_usd"]))
        # recent events table
        H.append("<table class='dense'><tr><th>when (UTC)</th><th>block</th><th>market</th>"
                 "<th class='num'>seized</th><th class='num'>repaid</th><th class='num'>bad debt</th>"
                 "<th class='num'>LLTV</th><th>tx</th></tr>")
        def _fmt(v,d,_suffix=""):
            try: return "{:,.4f}".format(float(v))+_suffix
            except Exception: return "&mdash;"
        for i in _items[:40]:
            _dt=time.strftime("%Y-%m-%d %H:%M", time.gmtime(i["ts"]))
            H.append("<tr><td class='dim'>%s</td><td class='num dim'>%s</td>"
                     "<td><b>%s</b><br><span class='dim' style='font-size:11px'>loan %s</span></td>"
                     "<td>%s</td><td class='num'>%s</td>"
                     "<td class='%s'>%s</td><td class='num dim'>%.4f</td>"
                     "<td class='mono-cell'>%s</td></tr>"
                     % (_dt, format(i["block"],",") if i.get("block") else "&mdash;",
                        esc(i.get("collateral") or "?"), esc(i.get("loan") or "?"),
                        ("%.4f" % i["seized"]) if i.get("seized") is not None else "&mdash;",
                        _fmt(i.get("repaid"),4) if i.get("repaid") is not None else "&mdash;",
                        ("bad" if (i.get("bad_debt") or 0)>0 else "dim"),
                        _fmt(i.get("bad_debt"),4) if i.get("bad_debt") is not None else "&mdash;",
                        i.get("lltv") if i.get("lltv") is not None else 0,
                        ("<span class='addr' title='%s' data-copy='%s' data-full='%s'>%s</span>"
                         % (esc(i["tx"]), esc(i["tx"]), esc(i["tx"]), esc((i["tx"] or "")[:10]+"\u2026"+(i["tx"] or "")[-6:]) if i.get("tx") else "")) if i.get("tx") else "&mdash;"))
        H.append("</table>")
        H.append("<div class='sub' style='margin-top:6px'>Show the 40 newest. Seized and repaid "
                 "are in their OWN asset's units (seized = collateral decimals, repaid = loan "
                 "decimals), because an index that divides by 1e6 unconditionally produces a "
                 "&ldquo;$1.4T seized in 30 minutes&rdquo; row &mdash; that bug shipped here once.</div>")
    if ei:
        c=ei["counts"]
        H.append("<div class='sub'>The screen flags a pool <code>THIN</code> below $1M TVL. TVL is the "
                 "<i>size</i> of a pool; exit impact is the <i>cost</i> of leaving it. Below is the exact "
                 "constant-product slippage for a position of each size, in dollars of value lost.</div>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n warn'>{c['brutal_but_passed_the_1m_floor']:,}</div>"
          f"<div class='l'>passed the $1M floor, still brutal to exit $1M</div></div>"
          f"<div class='card'><div class='n ok'>{c['flagged_thin_but_cheap_to_exit']:,}</div>"
          f"<div class='l'>flagged THIN, cheap to exit</div></div>"
          f"<div class='card'><div class='n'>{c['pools']:,}</div><div class='l'>pools profiled</div></div>"
          "</div>")
        # THE HONESTY NOTE THAT MATTERS MOST: this metric does not re-rank anything.
        if ei.get("pool_metric_is_tvl_rescaled"):
            H.append("<div class='note'><b>This metric does not re-rank the pools, and the page says so "
                     "rather than implying otherwise.</b> For a 50/50 constant-product pool, fixing a "
                     "loss threshold makes the largest acceptable position exactly proportional to TVL "
                     "(measured: every pool's ratio is identical to 9 decimal places). So ranking by "
                     "exit impact is <b>identical to ranking by TVL</b>. What it adds is a "
                     "<i>dollar cost</i> in place of a boolean, which is easier to act on &mdash; but it "
                     "is a re-expression of the same number, not new discrimination. It is stated here "
                     "because presenting a rescaling as a discovery is precisely the failure this "
                     "project is built to catch.</div>")
        H.append("<div class='note'><b>Two limits, pointing opposite ways.</b> The feed does not say "
                 "which AMM, so constant-product is assumed &mdash; that is the <i>worst case</i> for a "
                 "given depth, and a stableswap pool is far cheaper, so these costs are an upper bound. "
                 "But <b>TVL is not exit liquidity</b>: it counts both sides and assumes all of it is "
                 "touchable, so the real cost is higher &mdash; a lower bound. Both errors are named "
                 "rather than averaged into one confident number. Where a <i>real</i> liquidity figure "
                 "exists (the Morpho feed's <code>liquidity_usd</code>), it is used instead and no model "
                 "is applied: <b>47 of 60 markets hold under 10% of TVL as free liquidity</b>, and three "
                 "(USR, RLP, yUSD &mdash; all depegged) hold <b>zero</b>.</div>")
        H.append("<div class='note'><b>Not built, and why.</b> The brief asks for tick-level swap data "
                 "and net-of-LVR yield, mempool visibility, and live contract-invariant monitoring. "
                 "<b>None of the three is computable from this feed</b> &mdash; it carries 28 aggregate "
                 "fields, and none is a swap, a sender address, or a bytecode slot. A prior attempt at "
                 "net-of-LVR produced an 8,945% loss on a stablecoin pool because the feed's "
                 "<code>sigma</code> measures <i>yield</i> volatility, not price volatility. Each needs "
                 "an archive node and an indexer: a different product with a different cost basis. "
                 "The Base RPC <i>is</i> reachable from here, so this is an engineering decision, not a "
                 "blocked one.</div>")

    H.append("</div>")
    # ---- Pre-Mortem Engine results ----
    try:
        pm=json.load(open("premortem_summary.json"))
    except Exception:
        pm=None
    if pm:
        H.append("<div data-section='premortem'><h2 id='sec-premortem' class='anchorable'>The Pre-Mortem Engine &mdash; why we rejected our own strategies</h2>")
        H.append("<div class='sub'>We built five TradingView strategies. Then we graded them against "
                 "buy-and-hold on three years of hourly bars &mdash; next-bar fills, real fees, real gas, "
                 "ruin handling, and a baseline that pays the same friction. Below is what happened.</div>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n'>{pm['valid']}</div><div class='l'>runs graded</div></div>"
          f"<div class='card'><div class='n bad'>{pm['loses']}</div><div class='l'>lost to buy-and-hold</div></div>"
          f"<div class='card'><div class='n ok'>{pm['beats']}</div><div class='l'>beat it</div></div>"
          f"<div class='card'><div class='n bad'>{pm['ruined']}</div><div class='l'>accounts wiped</div></div>"
          f"<div class='card'><div class='n warn'>{pm['corr']}</div><div class='l'>corr(HODL, alpha)</div></div>"
          "</div>")
        H.append(f"<div class='note'><b>In a rising market the strategies won {pm['bull_beats']} of "
                 f"{pm['bull_runs']}.</b> On flat or falling assets they won {pm['flat_beats']} of "
                 f"{pm['flat_runs']}. The correlation between how well the asset did and the strategy's "
                 f"alpha is <b>{pm['corr']}</b> &mdash; almost a straight line. <b>The edge is not timing "
                 f"skill. It is being flat while the asset goes nowhere.</b> That reads as outperformance "
                 f"against a flat benchmark and evaporates the moment there is a trend to capture.</div>")
        H.append("<table><tr><th>strategy</th><th>beat</th><th>runs</th><th>median alpha vs HODL</th></tr>")
        for st in pm["strategies"]:
            c="ok" if st["beat"]>st["n"]/2 else "bad"
            H.append(f"<tr><td>{esc(st['name'])}</td><td class='{c}'>{st['beat']}</td>"
                     f"<td class='dim'>{st['n']}</td>"
                     f"<td class='{'ok' if st['med_alpha']>0 else 'bad'}'>{st['med_alpha']:+.1f} pts</td></tr>")
        H.append("</table>")
        H.append("<h3 style='font-size:13px;margin:18px 0 6px'>By asset &mdash; the market decided the outcome</h3>")
        H.append("<table><tr><th>asset</th><th>buy &amp; hold</th><th>strategies that beat it</th></tr>")
        for a in pm["assets"]:
            H.append(f"<tr><td>{esc(a['sym'])}</td><td class='{'ok' if a['hodl']>0 else 'bad'}'>"
                     f"{a['hodl']:+.1f}%</td><td class='dim'>{a['beat']} / {a['n']}</td></tr>")
        H.append("</table>")
        H.append(f"<div class='note'><b>Three bugs this exercise found in our own engine.</b> "
                 f"Impossible ROIs of &minus;645% (the engine re-bet the full notional after the account "
                 f"had shrunk &mdash; over-betting). A strategy that never traded scored alpha of "
                 f"+100% in a falling market purely by not participating (now reported as "
                 f"<code>SAT_OUT</code>). And <code>{esc(pm['excluded']['file'])}</code> is not hourly "
                 f"&mdash; {pm['excluded']['bars']:,} bars spanning {esc(pm['excluded']['span'])}, median "
                 f"gap {pm['excluded']['median_gap_h']}h. <b>That last bug produced the single most "
                 f"dramatic number in the set</b>, and it was a window artefact. ETH is excluded from "
                 f"the figures above.</div>")
        H.append("<div class='note'><b>What we sell is the harness, not the strategies.</b> "
                 "<i>Bring your strategy or your pool thesis. We run it against next-bar execution, real "
                 "fees, real gas, ruin handling, and a fee-charged buy-and-hold baseline. We show you "
                 "what fails before you fund it.</i></div>")

    H.append("</div>")
    # ---- RWA lens (tokenised treasuries) ----
    RWA_KW=("ondo","superstate","backed","mountain","openeden","maple","centrifuge","goldfinch",
            "tbill","treasury","rwa","usdy","buidl","eutbl","ustb","ousg","midas")
    rwa=[r for r in res if any(k in (str(r.get("project",""))+str(r.get("symbol",""))).lower()
                               for k in RWA_KW)]
    if rwa:
        rr=[screen_pool_view(r) for r in rwa]
        npass=sum(1 for x in rr if x["verdict"] in ("REAL","PROMISING"))
        allpass=vc.get("REAL",0)+vc.get("PROMISING",0)
        rwa_tvl=sum(x["tvl"] for x in rr)
        thin=sum(1 for x in rr if x["tvl"]<1_000_000)
        H.append("<div data-section='rwa'><h2 id='sec-rwa' class='anchorable'>Lens: tokenised treasuries &amp; RWAs</h2>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n'>{len(rr)}</div><div class='l'>pools matched</div></div>"
          f"<div class='card'><div class='n'>${rwa_tvl/1e9:.1f}B</div><div class='l'>TVL in the slice</div></div>"
          f"<div class='card'><div class='n ok'>{npass/len(rr)*100:.0f}%</div><div class='l'>pass this screen</div></div>"
          f"<div class='card'><div class='n warn'>{allpass/len(res)*100:.0f}%</div><div class='l'>whole feed passes</div></div>"
          f"<div class='card'><div class='n bad'>{thin}</div><div class='l'>too small to enter</div></div>"
          "</div>")
        H.append(f"<div class='note'><b>The tokenised-treasury slice passes this screen "
                 f"{(npass/len(rr))/max(allpass/len(res),1e-9):.1f}x more often than the market overall</b> "
                 f"&mdash; {npass/len(rr)*100:.0f}% versus {allpass/len(res)*100:.0f}%. "
                 f"<b>And almost none are rejected for fake yield</b>, because a tokenised treasury "
                 f"passes through a real rate. They are rejected for being too small ({thin} of "
                 f"{len(rr)}) and too new. That is a capacity and history problem, not a fraud problem "
                 f"&mdash; and it is exactly what an institution's compliance process needs documented.</div>")
        best=sorted([x for x in rr if x["verdict"]=="REAL"], key=lambda x:x["sigma"] if x["sigma"] is not None else 99)
        # AMM provenance, STATED SEPARATELY. The lending half is refreshed every 15 minutes by
        # aegis-forward.timer; this half by aegis-amm.timer on a 6-hour batch (00/06/12/18 UTC).
        # They move at different velocities -- Morpho state changes within blocks, AMM yields are
        # built from 24h volume and 7d/30d fee averages -- so presenting both under one
        # block-height line implied the whole document shared the lending block.
        #
        # THE LINE USED TO SAY "refreshed by a manual build". That was true once and stopped
        # being true when aegis-amm.timer was created; the page went on claiming a human ran it.
        # A provenance line that describes a process that no longer exists is worse than none,
        # because it is believed. The cadence is now named, and the age is still MEASURED from
        # the file mtime rather than assumed from the schedule -- if the timer stops, the age
        # keeps climbing and the claim is visibly falsified.
        AMM_CADENCE = "6h batch (00/06/12/18 UTC)"
        try:
            import os as _os, datetime as _dt
            _rj = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "results.json")
            _mt = _dt.datetime.utcfromtimestamp(_os.path.getmtime(_rj)).strftime("%Y-%m-%d %H:%MZ")
            _age = (_dt.datetime.utcnow() - _dt.datetime.utcfromtimestamp(_os.path.getmtime(_rj)))
            _h = _age.total_seconds()/3600.0
            _age_s = "%.1f hours old" % _h if _h >= 1 else "%d minutes old" % int(_age.total_seconds()/60)
        except Exception:
            _mt, _age_s = "unknown", "unknown"
        H.append("<div class='sub' style='margin:2px 0 8px'><b>AMM Index Provenance:</b> "
                 "DefiLlama snapshot <code>%s</code> &middot; %s &middot; on a %s, slower than the "
                 "15-minute lending feed above. DefiLlama indexes pools on a multi-hour cycle, so "
                 "a faster poll would return the same record. "
                 "<b>These two halves describe different points in time.</b></div>"
                 % (esc(_mt), esc(_age_s), esc(AMM_CADENCE)))
        # DENSE pool table. Previously four visible columns (pool, project, APY, TVL) while the
        # embedded data carried fourteen fields. Every column below is a value the feed already
        # published and the page discarded -- nothing here is derived, and a missing value
        # renders as a dash rather than a zero.
        H.append("<table class='dense'><tr>"
                 "<th>pool</th><th>project</th><th>chain</th>"
                 "<th class='num'>APY</th><th class='num'>organic</th>"
                 "<th class='num'>emissions</th><th class='num'>emit&nbsp;share</th>"
                 "<th class='num'>7d base</th><th class='num'>&Delta;1d</th>"
                 "<th class='num'>&Delta;7d</th><th class='num'>&Delta;30d</th>"
                 "<th class='num'>30d mean</th><th class='num'>vs mean</th>"
                 "<th class='num'>TVL</th><th class='num'>vol 24h</th>"
                 "<th class='num'>vol 7d</th><th class='num'>turnover/d</th>"
                 "<th class='num'>IL 7d</th><th>IL risk</th><th>exposure</th>"
                 "<th class='num'>&sigma;</th><th>stability</th>"
                 "<th class='num'>days</th><th>verdict</th><th>flags</th>"
                 "<th>reward tokens</th><th>underlying</th><th>links</th></tr>")
        # Rendered 10 rows while 1,308 REAL pools sat in the embedded JSON. A 28-column dense
        # table is wasted on ten rows -- the whole point of the columns is to let a reader scan
        # and compare. Widened to 120; the JS filter and sort make that practical, and the rows
        # were already downloaded in `DATA`, so this adds markup, not bytes of data.
        for x in best[:120]:
            sgv=x["sigma"]
            sig_txt="n/a" if sgv is None else f"{sgv:.3f}"
            def _n(v, f="{:,.2f}", suffix=""):
                return (f.format(v) + suffix) if isinstance(v,(int,float)) else "&mdash;"
            apy=x["apy"]; rew=x.get("rew") or 0
            emit = (rew/apy*100) if apy else None
            mean=x.get("mean30")
            vs = ((apy/mean-1)*100) if (mean and apy) else None
            turn = ((x.get("vol1") or 0)/x["tvl"]) if x.get("tvl") else None
            st = ("very stable" if isinstance(sgv,(int,float)) and sgv<0.10 else
                  "stable" if isinstance(sgv,(int,float)) and sgv<0.30 else
                  "variable" if isinstance(sgv,(int,float)) and sgv<1.0 else
                  "erratic" if isinstance(sgv,(int,float)) else "&mdash;")
            stc = "ok" if st in ("very stable","stable") else "warn" if st=="variable" else "bad"
            toks = " ".join("<span class='addr' title='%s' data-copy='%s' data-full='%s'>%s</span>"
                             % (esc(t), esc(t), esc(t), esc(t[:6] + "\u2026" + t[-4:] if len(t) > 16 else t))
                             for t in (x.get("toks") or []))
            flags = ", ".join(x.get("fails") or []) or "&mdash;"
            # DRAWER TELEMETRY, NOT A REPEAT. The dense table is 30 columns; what a reader
            # expands it for is what the columns do not carry: raw contract addresses, the
            # metadata string, the exact reward-token set. Cells the page truncates for space
            # also emit data-full on the cell itself, and the drawer prefers that.
            _extra = ";".join([
                "pool meta:%s" % (x.get("meta") or ""),
                "days counted:%s" % (x.get("count") if x.get("count") is not None else ""),
                "IL risk band:%s" % (x.get("ilrisk") or ""),
                "exposure:%s" % (x.get("exposure") or ""),
            ])
            _extra = ";".join(p2 for p2 in _extra.split(";") if p2.split(":", 1)[-1].strip())
            H.append(
                "<tr%s><td><b>%s</b></td><td>%s</td><td class='dim'>%s</td>"
                "<td class='num ok'>%s</td><td class='num'>%s</td>"
                "<td class='num dim'>%s</td><td class='num dim'>%s</td>"
                "<td class='num dim'>%s</td><td class='num'>%s</td>"
                "<td class='num'>%s</td><td class='num'>%s</td>"
                "<td class='num dim'>%s</td><td class='num %s'>%s</td>"
                "<td class='num'>$%s</td><td class='num'>$%s</td>"
                "<td class='num'>$%s</td><td class='num'>%s</td>"
                "<td class='num dim'>%s</td><td class='dim'>%s</td><td class='dim'>%s</td>"
                "<td class='num dim'>%s</td><td class='%s'>%s</td>"
                "<td class='num dim'>%s</td><td>%s</td><td class='dim'>%s</td>"
                "<td class='dim'>%s</td><td class='dim'>%s</td><td class='dim'>%s</td></tr>"
                % (("; data-extra='%s'" % esc(_extra)) if _extra else "",
                   esc(x['symbol'])[:20], esc(x['project'])[:22], esc(x.get('chain') or ''),
                   _n(apy, "{:.2f}", "%"), _n(x.get('base'), "{:.2f}", "%"),
                   _n(rew, "{:.2f}", "%"), _n(emit, "{:.0f}", "%"),
                   _n(x.get('apy7'), "{:.2f}", "%"),
                   _n(x.get('d1'), "{:+.2f}", "%"), _n(x.get('d7'), "{:+.2f}", "%"),
                   _n(x.get('d30'), "{:+.2f}", "%"), _n(mean, "{:.2f}", "%"),
                   ("bad" if (vs is not None and vs < -20) else "warn" if (vs is not None and vs < 0) else "ok"),
                   _n(vs, "{:+.0f}", "%"),
                   "{:,.1f}M".format(x['tvl']/1e6),
                   "{:,.0f}".format(x['vol1']) if x.get('vol1') else "&mdash;",
                   "{:,.0f}".format(x['vol7']) if x.get('vol7') else "&mdash;",
                   _n(turn, "{:.2%}") if turn is not None else "&mdash;",
                   _n(x.get('il7d'), "{:.2f}", "%"), (esc(x.get('ilrisk')) if x.get('ilrisk') else '&mdash;'),
                   (esc(x.get('exposure')) if x.get('exposure') else '&mdash;'),
                   sig_txt, stc, st, _n(x.get('count'), "{:.0f}"),
                   pill(x['verdict']), flags,
                   (esc(x.get('meta')) if x.get('meta') else '&mdash;'),
                   toks or "&mdash;",
                   " ".join("<a href='%s' target='_blank' rel='noopener'%s>%s</a>"
                            % (esc(u), ttl, lbl) for lbl, u, ttl in
                            (("DL", (x.get('links') or {}).get('defillama'),
                              " title='the pool on DefiLlama, the source feed'"),
                             # The official protocol site is added HERE, at render time, from the
                             # protocol registry -- it is per-protocol, so carrying it per-row
                             # would repeat one URL 460 times. It is the only link that identifies
                             # the PROTOCOL rather than a token, which is why it survives while
                             # GeckoTerminal and DexScreener did not.
                             ("official", _off_url(x.get('project')),
                              " title='official site for %s'" % esc(x.get('project') or '')))
                            if u) or "&mdash;"))
        H.append("</table>")
        H.append("<div class='sub'>Sorted by yield stability. A tokenised treasury bill should barely "
                 "move, and the steadiest entries here (sigma 0.002) behave exactly as one would expect. "
                 "Matching is by keyword, so treat the count as directional rather than a census.</div>")

    H.append("</div>")
    # ---- pay per audit ----
    H.append("<div data-section='pricing'>")
    H.append("""<h2 id='sec-pricing' class='anchorable'>Pricing</h2>
<div class="price">
<div class="tier"><h3>Free</h3><div class="p">$0</div>
<ul><li>Unlimited browser audits of the scanned set</li>
<li>Full flag breakdown and due-diligence card</li>
<li>Top 80 real-yield pools with links</li>
<li>3 audits/day via the API</li></ul></div>
<div class="tier"><h3>Pay per audit</h3><div class="p">$0.05</div>
<ul><li>No subscription, no minimum</li>
<li>Every audit returns the full flag set</li>
<li>Prepaid credits, never expire</li>
<li>100 audits &rarr; $5</li></ul></div>
<div class="tier"><h3>Bulk</h3><div class="p">$0.01</div>
<ul><li>Per audit at 10,000+</li>
<li>Same endpoint, same output</li>
<li>For desks screening a whole chain</li>
<li>Contact for a key</li></ul></div>
</div>
<div class="note"><b>Monitoring without a recurring bill.</b> A desk that wants continuous coverage
buys volume: <b>10,000 audits for $100</b>, never expiring, run whenever. The economics of a monitoring
subscription, without the subscription. <b>Why per-audit rather than a subscription.</b> A subscription bills you in the months
you do not trade. A per-audit price means you pay when you are about to commit capital — which is exactly
when the answer is worth something. The API is the same engine the browser runs: <code>POST /audit</code>
returns the verdict and the flag list.</div>""")

    H.append("</div>")
    H.append("<div data-section='method'><h2 id='sec-method' class='anchorable'>Method &amp; honest scope</h2><div class='sub'>"
      "Six checks, each set by a measured failure: outlier flag &middot; reward share &gt;50% &middot; "
      "spot APY below 60% of the 7-day base &middot; TVL floor $1M &middot; turnover &lt;1%/day "
      "(applied only where volume data exists) &middot; stable-asset plausibility.<br><br>"
      "<b>The flags are current-state risk markers, not forecasts.</b> SUBSIDISED, THIN and OUTLIER "
      "describe what a pool looks like right now. They are not a claim about what it will do. "
      "<b>What this does not do:</b> it does not predict returns, does not place orders, and does not "
      "assess contract code. It also does <b>not</b> compute a net-of-LVR yield — that needs tick-level "
      "swap data this feed does not carry. Audit coverage is reported separately and is thin: most "
      "protocols publish no report. Severity counts in a report are findings <i>raised</i>, not "
      "necessarily unresolved.</div>")

    H.append("</div>")
    H.append("<script>")
    H.append("const DATA="+json.dumps(embed,separators=(',',':'))+";")
    H.append("const ADDR="+json.dumps(addr,separators=(',',':'))+";")
    H.append("const POOLS_SCANNED="+str(len(res))+";")
    H.append(open("screener/app.js").read())
    # Chat widget wiring. Fetches /api/chat (same origin) and renders the deterministic answer.
    # NOTE: this is appended INSIDE the page's single inline <script>, so it is raw JS, not a
    # nested <script> tag (a nested tag would close the outer script early).
    H.append(
        "function aegisChatInit(){"
        "var q=document.getElementById('chat-q');"
        "if(!q)return;"
        "var log=document.getElementById('chat-log');"
        "var btn=document.getElementById('chat-btn');"
        "function add(txt,who){var d=document.createElement('div');"
        "d.className='chat-bubble '+(who||'bot');d.textContent=txt;log.appendChild(d);"
        "log.scrollTop=log.scrollHeight;}"
        "function ask(){var v=(q.value||'').trim();if(!v)return;"
        "add(v,'user');q.value='';btn.disabled=true;"
        "fetch('api/chat?'+new URLSearchParams({q:v}))"
        ".then(function(r){return r.json();})"
        ".then(function(j){add(j.error?('error: '+j.error):j.answer,'bot');})"
        ".catch(function(e){add('error: '+e,'bot');})"
        ".finally(function(){btn.disabled=false;});}"
        "btn.addEventListener('click',ask);"
        "q.addEventListener('keydown',function(e){if(e.key==='Enter')ask();});"
        "var head=document.getElementById('chat-head');"
        "var toggle=document.getElementById('chat-toggle');"
        "var w=document.getElementById('chat-widget');"
        "head.addEventListener('click',function(){w.classList.toggle('min');"
        "toggle.textContent=w.classList.contains('min')?'show':'hide';});"
        "}"
        "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',aegisChatInit);}"
        "else{aegisChatInit();}")
    # table.js adds client-side sort + filter to every table. Loaded after app.js so both run
    # in the same single inline script; no second request, no external dependency.
    H.append(open("screener/table.js").read() if os.path.exists("screener/table.js") else "")
    H.append("</script></body></html>")
    open(out,"w").write("".join(H))
    print(f"wrote {out} ({os.path.getsize(out):,} bytes)")
if __name__=="__main__": build()

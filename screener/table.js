/* Aegis UI controller - vanilla JS, zero dependencies, zero network requests.
 *
 * Layers, each degrading independently so a failure in one never disables the others:
 *   1. sort        click a header to sort; numeric-aware, nulls sink
 *   2. filter      per-table box + a GLOBAL search in the top bar
 *   3. tabs        segmented view switch
 *   4. drawers     click a row to expand raw parameters
 *   5. monograms   inline CSS token badges (no images, no requests)
 *   6. meters      utilisation / LLTV / sigma micro-bars
 *
 * --------------------------------------------------------------------------------------------
 * THREE BUGS ALREADY FIXED HERE, all the same shape -- a marker or tag set before the work:
 *
 * (a) The first version required `table.tHead`. Only ONE of eight tables had a <thead> and the
 *     parser does not synthesise one, so `table.tHead` was null for seven of eight -- while the
 *     code set `data-interactive="1"` BEFORE the check that bailed. Seven tables marked handled,
 *     then abandoned: no filter box, no arrows, no retry. Headers are now DISCOVERED (fall back
 *     to the first row) and the marker is set only AFTER the work succeeds.
 *
 * (b) `table.rows` includes <thead> rows, so "skip row 0" hides the wrong row when a real
 *     <thead> exists. Every path filters by row IDENTITY, not index.
 *
 * (c) `header.cells.forEach(...)` -- HTMLCollection has no forEach. It threw on the first row and
 *     a surrounding try/catch swallowed it, so each table got ONE row marked expandable and no
 *     drawer. Route every collection through Array.prototype.forEach.call.
 *
 * WHY MONOGRAMS AND METERS ARE BUILT IN JS, NOT IN THE HTML:
 * The `util` and `LLTV` columns are emitted by lending_dashboard.py, and audit_parity.py parses
 * the rendered HTML with regexes that depend on that exact markup. Editing it to add bars would
 * risk the parity guarantee for a cosmetic gain. Decorating at RUNTIME keeps the static file
 * byte-identical to what parity checks, and the visual layer is rebuilt on every load.
 *
 * DELIBERATELY NOT DONE: webfonts and remote token logos. Both are network fetches, and "zero
 * external requests" is asserted by tests/test_export_report.py and tests/test_table.cjs.
 */
(function () {
  "use strict";

  var NUMRE = /-?\d[\d,]*\.?\d*/;

  function num(txt) {
    if (txt == null) return null;
    var t = String(txt).trim();
    if (!t) return null;
    var mult = 1;
    if (/[kK]\b|[kK]$/.test(t)) mult = 1e3;
    if (/[mM]\b|[mM]$/.test(t)) mult = 1e6;
    if (/[bB]\b|[bB]$/.test(t)) mult = 1e9;
    var m = t.match(NUMRE);
    if (!m) return null;
    var v = parseFloat(m[0].replace(/,/g, ""));
    return isNaN(v) ? null : v * mult;
  }

  function cellText(td) {
    if (!td) return "";
    return (td.getAttribute("data-sort") || td.textContent || "").trim();
  }

  function findHeader(table) {
    if (table.tHead && table.tHead.rows && table.tHead.rows.length) {
      var hr = table.tHead.rows[table.tHead.rows.length - 1];
      return { row: hr, cells: hr.cells, fromBody: false };
    }
    var body = table.tBodies && table.tBodies[0];
    var rows = body ? body.rows : table.rows;
    if (!rows || !rows.length) return null;
    var first = rows[0];
    if (!first.cells || !first.cells.length) return null;
    return { row: first, cells: first.cells, fromBody: true };
  }

  function dataRows(table, header) {
    var body = table.tBodies && table.tBodies[0];
    var all = Array.prototype.slice.call(body ? body.rows : table.rows);
    return all.filter(function (tr) {
      if (header && tr === header.row) return false;
      if (tr.getAttribute && tr.getAttribute("data-drawer") === "1") return false;
      return true;
    });
  }

  /* Column definitions. These are the ACTUAL thresholds from screen.py and lending_screen.py,
   * not descriptions of them -- a tooltip that paraphrases a rule can drift from the rule, and
   * this page exists to not do that. Every number here appears in those two files. */
  var DEFS_RAW = {
    "apy": "Advertised annual yield. Includes reward emissions, so a high value can be mostly token inflation.",
    "base": "Organic yield: fees or interest only, excluding reward emissions. The part that is not a subsidy.",
    "reward": "Yield from token emissions. Above 50% of total APY the pool is flagged SUBSIDISED.",
    "tvl": "Total value deposited. Below $1M a single exit moves the price.",
    "sigma (yield volatility)": "Standard deviation of the yield itself over the tracked window, not of the token price. Above 0.30 the yield is unstable.",
    "\u03c3": "Standard deviation of the yield itself over the tracked window, not of the token price. Above 0.30 the yield is unstable.",
    "days": "Days of continuous history. Under 30 the figures are not yet meaningful.",
    "stability": "Yield volatility band, derived from sigma.",
    "audit": "Whether a third-party audit report is published. THIN means coverage is minimal.",
    "pool": "The trading pair. Click the row for the full breakdown.",
    "project": "The protocol operating the pool.",
    "chain": "The network the pool is deployed on.",
    "links": "Outbound references: explorer, aggregator, audit.",
    "collateral": "The asset securing the borrow. If it depegs, the position can go bad.",
    "supplied": "Total USDC supplied to this market by lenders.",
    "net apy": "Supply APY after Morpho's own reward accounting. Already nets emissions.",
    "lltv": "Liquidation Loan-To-Value: the maximum borrow against collateral. Above 94.5% a small depeg can produce bad debt, because the margin (1 minus LLTV) is thin.",
    "util": "Share of supplied capital currently borrowed. Above 95% depositors cannot withdraw; 100% means the market is locked.",
    "liquidity": "Capital available to withdraw right now.",
    "unrealised": "Bad debt owed but not yet written off. It may still be recovered, so it is not the same as a loss.",
    "realised": "Bad debt written off. This is the loss actually taken, and it is the smaller number for a reason.",
    "% lost": "Share of supplied capital that is bad debt, outstanding plus realised.",
    "morpho flags": "Morpho's own warning labels, consumed as published rather than re-derived.",
    "rule": "The check that produced a flag.",
    "meaning": "What that check tests for.",
    "markets": "How many markets the check flagged.",
    "strategy": "The timing strategy tested.",
    "runs": "Independent simulation runs.",
    "beat": "Whether the strategy beat holding the asset.",
    "median alpha vs hodl": "Median excess return against buy-and-hold. Negative means the strategy lost to doing nothing.",
    "asset": "The asset held.",
    "buy & hold": "Return from simply holding, the baseline every strategy is measured against.",
    "strategies that beat it": "How many of the tested strategies outperformed holding.",
    "symbol": "The traded pair.",
    // the What-changed table (transition log)
    "run": "The immutable run this event was recorded in. Click to sort by time.",
    "block": "The Base block the run was fetched at. A transition spans the two blocks either side of this row.",
    "severity": "high = a market moved into AVOID, or utilisation crossed 90%. medium = a large utilisation move. warn = the interval itself is unreliable.",
    "market": "The collateral symbol whose state changed.",
    "transition": "What changed, as recorded by the diff between two consecutive runs.",
    "when (utc)": "Wall-clock time the run was logged.",
    "run": "The immutable run this was recorded in. Every run is replay-verified.",
    "block": "The Base block the run was fetched at.",
    "sev": "high = moved into AVOID or utilisation crossed 90%. medium = a large move. warn = the interval itself is unreliable.",
    "venue": "The lending protocol and the chain the market lives on.",
    "util from": "Utilisation before the change, as a fraction of supplied capital borrowed.",
    "util to": "Utilisation after the change. Above 95% depositors cannot withdraw.",
    "Δ": "The size of the utilisation move, in percentage points.",
    "borrowed": "Capital currently borrowed from this market.",
    "liquidity": "Capital available to withdraw right now.",
    "verdict": "The screen verdict for this market in that run.",
    "flags": "Which checks failed for this market in that run.",
    "oracle": "The oracle contract address the market prices collateral with.",
    "links": "Morpho opens the market; Basescan opens the collateral token, since a market id is a Morpho-internal key rather than an address.",
    // dense pool table
    "organic": "Yield from fees or interest only, excluding token emissions. The part that is not a subsidy.",
    "emissions": "Yield paid in the protocol's own token. Above 50% of total APY the pool is flagged SUBSIDISED.",
    "emit share": "Emissions as a share of advertised APY. The higher this is, the less of the number is real yield.",
    "7d base": "The organic rate averaged over the last 7 days. A large gap from spot means the current APY is a spike.",
    "\u03941d": "Change in advertised APY over 1 day.",
    "\u03947d": "Change in advertised APY over 7 days.",
    "\u039430d": "Change in advertised APY over 30 days.",
    "30d mean": "The mean APY over 30 days. The baseline the current rate should be judged against.",
    "vs mean": "Current APY against its own 30-day mean. Negative means the yield is BELOW its own recent average, which a spot figure hides.",
    "vol 24h": "Value traded in the last 24 hours.",
    "vol 7d": "Value traded over 7 days.",
    "turnover/d": "Daily volume as a share of TVL. Low turnover means fees cannot pay depositors, so yield must come from emissions.",
    "il 7d": "Estimated 7-day impermanent loss for an LP in this pool. Non-zero means the position can lose value while the yield is positive.",
    "il risk": "The feed's own impermanent-loss risk band. Consumed as published, not re-derived.",
    "exposure": "How the pool's value is exposed, as the feed classifies it.",
    "reward tokens": "The tokens paid as emissions. Several means the yield depends on more than one price.",
    "underlying": "The contract addresses of the assets in the pool.",
    "\u03c3": "Standard deviation of the YIELD itself, not the token price. Above 0.30 the income is unstable even if the average is high.",

    /* --- the forward-stress table. These are MODELLED quantities, and the definitions say so:
       a reader must not mistake a simulated probability for a measured one. --- */
    "ltv": "Loan-to-value now: borrow / collateral at the current oracle price. Lower is safer; the margin to liquidation is 1 - LTV/LLTV.",
    "margin": "How far the collateral price may fall before LTV reaches LLTV. 50% means the price can halve before the position is liquidatable.",
    "1d": "MODELLED probability of breaching LLTV within one day, from a lognormal simulation at this market's measured volatility. Not a forecast.",
    "7d": "MODELLED probability of breaching LLTV within seven days. Same simulation; it EXCLUDES cascade risk because markets are simulated independently.",
    "30d breach": "MODELLED probability of breaching LLTV within 30 days. Independent lognormal paths at the market's own volatility, so a real cascade is understated.",
    "vol source": "'recomputed' means the raw price series was re-read and annualised at its true sampling cadence; 'stored' means the older value had to be used and may be inflated.",

    /* --- the liquidation table. Seized and repaid are in their OWN asset's decimals; a
       generic sentence here would hide that the first read of this data divided everything
       by 1e6 and produced "$1.4T seized in 30 minutes". --- */
    "seized": "Collateral taken by the liquidator, in the COLLATERAL asset's own decimals (WETH 18dp, SOL 9dp). Never summed with repaid: they are different units.",
    "repaid": "Debt actually extinguished, in the LOAN asset's decimals (USDC 6dp).",
    "bad debt": "The shortfall this one liquidation could not cover, in the LOAN asset's decimals. Above 0 the market took a loss beyond the collateral's value -- the real signal.",
    "day": "The UTC day the liquidations landed on. A day with no covered event is omitted, so the rows are coverage, not run-history.",
    "covered": "Liquidations that landed on a market the screen had ALREADY verdict-ed before the event. The count the forward test tracks.",
    "avoid": "Of the covered events, how many hit a market the screen had flagged AVOID at the newest run before the liquidation. Zero is a measurement, not a miss.",
    "caution": "Of the covered events, how many hit a CAUTION market at the newest run before the liquidation.",
    "real": "Of the covered events, how many hit a REAL market. Expected to be the majority: liquidations are the mechanism of healthy lending, not its failure.",
    "bad-debt": "How many covered events landed on a market where the liquidation could not cover the full debt (a real loss taken). Zero in the series so far, and reported as such.",
    "bad-debt": "How many covered events landed on a market where the liquidation could not cover the full debt (a real loss taken). Zero in the series so far, and reported as such.",
    /* --- the forward-test coverage series (task B+). Append-only daily buckets. --- */
    "day": "The UTC day the liquidations landed on. A day with no covered event is omitted, so the rows are coverage, not run-history.",
    "covered": "Liquidations that landed on a market the screen had ALREADY verdict-ed before the event. The count the forward test tracks.",
    "avoid": "Of the covered events, how many hit a market the screen had flagged AVOID at the newest run before the liquidation. Zero is a measurement, not a miss.",
    "caution": "Of the covered events, how many hit a CAUTION market at the newest run before the liquidation.",
    "real": "Of the covered events, how many hit a REAL market. Expected to be the majority: liquidations are the mechanism of healthy lending, not its failure.",
    "tx": "The transaction hash, truncated here. Click to copy the full hash.",
    /* --- the runway table. An identity, not a forecast, and the definitions say so. --- */
    "utilisation": "Borrowed share of supplied capital. At 95% the market locks and depositors cannot withdraw, however deep the headline TVL looks.",
    "runway$": "Dollars of supply that can still be withdrawn before utilisation reaches 95%: supply - borrow/0.95. An accounting identity on two published numbers, NOT a forecast of when they will leave.",
    "target$": "What the allocator assigned after capping the position to half the runway. A dollar budget, not a percentage.",
    "occupancy": "Share of the available runway this one position occupies. Above 1.0 it cannot leave without freezing the market for everyone behind it.",

    /* --- regime segmentation --- */
    "regime": "ACTIVE = utilisation moves, so the series carries information. QUIESCENT = flat and genuinely idle. FROZEN = flat because it is pinned at the 100% ceiling and cannot move.",
    "range": "Total spread of utilisation across the whole stored history. Under 0.1 percentage points the series carries no signal at all, whatever its current level.",
    "max move": "Largest single-interval change in utilisation. A large value means the market can move fast enough to matter between two alerts.",
    ">5pp": "How many single polling intervals moved utilisation by more than 5 percentage points.",

    /* --- the all-venues lending table. It uses short header names, so the definitions are
       keyed on those names rather than assuming the longer ones elsewhere match. --- */
    "venue": "The DefiLlama protocol slug. Category is joined from api.llama.fi/protocols, which resolved every pool rather than most.",
    "rew": "Yield from token emissions. A high reward share means the rate ends when the incentives do, so it is not a rate to underwrite.",
    "sigma": "Standard deviation of the YIELD itself, not the token price. Above 0.30 the income is unstable even when its average looks attractive.",
    "days": "How many days this pool has been tracked. A short history means the advertised rate has not survived a full cycle.",
    "verdict": "The screen's own verdict for this pool, from the same rules applied to the AMM side."
  };

  // Keys are lowercased at build time. Labels are lowercased before lookup, and case folding
  // is not identity for every alphabet: "Δ".toLowerCase() is "δ", so a key stored as "Δ" never
  // matched its own header. Normalising BOTH sides is the only version that cannot drift.
  var DEFS = {};
  (function () {
    for (var k in DEFS_RAW) {
      if (Object.prototype.hasOwnProperty.call(DEFS_RAW, k)) {
        DEFS[k.replace(/\s+/g, " ").toLowerCase()] = DEFS_RAW[k];
      }
    }
  })();

  function defFor(label) {
    // The header text is whatever the DOM holds, which for entities like &Delta; is the
    // rendered glyph -- but a definition keyed on the glyph missed when the source emitted the
    // entity form. Decode entities first so both forms resolve to the same key.
    var raw = String(label || "");
    if (raw.indexOf("&") !== -1 && raw.indexOf(";") !== -1) {
      var ta = document.createElement("textarea");
      ta.innerHTML = raw;
      raw = ta.value;
    }
    // Collapse ALL whitespace, including the non-breaking space a rendered &nbsp; becomes.
    // "emit share" in the source arrives as "emit\u00a0share" in the DOM, so a plain-space
    // key never matched -- the same class of miss as the &Delta; entity and the case-folding.
    var key = raw.replace(/[\u2191\u2193]/g, "").replace(/\s+/g, " ").trim().toLowerCase();
    if (DEFS[key]) return DEFS[key];
    // a definition that is merely missing is better than one that is invented
    return "Sorts this column. No definition is recorded for \u201c" + key + "\u201d.";
  }

  function headerLabels(table, header) {
    return Array.prototype.map.call(header.cells, function (th) {
      return (th.textContent || "").replace(/[\u2191\u2193]/g, "").trim().toLowerCase();
    });
  }

  /* ------------------------------------------------------------------ monograms */

  function mono(sym) {
    var s = String(sym || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    if (!s) return "?";
    if (s.length <= 2) return s;
    return s.charAt(s.length - 1);   // cbBTC -> B, wstETH -> W, USDC -> C
  }

  var KNOWN = {
    BTC: "#f7931a", ETH: "#627eea", USDC: "#2775ca", USDT: "#26a17b", DAI: "#f5ac37",
    SOL: "#14f195", XRP: "#23292f", ADA: "#0033ad", DOGE: "#c2a633", LTC: "#345d9d",
    ZEC: "#ecb244", AERO: "#1f6feb", USDE: "#00d395", WSTETH: "#00a3ff", CBETH: "#627eea",
    LBTC: "#f7931a", JITOSOL: "#14f195", CBBTC: "#f7931a", CBXRP: "#23292f",
    CBADA: "#0033ad", CBDOGE: "#c2a633", CBLTC: "#345d9d", CBZEC: "#ecb244"
  };

  function hue(sym) {
    var s = String(sym || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    var h = 0;
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return h;
  }

  function badge(sym) {
    var raw = String(sym || "").trim();
    if (!raw) return null;
    var key = raw.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    var col = KNOWN[key];
    var style;
    if (col) {
      style = "color:" + col + ";border-color:" + col + "55;background:" + col + "1f";
    } else {
      var h = hue(raw);
      style = "color:hsl(" + h + " 70% 65%);border-color:hsl(" + h + " 70% 55% / .35);" +
              "background:hsl(" + h + " 70% 55% / .12)";
    }
    var span = document.createElement("span");
    span.className = "token-badge";
    span.setAttribute("style", style);
    span.setAttribute("aria-hidden", "true");
    span.textContent = mono(raw);
    return span;
  }

  /* The cell's text is wrapped in a plain span so the badge glyph is NOT part of the token's
   * text content. Otherwise sorting would see "BcbBTC" and the filter would match on "B". */
  function addBadges(table, header) {
    var labels = headerLabels(table, header);
    var ci = -1;
    for (var i = 0; i < labels.length; i++) {
      if (labels[i] === "collateral" || labels[i] === "symbol") { ci = i; break; }
    }
    if (ci < 0) return 0;
    var n = 0;
    dataRows(table, header).forEach(function (tr) {
      var td = tr.cells[ci];
      if (!td || td.querySelector(".token-badge")) return;
      var sym = (td.textContent || "").trim();
      if (!sym || sym.length > 24) return;
      var b = badge(sym);
      if (!b) return;
      var wrap = document.createElement("span");
      wrap.className = "sym";
      while (td.firstChild) wrap.appendChild(td.firstChild);
      td.appendChild(b);
      td.appendChild(wrap);
      td.setAttribute("data-sort", sym);
      n++;
    });
    return n;
  }

  /* ------------------------------------------------------------------ meters */

  function meter(pct, cls) {
    var w = document.createElement("span");
    w.className = "bar-wrap";
    w.setAttribute("aria-hidden", "true");
    var f = document.createElement("span");
    f.className = "bar-fill " + cls;
    f.style.width = Math.max(0, Math.min(100, pct)).toFixed(1) + "%";
    w.appendChild(f);
    return w;
  }

  /* Thresholds come from lending_screen.py so the bar and the verdict cannot disagree:
   * MAX_UTILIZATION = 0.95 (above it depositors cannot exit), MAX_LLTV = 0.945. */
  function addUtilBars(table, header) {
    var labels = headerLabels(table, header);
    var ci = labels.indexOf("util");
    if (ci < 0) return 0;
    var n = 0;
    dataRows(table, header).forEach(function (tr) {
      var td = tr.cells[ci];
      if (!td || td.querySelector(".bar-wrap")) return;
      var v = num(cellText(td));
      if (v === null) return;
      var pct = (v <= 1.0001) ? v * 100 : v;   // stored as a fraction; guard both
      var cls = pct >= 95 ? "bad" : pct >= 90 ? "warn" : "safe";
      td.appendChild(meter(pct, cls));
      n++;
    });
    return n;
  }

  function addLltvBars(table, header) {
    var labels = headerLabels(table, header);
    var ci = labels.indexOf("lltv");
    if (ci < 0) return 0;
    var n = 0;
    dataRows(table, header).forEach(function (tr) {
      var td = tr.cells[ci];
      if (!td || td.querySelector(".bar-wrap")) return;
      var v = num(cellText(td));
      if (v === null) return;
      var pct = (v <= 1.0001) ? v * 100 : v;
      var cls = pct >= 94.5 ? "bad" : pct >= 85 ? "warn" : "safe";
      td.appendChild(meter(pct, cls));
      n++;
    });
    return n;
  }

  /* sigma-to-breach: LOWER is riskier. The allocator's SIGMA_FLOOR is 2.0; a full bar means
   * comfortable, so the bar shows distance from the floor rather than the raw value. */
  function addSigmaBars(table, header) {
    var labels = headerLabels(table, header);
    var ci = -1;
    for (var i = 0; i < labels.length; i++) {
      if (labels[i].indexOf("sigma") === 0 || labels[i] === "\u03c3") { ci = i; break; }
    }
    if (ci < 0) return 0;
    var n = 0;
    dataRows(table, header).forEach(function (tr) {
      var td = tr.cells[ci];
      if (!td || td.querySelector(".bar-wrap")) return;
      var v = num(cellText(td));
      if (v === null) return;
      var shown = (v / 4) * 100;   // 4 sigma fills the bar
      var cls = v < 1 ? "bad" : v < 2 ? "warn" : "safe";
      td.appendChild(meter(shown, cls));
      n++;
    });
    return n;
  }

  /* ------------------------------------------------------------------ sorting */

  function sortTable(table, header, idx, dir) {
    var rows = dataRows(table, header);
    if (!rows.length) return;

    var numeric = true, any = false;
    var keys = rows.map(function (tr) {
      var td = tr.cells && tr.cells[idx];
      if (!td) return null;
      var n = num(cellText(td));
      if (n === null) { numeric = false; return null; }
      any = true;
      return n;
    });
    if (!numeric || !any) {
      keys = rows.map(function (tr) {
        var td = tr.cells && tr.cells[idx];
        return cellText(td).toLowerCase();
      });
    }

    var order = rows.map(function (tr, i) { return [keys[i], tr, i]; });
    order.sort(function (a, b) {
      var x = a[0], y = b[0];
      var xn = (x === null || x === ""), yn = (y === null || y === "");
      if (xn && yn) return a[2] - b[2];
      if (xn) return 1;
      if (yn) return -1;
      if (typeof x === "number" && typeof y === "number") {
        return (dir * (x - y)) || (a[2] - b[2]);
      }
      return (dir * String(x).localeCompare(String(y))) || (a[2] - b[2]);
    });
    var host = (table.tBodies && table.tBodies[0]) || table;
    order.forEach(function (o) {
      host.appendChild(o[1]);
      var d = o[1].__drawer;
      if (d) host.appendChild(d);
    });
  }

  /* ------------------------------------------------------------------ drawers */

  /* A DRAWER THAT ADDS, NOT REPEATS (dense-table rule). The old drawer walked every visible
   * column and printed label + value for each — a vertical copy of the row the reader had just
   * clicked, contributing nothing the row did not already show, on 602 rows.
   *
   * It now does three things instead:
   *   1. data-full on any cell (truncated addresses, long USD) emits label + FULL value.
   *   2. data-extra="k=v;k=v" from the emitting Python adds telemetry the table has no column
   *      for (30-day APY baseline, impermanent loss, reward tokens, contract addresses...).
   *   3. only when neither exists does it fall back to the column walk — so no drawer is ever
   *      emptier than what the row shows.
   */
  function buildDrawer(table, header, tr) {
    var d = document.createElement("tr");
    d.setAttribute("data-drawer", "1");
    d.className = "drawer-row";
    var td = document.createElement("td");
    td.colSpan = header.cells.length;
    var dl = document.createElement("div");
    dl.className = "drawer";
    var n = 0;
    // -- 1. cells whose visible value was truncated for space
    Array.prototype.forEach.call(header.cells, function (th, ci) {
      var cell = tr.cells[ci];
      if (!cell) return;
      var full = cell.getAttribute("data-full");
      if (!full) return;
      var label = (th.textContent || "").replace(/[\u2191\u2193]/g, "").trim() || ("col " + (ci + 1));
      var row = document.createElement("div");
      row.className = "drow";
      var k = document.createElement("span"); k.className = "dk"; k.textContent = label;
      var v = document.createElement("span"); v.className = "dv"; v.textContent = full;
      row.appendChild(k); row.appendChild(v); dl.appendChild(row); n++;
    });
    // -- 2. telemetry the emitting page carried but the table has no column for
    (tr.getAttribute("data-extra") || "").split(";").forEach(function (kv) {
      if (!kv) return;
      var i = kv.indexOf(":");
      var k = i > 0 ? kv.slice(0, i) : kv, v = i > 0 ? kv.slice(i + 1) : "";
      if (!v) return;
      var row = document.createElement("div");
      row.className = "drow";
      var kk = document.createElement("span"); kk.className = "dk"; kk.textContent = k;
      var vv = document.createElement("span"); vv.className = "dv"; vv.textContent = v;
      row.appendChild(kk); row.appendChild(vv); dl.appendChild(row); n++;
    });
    // -- 3. fallback: the previous behaviour, for tables with neither attribute
    if (!n) {
      Array.prototype.forEach.call(header.cells, function (th, ci) {
        var label = (th.textContent || "").replace(/[\u2191\u2193]/g, "").trim();
        var val = tr.cells[ci] ? tr.cells[ci].innerHTML : "";
        if (!label && !val) return;
        var row = document.createElement("div");
        row.className = "drow";
        var k = document.createElement("span"); k.className = "dk"; k.textContent = label || ("col " + (ci + 1));
        var v = document.createElement("span"); v.className = "dv"; v.innerHTML = val;
        row.appendChild(k); row.appendChild(v); dl.appendChild(row);
      });
    }
    td.appendChild(dl);
    d.appendChild(td);
    tr.__drawer = d;
    d.style.display = "none";
    return d;
  }

  function wireDrawers(table, header) {
    var rows = dataRows(table, header);
    if (!rows.length || header.cells.length < 4) return 0;
    var n = 0;
    rows.forEach(function (tr) {
      if (tr.getAttribute("data-expandable") === "1") return;
      tr.setAttribute("data-expandable", "1");
      tr.classList.add("expandable");
      var d = buildDrawer(table, header, tr);
      var host = (table.tBodies && table.tBodies[0]) || table;
      if (tr.nextSibling) host.insertBefore(d, tr.nextSibling); else host.appendChild(d);
      // KEYBOARD + SCREEN READER. Measured: 602 expandable rows, ZERO with tabindex and ZERO with
      // aria-expanded. A drawer could only be opened with a pointer, and once open nothing
      // announced it -- so its contents (the raw parameters, the main reason to expand) were
      // unreachable non-visually. `aria-expanded` is the correct state for a disclosure control;
      // `aria-sort` belongs on the sortable <th>, not here.
      tr.setAttribute("tabindex", "0");
      tr.setAttribute("aria-expanded", "false");
      tr.setAttribute("role", "button");   // a row acting as a disclosure control

      var toggleRow = function () {
        var wasOpen = tr.classList.contains("open");
        // FOCUS MUST NOT BE STRANDED IN A HIDDEN SUBTREE. MEASURED: focus an anchor inside an open
        // drawer, close it, and focus stays on the now-hidden anchor -- so the next Tab continues
        // from inside a display:none subtree and the reader is lost. When the drawer closes and
        // focus was inside it, return focus to the disclosure row that owns it. That row is the
        // control the user just activated, so it is where they expect to be.
        if (wasOpen && tr.__drawer && typeof document !== "undefined"
            && document.activeElement && tr.__drawer.contains
            && tr.__drawer.contains(document.activeElement)) {
          // preventScroll: the drawer's host is a .scrollwin container with overflow-y. Focusing a
          // row near the top of a tall drawer would otherwise scroll the container abruptly, so the
          // restoration itself becomes a disorienting jump. Older engines ignore the options
          // object rather than throwing, hence the two-step.
          //
          // HONEST LIMIT: this CANNOT be verified in jsdom, which has no layout engine -- every
          // geometry reports 0 and focus never scrolls. The option is correct by specification and
          // unproven by test. Stated rather than implied.
          try { tr.focus({ preventScroll: true }); } catch (e) { try { tr.focus(); } catch (e2) {} }
        }
        tr.classList.toggle("open", !wasOpen);
        var isOpen = tr.classList.contains("open");
        tr.setAttribute("aria-expanded", isOpen ? "true" : "false");
        var box = table.previousElementSibling;
        var q = (box && box.tagName === "INPUT" && box.className.indexOf("tfilter") !== -1)
                ? (box.value || "").trim().toLowerCase() : "";
        if (typeof applyVisibility === "function") applyVisibility(table, header, q);
      };

      tr.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
        e.preventDefault();          // Space would otherwise scroll the window
        toggleRow();
      });

      tr.addEventListener("click", function (e) {
        var t = e.target;
        while (t && t !== tr) {
          if (t.tagName === "A" || t.tagName === "INPUT") return;
          t = t.parentNode;
        }
        // THE CLASS IS THE STATE; the display is DERIVED. Previously this read the inline
        // display to decide the next state AND wrote it, while applyVisibility() also wrote it --
        // two readers and two writers of one property, the same defect as the filter/tab clash and
        // the drawer/filter clash before it. MEASURED after filter + clear: display:none while
        // class said "open", so the first click afterwards opened an already-"open" drawer and the
        // state was inverted until the next click.
        //
        // The handler records INTENT once, in one place, and delegates the projection to the single
        // executor. Writing styles here is what made it a second writer.
        toggleRow();
      });
      n++;
    });
    return n;
  }

  /* ------------------------------------------------------------------ filtering */

  /* ------------------------------------------------------------------ visibility
   *
   * TWO INDEPENDENT DIMENSIONS DECIDE WHETHER A ROW IS SHOWN: the chain tab and the text filter.
   * They used to each write `tr.style.display` directly, and neither knew the other's state. Two
   * measured consequences:
   *
   *   1. applyFilter set display = "" on matching rows, which CLEARS the inline display:none the
   *      chain layer had set. Typing a filter made the 15 data-extra rows visible and clearing the
   *      filter left them visible -- a transient action made a permanent change.
   *   2. With a chain tab active, applying and then clearing a global search restored EVERY row
   *      (443) instead of that tab's subset (36), while the tab still read aria-selected="true".
   *      The UI claimed a filter it was not applying.
   *
   * Both are the same defect: a shared CSS property with two uncoordinated writers. The fix is to
   * make visibility a FUNCTION OF STATE rather than a mutation each handler performs. Every
   * dimension declares its predicate; one function evaluates them together. Adding a third
   * dimension then cannot clobber the first two.
   */
  var VIS = { chain: null, watch: false, time: null, verdict: null };
  // chain tab + watchlist + time floor + VERDICT quick-filter (the sidebar)

  /* ------------------------------------------------------------------ watchlist
   *
   * A client-side pin, persisted to localStorage. Nothing leaves the browser: no server, no
   * network, no database. The page's flat-JSON/no-DB contract is preserved because the pin is
   * the READER's state, not the project's. A stable key is derived from the row's own leading
   * cells (venue|chain|symbol), so a pin survives a reload of the SAME build; it is not a
   * contract address and it is not claimed to be one.
   */
  var WATCH_KEY = "aegis.watchlist.v1";

  function watchStore() {
    try {
      var s = window.localStorage && window.localStorage.getItem(WATCH_KEY);
      return s ? JSON.parse(s) : [];
    } catch (e) { return []; }
  }

  function saveWatch(list) {
    try { window.localStorage && window.localStorage.setItem(WATCH_KEY, JSON.stringify(list)); } catch (e) {}
  }

  /* A stable-enough row key: the first three cells, collapsed. Two rows that differ only in a
   * numeric column still pin separately, because the leading cells identify the instrument. */
  function pinKey(tr) {
    var parts = [];
    for (var i = 0; i < Math.min(3, tr.cells.length); i++) {
      var t = (tr.cells[i] && tr.cells[i].textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
      if (t) parts.push(t);
    }
    return parts.join("|");
  }

  function isPinned(tr) {
    var k = tr.getAttribute("data-pin-key");
    return k ? watchStore().indexOf(k) !== -1 : false;
  }

  function togglePin(tr) {
    var k = tr.getAttribute("data-pin-key");
    if (!k) return false;
    var list = watchStore();
    var i = list.indexOf(k);
    var now;
    if (i === -1) { list.push(k); now = true; }
    else { list.splice(i, 1); now = false; }
    saveWatch(list);
    tr.classList.toggle("pinned", now);
    var b = tr.querySelector(".pin");
    if (b) { b.setAttribute("aria-pressed", now ? "true" : "false"); b.textContent = now ? "★" : "☆"; }
    return now;
  }


  function rowWanted(tr, q) {
    // a drawer follows its parent row and is handled by the caller
    if (tr.getAttribute("data-drawer") === "1") return false;

    // dimension 1: chain tab
    if (tr.getAttribute("data-chain")) {
      var c = tr.getAttribute("data-chain");
      var extra = tr.getAttribute("data-extra-row") === "1";
      var other = tr.getAttribute("data-other") === "1";
      if (!VIS.chain) {
        if (extra) return false;                       // default view hides the extras
      } else if (VIS.chain === "other") {
        if (!other) return false;
      } else if (c !== VIS.chain) {
        return false;
      }
    }

    // dimension 2: watchlist. May only ever SUBTRACT, like the text filter.
    if (VIS.watch && !isPinned(tr)) return false;

    // dimension 3: time floor (the transitions slider). Only rows that carry a data-when
    // epoch participate; every other row is unaffected by the slider.
    if (VIS.time !== null) {
      var w = tr.getAttribute("data-when");
      if (w !== null && w !== "" && parseInt(w, 10) < VIS.time) return false;
    }

    // dimension 4: VERDICT quick-filter (the sidebar). Rows opt in by declaring
    // data-verdict, stamped at build time (glance table) or derived from their pill
    // cell at decorate time (transitions table). A row with no verdict is not hidden
    // by the verdict filter -- the filter is about choosing among judged rows, and
    // an unjudged row (a rule-count row, an address row) is not the sidebar's business.
    if (VIS.verdict) {
      var vd = tr.getAttribute("data-verdict");
      if (vd !== null && vd !== "" && vd !== VIS.verdict) return false;
    }

    // dimension 5: text filter. It may only ever SUBTRACT.
    if (q) {
      var hay = (tr.getAttribute("data-rowtext") || tr.textContent || "").toLowerCase();
      if (hay.indexOf(q) === -1) return false;
    }
    return true;
  }

  /* Re-evaluate EVERY managed row in a table against all dimensions at once. */
  function applyVisibility(table, header, q) {
    var rows = dataRows(table, header);
    var shown = 0;
    Array.prototype.forEach.call(table.tBodies && table.tBodies[0]
                                 ? table.tBodies[0].rows : table.rows, function (tr) {
      // A DRAWER ROW IS DECIDED BY ITS PARENT, NOT BY ITSELF. This branch used to force
      // display:none, which then CLOBBERED the parent's decision: the parent is visited first and
      // shows its drawer, then the loop reaches the drawer row itself and hides it again. Measured
      // symptom: clicking a row set class="open" but the drawer stayed invisible, because two
      // iterations of the same loop disagreed and the last one won. Skip it entirely -- the parent
      // owns it.
      if (tr.getAttribute("data-drawer") === "1") return;
      var isHeader = (header && tr === header.row);
      if (isHeader) return;
      var want = rowWanted(tr, q);
      // SEARCH THE DRAWER TOO. A drawer holds the raw parameters -- the reason to expand -- and
      // filtering did not see them: a query matching only drawer text hid the parent, and with it
      // the matching content. Stamping `data-rowtext` once per evaluation merges both, and the
      // attribute is what rowWanted() prefers, so the searchable text is the whole disclosure.
      if (tr.__drawer) {
        // INDEX THE DRAWER'S VALUES, NOT ITS LABELS. Merging the whole drawer made every row match
        // any header word -- the drawer repeats the column labels ("when", "run", "block", ...), so
        // searching "when" matched all 457 rows and the filter stopped filtering. Measured: the
        // first draft of this fix made section 5 fail with "no row was hidden".
        //
        // The values live in .dv spans; the labels in .dk. Only the values are content a reader
        // would search for.
        var vals = tr.__drawer.querySelectorAll ? tr.__drawer.querySelectorAll(".dv") : [];
        var extra = "";
        Array.prototype.forEach.call(vals, function (v) { extra += " " + (v.textContent || ""); });
        tr.setAttribute("data-rowtext", (tr.textContent || "") + " " + extra);
      }
      tr.style.display = want ? "" : "none";
      // A DRAWER IS VISIBLE IFF its parent row is visible AND it is open. Both conditions are read
      // from state -- the parent's computed visibility and the class -- never from the drawer's
      // own inline style. This is what the previous version got wrong: it only ever HID drawers,
      // never restored one, so a drawer open before a filter stayed hidden after the filter
      // cleared while its class still claimed "open".
      if (tr.__drawer) {
        tr.__drawer.style.display = (want && tr.classList.contains("open")) ? "" : "none";
      }
      if (want) shown++;
    });
    return shown;
  }

  function applyFilter(table, header, q) {
    // One of two dimensions; applyVisibility evaluates them together.
    return applyVisibility(table, header, q);
  }

  /* Attach a pin control to each data row. The row keeps its click-to-expand behaviour; the
   * pin is a small star in its own cell so a tap targets the star, not the disclosure. */
  function wirePins(table, header) {
    // The pin column is APPENDED, never prepended: sort/badge/meter logic indexes every cell by
    // header.cells[i], so inserting a cell at the front would shift every column and break all
    // of them. A trailing column leaves the existing indices untouched. A matching empty <th>
    // keeps the header and the body aligned.
    if (!header.row.querySelector(".pin-head")) {
      var th = document.createElement("th");
      th.className = "pin-head";
      th.setAttribute("aria-label", "watchlist");
      header.row.appendChild(th);
    }
    var n = 0;
    dataRows(table, header).forEach(function (tr) {
      if (tr.querySelector(".pin")) return;
      var k = pinKey(tr);
      if (!k) return;
      tr.setAttribute("data-pin-key", k);
      if (isPinned(tr)) tr.classList.add("pinned");
      var cell = document.createElement("td");
      cell.className = "pin-cell";
      var b = document.createElement("button");
      b.type = "button";
      b.className = "pin";
      b.textContent = isPinned(tr) ? "★" : "☆";
      b.setAttribute("aria-pressed", isPinned(tr) ? "true" : "false");
      b.setAttribute("aria-label", "pin this row to the watchlist");
      b.addEventListener("click", function (e) {
        e.stopPropagation();          // do not open the drawer
        togglePin(tr);
        // re-evaluate visibility so the watch toggle hides a just-unpinned row immediately
        var box = table.previousElementSibling;
        var q = (box && box.tagName === "INPUT" && box.className.indexOf("tfilter") !== -1)
                ? (box.value || "").trim().toLowerCase() : "";
        applyVisibility(table, header, q);
      });
      cell.appendChild(b);
      tr.appendChild(cell);
      n++;
    });
    return n;
  }

  function decorate(table) {
    if (table.getAttribute("data-interactive") === "1") return;

    var header = findHeader(table);
    if (!header) return;

    var did = 0;
    Array.prototype.forEach.call(header.cells, function (th, i) {
      if (th.querySelector && th.querySelector(".sort-arrow")) return;
      // NOT role="button". A <th> is implicitly a columnheader, and THAT is the only role on
      // which aria-sort is supported -- role="button" REPLACES columnheader, so an aria-sort put
      // there is ignored by assistive technology. Marking it a button would have shipped markup
      // that looks accessible and announces nothing.
      //
      // The element keeps its columnheader role and gains aria-sort (the standard way a sortable
      // grid column is expressed). It stays keyboard-operable because the keydown handler below
      // and tabindex remain; a columnheader is not focusable by default, so tabindex is required.
      th.setAttribute("tabindex", "0");
      th.setAttribute("aria-sort", "none");
      th.setAttribute("aria-label", (th.textContent || "").trim() + " \u2014 " + defFor(th.textContent));
      th.title = defFor(th.textContent);
      var arrow = document.createElement("span");
      arrow.className = "sort-arrow";
      arrow.textContent = "";
      th.appendChild(arrow);

      function toggle() {
        var dir = th.getAttribute("data-sort-dir") === "asc" ? -1 : 1;
        Array.prototype.forEach.call(header.cells, function (o) {
          o.removeAttribute("data-sort-dir");
          // a column that is no longer the sort key must say so, or a screen reader reports a
          // stale sort on every other column
          if (o.hasAttribute("aria-sort")) o.setAttribute("aria-sort", "none");
          var a = o.querySelector ? o.querySelector(".sort-arrow") : null;
          if (a) a.textContent = "";
        });
        th.setAttribute("data-sort-dir", dir === 1 ? "asc" : "desc");
        // aria-sort uses the words "ascending"/"descending"; data-sort-dir uses "asc"/"desc". Both
        // are set, and the test asserts they AGREE rather than trusting that they do.
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        arrow.textContent = dir === 1 ? " \u2191" : " \u2193";
        try { sortTable(table, header, i, dir); } catch (e) {}
      }
      th.addEventListener("click", toggle);
      th.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
      did++;
    });
    if (!did) return;

    // decorative layers. Independent: a failure in one must not stop the others.
    try { addBadges(table, header); } catch (e) {}
    try { addUtilBars(table, header); } catch (e) {}
    try { addLltvBars(table, header); } catch (e) {}
    try { addSigmaBars(table, header); } catch (e) {}
    try { wirePins(table, header); } catch (e) {}

    // numeric alignment, probed AFTER decoration so badge glyphs cannot skew detection
    var probe = dataRows(table, header).slice(0, 8);
    Array.prototype.forEach.call(header.cells, function (th, i) {
      var n = 0, t = 0;
      probe.forEach(function (tr) {
        if (!tr.cells[i]) return;
        t++;
        if (num(cellText(tr.cells[i])) !== null) n++;
      });
      if (t && n / t >= 0.6) {
        th.classList.add("num");
        dataRows(table, header).forEach(function (tr) {
          if (tr.cells[i]) tr.cells[i].classList.add("num");
        });
      }
    });

    var box = document.createElement("input");
    box.type = "search";
    box.className = "tfilter";
    box.placeholder = "filter rows\u2026";
    box.setAttribute("aria-label", "filter rows in this table");
    box.addEventListener("input", function () {
      applyFilter(table, header, box.value.trim().toLowerCase());
    });
    if (table.parentNode) table.parentNode.insertBefore(box, table);

    table.__aegis = { header: header, box: box, filter: function (q) {
      box.value = q; applyFilter(table, header, (q || "").toLowerCase());
    } };
    try { wireDrawers(table, header); } catch (e) {}

    table.setAttribute("data-interactive", "1");

    // bound the height LAST, once the rows exist and the header is known
    if (table.classList.contains("dense")) {
      try { applyWindow(table); } catch (e) {}
    }
  }

  /* ------------------------------------------------------------------ tabs */

  /* A chain tab selects ROWS, not sections. The pools table applies two gates (REAL verdict,
   * >$10M TVL) and sorts by APY, so an entire ecosystem can be present in the embedded data
   * while contributing almost nothing to the visible table -- 26 Flare rows were embedded and
   * only one reached the table. Filtering rows by data-chain makes that coverage reachable
   * WITHOUT lowering either gate: the screen stays as strict as it was, and the reader chooses
   * to look at a chain rather than the gates being relaxed for them. */
  /* Chain tabs. `chain:<slug>` selects rows; `chain:other` selects every chain too small to
   * have earned its own tab. The set of "small" chains is computed at BUILD time and embedded
   * as data-other="1" on those rows, so the JS does not need the list. */
  function applyChainFilter(chain) {
    Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
      var body = t.tBodies && t.tBodies[0];
      if (!body) return;
      var rows = Array.prototype.slice.call(body.rows);
      var tagged = rows.filter(function (r) { return r.getAttribute("data-chain"); });
      if (!tagged.length) return;
      // RECORD the dimension, then let applyVisibility evaluate it together with the text filter.
      // Writing styles from here is what let the two filters clobber each other.
      VIS.chain = chain || null;
      var box = t.previousElementSibling;
      var q = (box && box.tagName === "INPUT" && box.className.indexOf("tfilter") !== -1)
              ? (box.value || "").trim().toLowerCase() : "";
      applyVisibility(t, findHeader(t), q);
      // the window height belongs to the FILTERED set, not the whole table
      try { applyWindow(t); } catch (e) {}
    });
  }

  /* Jump strip: scroll to a section, revealing it first.
   *
   * AN ANCHOR INTO A HIDDEN CONTAINER FAILS SILENTLY. The view tabs hide whole sections with
   * display:none, and a browser cannot scroll to an element that is not rendered -- no error, no
   * movement, nothing. So a jump first finds the section owning the target, makes it visible the
   * same way the tabs do, then scrolls. Revealing first also keeps the topbar's active-tab state
   * honest, because it routes through the same code path rather than a second implementation.
   */
  function sectionOwner(el) {
    var p = el;
    while (p && p !== document.body) {
      if (p.getAttribute && p.getAttribute("data-section")) return p;
      p = p.parentElement;
    }
    return null;
  }

  /* Honour the hash on load and on change.
   *
   * A jump sets location.hash so the link is shareable, but nothing ever READ it. A recipient
   * opening #sec-lending got the right scroll position (in the default view every section is
   * rendered, so the browser's native anchor jump still worked) inside the WRONG VIEW -- the
   * sender's active tab was not reproduced. Writing a link you cannot read is not a shareable link.
   *
   * Deliberately NOT fixed with history.pushState. replaceState overwrites the current entry, which
   * looks like a flaw, but it is the safer choice here: pushState would add a history entry per jump,
   * so a reader clicking four jump links then pressing Back would walk backwards through anchors
   * instead of leaving the page -- arguably worse for a document people arrive at and read. What was
   * actually missing was the READ side, which is this.
   */
  function applyHash() {
    var id = (typeof location !== "undefined" && location.hash || "").replace(/^#/, "");
    if (!id) return false;
    var target = document.getElementById(id);
    if (!target) return false;
    // reveal the section that owns it, exactly as a click on the jump link would
    var sec = sectionOwner(target);
    if (sec) {
      Array.prototype.forEach.call(document.querySelectorAll("[data-section]"), function (o) {
        o.style.display = (o === sec) ? "" : "none";
      });
      var name = sec.getAttribute("data-section");
      Array.prototype.forEach.call(document.querySelectorAll("[data-tab]"), function (t) {
        var isMatch = t.getAttribute("data-tab") === name;
        t.classList.toggle("active", isMatch);
        t.setAttribute("aria-selected", isMatch ? "true" : "false");
      });
    }
    if (typeof target.scrollIntoView === "function") {
      try { target.scrollIntoView({ block: "start" }); } catch (e) {}
    }
    return true;
  }

  function wireJumps() {
    var links = document.querySelectorAll("[data-jump]");
    Array.prototype.forEach.call(links, function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var id = a.getAttribute("data-jump");
        var target = document.getElementById(id);
        if (!target) return;
        // reveal the section that owns this target, if one is hiding it
        var sec = sectionOwner(target);
        if (sec && sec.style.display === "none") {
          Array.prototype.forEach.call(document.querySelectorAll("[data-section]"), function (o) {
            o.style.display = (o === sec) ? "" : "none";
          });
          // keep the tab strip in step so it does not claim a section that is no longer shown
          var name = sec.getAttribute("data-section");
          Array.prototype.forEach.call(document.querySelectorAll("[data-tab]"), function (t) {
            var isMatch = t.getAttribute("data-tab") === name;
            t.classList.toggle("active", isMatch);
            t.setAttribute("aria-selected", isMatch ? "true" : "false");
          });
        }
        // Scroll AFTER revealing: an element that was display:none has no position until shown.
        // Guarded by typeof, not try/catch: jsdom has no layout engine and therefore no
        // scrollIntoView, and a throw here would skip the hash and focus lines below silently.
        if (typeof target.scrollIntoView === "function") {
          try { target.scrollIntoView({ block: "start" }); }
          catch (err) { try { target.scrollIntoView(); } catch (err2) {} }
        }
        // update the URL LAST, so the hashchange listener sees the section already revealed and
        // simply re-scrolls rather than duplicating the reveal
        try { if (history && history.replaceState) history.replaceState(null, "", "#" + id); } catch (e1) {}
        // a jump moves the viewport, so move the caret too or a keyboard user is left behind
        if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
        try { target.focus({ preventScroll: true }); } catch (e2) { try { target.focus(); } catch (e3) {} }
      });
    });
  }

  function wireTabs() {
    var tabs = document.querySelectorAll("[data-tab]");
    if (!tabs.length) return;
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener("click", function () {
        var want = tab.getAttribute("data-tab");
        Array.prototype.forEach.call(tabs, function (o) {
          o.classList.toggle("active", o === tab);
          o.setAttribute("aria-selected", o === tab ? "true" : "false");
        });
        // chain tabs filter rows; view tabs switch sections
        var isChain = want.indexOf("chain:") === 0;
        var chainSlug = isChain ? want.slice(6) : null;
        // A CHAIN TAB FILTERS THE POOL TABLE, which lives in `watch`, NOT in `pools`. MEASURED:
        // the 457-row chain-tagged table is inside data-section="watch"; the `pools` marker holds
        // only the 117-row AMM slice, which carries no chain tags. So a chain tab must show the
        // section that CONTAINS THE FILTERED TABLE, or it shows the filtering while showing the
        // wrong thing. The section is found from the table, not assumed from a name.
        var chainHost = null;
        if (isChain) {
          var tagged = document.querySelector("tr[data-chain]");
          if (tagged) {
            var p2 = tagged;
            while (p2 && p2 !== document.body) {
              if (p2.getAttribute && p2.getAttribute("data-section")) { chainHost = p2.getAttribute("data-section"); break; }
              p2 = p2.parentElement;
            }
          }
        }

        // NESTED SECTIONS: hide a section ONLY if no other visible section lives inside it.
        // MEASURED nesting: pools sits INSIDE watch, and lending sits inside watch. The chain
        // branch used to set watch="none" while keeping pools="" -- hiding the PARENT, which blanks
        // the child with it. The page went completely blank on every chain tab (Base, Ethereum,
        // Arbitrum, all 17 of them), because the one section it kept was inside the one it hid.
        //
        // So compute the desired visibility from the TAB, then walk the tree and show any section
        // that either IS wanted or CONTAINS a wanted section.
        var wantOne = {};
        Array.prototype.forEach.call(document.querySelectorAll("[data-section]"), function (sec) {
          var k = sec.getAttribute("data-section");
          wantOne[k] = isChain ? (k === chainHost) : (k === want);
        });
        Array.prototype.forEach.call(document.querySelectorAll("[data-section]"), function (sec) {
          var k = sec.getAttribute("data-section");
          // an ancestor of a wanted section must stay visible, or the wanted section is invisible
          var keep = wantOne[k];
          if (!keep) {
            var sub = sec.querySelectorAll("[data-section]");
            for (var i = 0; i < sub.length; i++) {
              if (wantOne[sub[i].getAttribute("data-section")]) { keep = true; break; }
            }
          }
          // and a section nested inside a HIDDEN ancestor is invisible whatever it says
          var anc = sec.parentElement, hiddenAbove = false;
          while (anc && anc !== document.body) {
            if (anc.getAttribute && anc.getAttribute("data-section") && !wantOne[anc.getAttribute("data-section")]) {
              // only counts if that ancestor has no wanted descendant other than through us
              var sib = anc.querySelectorAll("[data-section]");
              var anyWanted = false;
              for (var j = 0; j < sib.length; j++) { if (wantOne[sib[j].getAttribute("data-section")]) { anyWanted = true; break; } }
              if (!anyWanted) { hiddenAbove = true; break; }
            }
            anc = anc.parentElement;
          }
          sec.style.display = (keep && !hiddenAbove) ? "" : "none";
        });
        try { applyChainFilter(chainSlug); } catch (e) {}
        // HIDE THE OTHER TABLES, at TABLE level. Section granularity is too coarse here: MEASURED,
        // the chain-tagged table lives inside `watch`, and `watch` also contains the transitions
        // log, the lending tables and the pre-mortem. Showing `watch` to reveal the filtered table
        // therefore shows all of them -- the right filter in the middle of the wrong page. The
        // chain dimension is about POOLS, so it is applied to tables directly.
        try {
          Array.prototype.forEach.call(document.querySelectorAll("table"), function (tb) {
            var tagged = tb.querySelector("tr[data-chain]");
            if (isChain) {
              tb.style.display = tagged ? "" : "none";
            } else {
              tb.style.display = "";
            }
          });
          // and hide the section headings that belong to tables now hidden, so no orphan header sits
          // above nothing. Kept simple: only the pools h2 is relevant to a chain tab.
          var poolsH2 = document.getElementById("sec-pools");
          if (poolsH2) poolsH2.style.display = isChain ? "" : "";
        } catch (e) {}
        if (isChain) {
          try {
            var t0 = document.querySelector("table tr[data-chain]");
            var host = t0 ? t0.closest("table") : null;
            if (host && typeof host.scrollIntoView === "function") host.scrollIntoView({ block: "start" });
          } catch (e) {}
        }
        init();
      });
    });
  }

  function wireGlobalSearch() {
    var g = document.getElementById("global-search");
    if (!g) return;
    g.addEventListener("input", function () {
      var q = g.value.trim().toLowerCase();
      Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
        if (t.__aegis) t.__aegis.filter(q);
      });
    });
  }

  /* WINDOW HEIGHT. A 460-row table is a data dump however it is styled, so each table gets a
   * bounded scroll window (~20 rows visible) with sticky headers. The height is set on the
   * WRAPPER, not the table, so the header row stays visible while scrolling the body.
   *
   * 20 rows is a starting point, not a finding: it is roughly the point where a reader stops
   * scanning a table and starts scrolling past it. The control is a slider so it can be tuned
   * against a real screen rather than guessed at here. */
  var ROWS_VISIBLE = 20;

  function applyWindow(table) {
    var body = table.tBodies && table.tBodies[0];
    var host = table.parentNode;
    if (!body || !host) return;
    // measure a real row so the window matches the actual line height of this table
    var sample = null;
    for (var i = 0; i < body.rows.length; i++) {
      var r = body.rows[i];
      if (r.getAttribute("data-drawer") === "1") continue;
      if (r.style.display === "none") continue;
      sample = r; break;
    }
    if (!sample) return;
    var h = sample.getBoundingClientRect().height || 26;
    var head = table.tHead || (table.rows && table.rows.length ? table.rows[0] : null);
    var hh = head ? (head.getBoundingClientRect().height || 30) : 0;
    // subtract the header so "20 rows" means twenty DATA rows, not twenty minus the header
    host.style.maxHeight = Math.round(h * ROWS_VISIBLE + hh + 6) + "px";
    host.style.overflowY = "auto";
    host.classList.add("scrollwin");
  }

  function wireRowControl() {
    var all = document.querySelectorAll("table");
    if (!all.length) return;
    var btn = document.getElementById("rowctl");
    if (!btn) return;
    btn.addEventListener("input", function () {
      var v = parseInt(btn.value, 10);
      if (!v || v < 5) return;
      ROWS_VISIBLE = v;
      Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
        if (t.classList.contains("dense")) applyWindow(t);
      });
    });
  }

  function init() {
    try {
      Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
        try { decorate(t); } catch (e) {}
      });
    } catch (e) {}
  }

  /* Click-to-copy on truncated address cells. The .addr spans carry the FULL value in
     data-copy, so what the user copies is the real address, not the 0x34a2…999F they see.
     Delegated because rows re-render on sort/filter. Selection fallback for non-secure
     contexts; execCommand is deprecated but still the only way in an http (tailnet) page. */
  function wireCopy() {
    if (!document.addEventListener) return;
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      while (t && t !== document) {
        if (t.getAttribute && t.getAttribute("data-copy")) break;
        t = t.parentNode;
      }
      if (!t || t === document) return;
      var v = t.getAttribute("data-copy");
      if (!v) return;
      var done = function () {
        var old = t.getAttribute("title");
        t.setAttribute("title", "copied " + v.slice(0, 10) + "…");
        setTimeout(function () { if (old !== null) t.setAttribute("title", old); }, 1200);
      };
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(v).then(done, function () { fallback(); });
        } else { fallback(); }
      } catch (e) { try { fallback(); } catch (e2) {} }
      function fallback() {
        var ta = document.createElement("textarea");
        ta.value = v; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
  }

  /* CARD PILLS THAT ACT (dense-table rule: high-priority flags function as quick filters).
   * A card with data-cardfilter funnels its click through the SAME text filter the search box
   * uses, so there is one filtering mechanism, not two. Scoped to the card's own section, so
   * "at or past the lock" filters the runway table rather than every table on the page. A
   * second click clears. Cards without data-cardfilter stay passive stat boxes. */
  function wireCardFilters() {
    if (!document.addEventListener) return;
    Array.prototype.forEach.call(document.querySelectorAll("[data-cardfilter]"), function (c) {
      c.style.cursor = "pointer";
      c.setAttribute("role", "button");
      c.setAttribute("tabindex", "0");
      function act() {
        var tok = (c.getAttribute("data-cardfilter") || "").toLowerCase();
        var host = c.closest("[data-section]") || document;
        var on = c.getAttribute("data-cardon") === "1";
        Array.prototype.forEach.call(host.querySelectorAll("table"), function (t) {
          if (t.__aegis) t.__aegis.filter(on ? "" : tok);
        });
        if (on) c.removeAttribute("data-cardon");
        else c.setAttribute("data-cardon", "1");
        c.style.outline = on ? "" : "2px solid var(--acc)";
      }
      c.addEventListener("click", act);
      c.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); }
      });
    });
  }

  /* ------------------------------------------------------------------ verdict sidebar
   *
   * THE ONE THING A CURATOR SCANS FOR IS THE VERDICT, buried in a 460-row wall. The sidebar
   * is three quick-filter buttons (REAL / CAUTION / AVOID) + a clear, plus a CSV export per
   * table. Zero network: everything runs through the SAME applyVisibility executor as the
   * chain tabs, the search, the watchlist and the slider, so five dimensions compose and
   * none can clobber another.
   *
   * Rows opt in via data-verdict. The glance rows carry it from the build; rows without it
   * are left visible -- the sidebar narrows judged rows, it never blanks an unjudged table.
   */
  function reapplyAll() {
    Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
      var h = t.__aegis && t.__aegis.header;
      if (!h) return;
      var box = t.previousElementSibling;
      var q = (box && box.tagName === "INPUT" && box.className.indexOf("tfilter") !== -1)
              ? (box.value || "").trim().toLowerCase() : "";
      applyVisibility(t, h, q);
      try { applyWindow(t); } catch (e) {}
    });
  }

  function wireVerdictSidebar() {
    var host = document.getElementById("verdict-bar");
    if (!host) return;
    Array.prototype.forEach.call(host.querySelectorAll("[data-verdict-btn]"), function (b) {
      b.addEventListener("click", function () {
        var want = b.getAttribute("data-verdict-btn");
        var on = VIS.verdict === want;
        VIS.verdict = on ? null : want;
        Array.prototype.forEach.call(host.querySelectorAll("[data-verdict-btn]"), function (o) {
          var mine = o.getAttribute("data-verdict-btn") === want;
          o.classList.toggle("active", !on && mine);
          o.setAttribute("aria-pressed", (!on && mine) ? "true" : "false");
        });
        reapplyAll();
      });
    });
    var clear = host.querySelector("[data-verdict-clear]");
    if (clear) {
      clear.addEventListener("click", function () {
        VIS.verdict = null;
        Array.prototype.forEach.call(host.querySelectorAll("[data-verdict-btn]"), function (o) {
          o.classList.remove("active");
          o.setAttribute("aria-pressed", "false");
        });
        reapplyAll();
      });
    }
  }

  /* CSV EXPORT, per table. Runs entirely in the browser: no server round-trip, no network
   * request, so the zero-request contract holds. A Blob + object URL download keeps the
   * page flat-file while giving the reader the raw rows behind any filtered view.
   * Quote every field and double embedded quotes (RFC 4180); prepend a BOM so Excel
   * opens UTF-8 correctly. */
  function csvEscape(v) {
    var s = (v == null) ? "" : String(v);
    return '"' + s.replace(/"/g, '""') + '"';
  }

  function exportTableCSV(table, header) {
    var rows = dataRows(table, header);
    var out = [];
    var cells = [];
    Array.prototype.forEach.call(header.cells, function (th) {
      cells.push(csvEscape((th.textContent || "").trim()));
    });
    out.push(cells.join(","));
    rows.forEach(function (tr) {
      if (tr.style.display === "none") return;   // export what the reader SEES (filters honoured)
      var line = [];
      Array.prototype.forEach.call(tr.cells, function (td) {
        line.push(csvEscape((td.textContent || "").replace(/\s+/g, " ").trim()));
      });
      out.push(line.join(","));
    });
    var blob = new Blob(["\ufeff" + out.join("\r\n")], { type: "text/csv;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "aegis-" + (table.getAttribute("data-section")
                             || (table.closest && table.closest("[data-section]")
                                 ? (table.closest("[data-section]").getAttribute("data-section"))
                                 : "table")) + ".csv";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      document.body.removeChild(a);
      try { URL.revokeObjectURL(url); } catch (e) {}
    }, 250);
  }

  function wireCSVButtons() {
    Array.prototype.forEach.call(document.querySelectorAll("table[data-interactive='1']"), function (t) {
      if (t.previousElementSibling && t.previousElementSibling.getAttribute
          && t.previousElementSibling.getAttribute("data-csv") === "1") return;
      var h = t.__aegis && t.__aegis.header;
      if (!h) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "csvbtn";
      b.textContent = "CSV";
      b.title = "Export the rows currently visible in this table (filters honoured)";
      b.setAttribute("aria-label", "export this table as CSV");
      b.setAttribute("data-csv", "1");
      b.addEventListener("click", function (e) { e.stopPropagation(); exportTableCSV(t, h); });
      /* INSERTION ORDER IS A CONTRACT: every other layer locates the filter box as
       * table.previousElementSibling (the pin handler, the drawer toggle, the time
       * slider, the chain filter, reapplyAll below). Inserting this button directly
       * before the TABLE broke that adjacency, and the guarded reads silently fell
       * back to "" -- the filter text was dropped on every re-apply. So the button
       * goes BEFORE the filter box, keeping [CSV][filter][table]. */
      var fbox = (t.__aegis && t.__aegis.box) || null;
      if (fbox && fbox.parentNode) fbox.parentNode.insertBefore(b, fbox);
      else if (t.parentNode) t.parentNode.insertBefore(b, t);
    });
  }

  function refreshWatchCount() {
    var c = document.getElementById("watch-count");
    if (!c) return;
    var list = watchStore();
    c.textContent = list.length ? (list.length + " pinned") : "";
  }

  function wireTimeSlider() {
    var el = document.getElementById("timectl");
    if (!el) return;
    var label = document.getElementById("tmin");
    function fmt(v) {
      var d = new Date(v * 1000);
      return d.toISOString().slice(0, 16).replace("T", " ");
    }
    function apply() {
      var v = parseInt(el.value, 10);
      VIS.time = v;                    // a STATE dimension, not a direct style write
      if (label) label.textContent = fmt(v);
      // route through the single visibility executor, exactly like chain/filter/watch, so the
      // three dimensions cannot clobber each other's display writes.
      Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
        var h = t.__aegis && t.__aegis.header;
        if (!h) return;
        var box = t.previousElementSibling;
        var q = (box && box.tagName === "INPUT" && box.className.indexOf("tfilter") !== -1)
                ? (box.value || "").trim().toLowerCase() : "";
        applyVisibility(t, h, q);
        try { applyWindow(t); } catch (e) {}
      });
    }
    el.addEventListener("input", apply);
    apply();
  }

  function wireWatchToggle() {
    var b = document.getElementById("watch-toggle");
    if (!b) return;
    b.addEventListener("click", function () {
      VIS.watch = !VIS.watch;
      b.classList.toggle("active", VIS.watch);
      b.setAttribute("aria-pressed", VIS.watch ? "true" : "false");
      Array.prototype.forEach.call(document.querySelectorAll("table"), function (t) {
        var h = t.__aegis && t.__aegis.header;
        if (!h) return;
        var box = t.previousElementSibling;
        var q = (box && box.tagName === "INPUT" && box.className.indexOf("tfilter") !== -1)
                ? (box.value || "").trim().toLowerCase() : "";
        applyVisibility(t, h, q);
        try { applyWindow(t); } catch (e) {}
      });
    });
  }

  function boot() {
    init();
    try { wireTabs(); } catch (e) {}
    try { wireGlobalSearch(); } catch (e) {}
    try { wireWatchToggle(); } catch (e) {}
    try { refreshWatchCount(); } catch (e) {}
    try { wireTimeSlider(); } catch (e) {}
    // Apply the DEFAULT view on load: Summary only. Each table is its own section now, so a
    // fresh page must not dump every section (that was the "Everything" tab, now removed). The
    // chain rows are filtered by applyChainFilter, and a deep link (location.hash) overrides this
    // default in applyHash() below.
    if (!(typeof location !== "undefined" && location.hash)) {
      try {
        Array.prototype.forEach.call(document.querySelectorAll("[data-section]"), function (o) {
          o.style.display = o.getAttribute("data-section") === "summary" ? "" : "none";
        });
      } catch (e) {}
    }
    try { applyChainFilter(null); } catch (e) {}
    try { wireRowControl(); } catch (e) {}
    try { wireJumps(); } catch (e) {}
    try { wireCopy(); } catch (e) {}
    try { wireCardFilters(); } catch (e) {}
    try { wireVerdictSidebar(); } catch (e) {}
    try { wireCSVButtons(); } catch (e) {}
    try { applyHash(); } catch (e) {}
    try { if (typeof addEventListener === "function") addEventListener("hashchange", function () { try { applyHash(); } catch (e) {} }); } catch (e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  try { window.__aegisInit = boot; } catch (e) {}
})();

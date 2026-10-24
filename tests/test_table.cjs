/* test_table.js - does the table controller ACTUALLY modify the DOM?
 *
 * This exists because the previous verification was wrong. I had confirmed the script was
 * present, syntactically valid, and made no network calls -- and concluded it worked. It did
 * not. Only 1 of 8 tables had a <thead>, and the code required one, so seven tables were
 * marked handled and abandoned. "The script is in the page" is not the same claim as "the
 * script changed the page", and only the second one is testable.
 *
 * So this loads the REAL generated report.html in jsdom, runs the REAL inline script, and
 * asserts the DOM was mutated. Source-inspection tests cannot catch this class of bug.
 *
 * Run:  node tests/test_table.cjs         (from the project root)
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const ROOT = path.dirname(__dirname);
const PAGE = path.join(ROOT, "report.html");

let FAILS = [];
function check(name, cond, detail) {
  console.log("  " + name.padEnd(62) + (cond ? "PASS" : "FAIL"));
  if (!cond && detail) console.log("      " + detail);
  if (!cond) FAILS.push(name);
}

if (!fs.existsSync(PAGE)) {
  console.log("report.html not found; run: python3 screener/build_v2.py");
  process.exit(1);
}

const html = fs.readFileSync(PAGE, "utf8");

console.log("=== loading the real report.html in jsdom ===");
const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true });
const doc = dom.window.document;

setTimeout(() => {
  const tables = Array.from(doc.querySelectorAll("table"));
  console.log("  tables in document: " + tables.length);
  console.log("");

  console.log("=== 1. every table got a filter input above it ===");
  const filters = Array.from(doc.querySelectorAll("input.tfilter"));
  check("at least one table exists", tables.length > 0);
  check("filter inputs injected: " + filters.length + " of " + tables.length,
        filters.length === tables.length,
        "the old code injected 0 because table.tHead was null for theadless tables");

  console.log("\n=== 2. every header cell became a sortable button ===");
  let headed = 0, decorated = 0, arrows = 0;
  tables.forEach(function (t) {
    const headerRow = (t.tHead && t.tHead.rows.length)
      ? t.tHead.rows[t.tHead.rows.length - 1]
      : (t.rows && t.rows.length ? t.rows[0] : null);
    if (!headerRow) return;
    headed++;
    if (t.getAttribute("data-interactive") === "1") decorated++;
    arrows += headerRow.querySelectorAll(".sort-arrow").length;
  });
  check("tables with a discoverable header row: " + headed, headed > 0);
  check("tables marked data-interactive: " + decorated + " of " + headed,
        decorated === headed);
  check("sort arrows created: " + arrows, arrows > 0);

  console.log("\n=== 3. no table is STRANDED (the real consequence of ordering) ===");
  // NO SOURCE GREPPING. This compared indexOf() offsets in table.js, which is a statement about
  // the TEXT of the file: a comment containing the marker string would satisfy it, and renaming
  // a local variable would break it. `decorate()` is inside an IIFE so it cannot be called
  // directly -- so assert the OBSERVABLE CONSEQUENCE instead, on the real page.
  //
  // The bug this guards: `decorate()` marked a table data-interactive BEFORE checking it had a
  // sortable header. A table with no header got marked, then bailed -- marked-but-undecorated,
  // and a later pass would skip it because it looked handled. That stranded 7 tables.
  //
  // The consequence is visible from outside: if a table can be decorated, it MUST be marked; if
  // it cannot, it must NOT be. A table with several rows and no marker is a stranded table.
  {
    const allTables = Array.from(doc.querySelectorAll("table"));
    const marked = allTables.filter(function (t) { return t.getAttribute("data-interactive") === "1"; });
    const unmarkedMultiRow = allTables.filter(function (t) {
      return t.getAttribute("data-interactive") !== "1" && t.querySelectorAll("tr").length > 1;
    });
    check("every multi-row table on the page is marked as decorated (" + marked.length + "/" + allTables.length + ")",
          unmarkedMultiRow.length === 0,
          "unmarked multi-row tables = stranded: " + unmarkedMultiRow.length);
    // and the inverse, which is the actual regression: a table that CANNOT be decorated must not
    // claim it was. Inject one and confirm the page leaves it alone.
    const dead = doc.createElement("table");
    dead.innerHTML = "<tr><td>a single cell, nothing to sort by</td></tr>";
    doc.body.appendChild(dead);
    const before = dead.getAttribute("data-interactive");
    // re-run the page's own decorator over the whole document, as a later pass would
    try { if (typeof dom.window.init === "function") dom.window.init(); } catch (e) {}
    check("an undecoratable table is not marked as handled",
          dead.getAttribute("data-interactive") !== "1",
          "marking before the bail is what stranded 7 tables (was " + before + ")");
    dead.remove();
  }

  console.log("\n=== 3c. EVERY table sorts correctly, not just one ===");
  // The sort assertions below ran against ONE table, chosen by `tables.find(...)`. The other seven
  // were never sorted in any test, even though all eight are interactive and every one has a
  // column with distinct keys. A comparator regression affecting a table whose values are shaped
  // differently (a percentage column, a currency column, a text column) would have gone unseen.
  //
  // Each table is exercised on ITS OWN best column: the sortable column with the most distinct
  // sort keys. A table contributes no assertions only when it has no such column, and that case
  // is REPORTED rather than skipped silently.
  {
    const NUMRE2 = /-?\d[\d,]*\.?\d*/;
    const mult2 = function (txt) {
      let m = 1;
      if (/[kK]\b|[kK]$/.test(txt)) m = 1e3;
      if (/[mM]\b|[mM]$/.test(txt)) m = 1e6;
      if (/[bB]\b|[bB]$/.test(txt)) m = 1e9;
      const g = txt.match(NUMRE2);
      if (!g) return null;
      const v = parseFloat(g[0].replace(/,/g, ""));
      return isNaN(v) ? null : v * m;
    };
    let sorted = 0, unexercised = [];
    tables.forEach(function (tb, ti) {
      const hr = (tb.tHead && tb.tHead.rows.length) ? tb.tHead.rows[tb.tHead.rows.length - 1] : tb.rows[0];
      if (!hr) { unexercised.push(ti + ":no-header"); return; }
      const bd = tb.tBodies[0] || tb;
      // EXCLUDE THE HEADER BY IDENTITY, ALWAYS. The first version did this only when `!tb.tHead`,
      // which is wrong: the header is the LAST row of <thead> when there is one, and for a
      // THEADLESS table it is simply the first BODY row. Table[2] has no <thead>, so the header
      // row leaked into the data set and was sorted as if "collateral | supplied | unrealised"
      // were values -- producing a spurious ordering failure that was MY bug, not the page's.
      // Production's dataRows() filters `tr === header.row` unconditionally; mirror that.
      const rowsNow = function () {
        return Array.from(bd.rows || []).filter(function (r) {
          if (r === hr) return false;
          return r.getAttribute("data-drawer") !== "1";
        });
      };
      const base = rowsNow();
      // MIRROR cellText(): the page prefers a cell's `data-sort` ATTRIBUTE over its text. Reading
      // textContent alone produced a false "unsorted" for table[2], whose collateral cell renders
      // "RUSR" but carries data-sort="USR" -- so the page sorted on USR while the test compared
      // RUSR. Measured: data-sort="USR", textContent="RUSR". A cell can display a badge prefix the
      // sort must ignore, and the attribute is how that is expressed.
      const txt = function (r, ci) {
        const c = r.cells[ci];
        if (!c) return "";
        return (c.getAttribute("data-sort") || c.textContent || "").trim();
      };

      // choose this table's best sortable column by DISTINCT SORT KEY
      let ci = -1, best = 1;
      Array.from(hr.cells).forEach(function (th, i) {
        if (!th.querySelector || !th.querySelector(".sort-arrow")) return;
        const ks = new Set(base.map(function (r) {
          const t2 = txt(r, i);
          const n = mult2(t2);
          return n === null ? t2.toLowerCase() : String(n);
        }));
        if (ks.size > best) { best = ks.size; ci = i; }
      });
      if (ci < 0) { unexercised.push(ti + ":no-distinct-column"); return; }

      const numeric = base.every(function (r) { return mult2(txt(r, ci)) !== null || txt(r, ci) === ""; });
      const key = function (v) { const n = mult2(v); return (numeric && n !== null) ? n : v.toLowerCase(); };
      const before = base.map(function (r) { return txt(r, ci); });

      hr.cells[ci].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      const asc = rowsNow().map(function (r) { return txt(r, ci); });

      // P1: non-decreasing on this table's own key space
      let ok = true;
      for (let i = 1; i < asc.length; i++) {
        const p = key(asc[i - 1]), c = key(asc[i]);
        if (p === "" || c === "") continue;
        if (typeof p === "number" && typeof c === "number") { if (p > c) ok = false; }
        else if (String(p).localeCompare(String(c)) > 0) ok = false;
      }
      // P4: multiset preserved
      const bag2 = function (a) { return a.slice().sort().join("\u0001"); };
      const same = bag2(before.map(key)) === bag2(asc.map(key));
      check("table[" + ti + "] col " + ci + " sorts non-decreasing (" + asc.length + " rows, " + best + " distinct)",
            ok && same, "ordered=" + ok + " multisetPreserved=" + same);
      sorted++;
    });
    check("tables exercised by the sort check: " + sorted + " of " + tables.length,
          sorted === tables.length,
          "unexercised: " + unexercised.join(", "));
  }

  console.log("\n=== 4. sorting produces the CORRECT order, not merely a different one ===");
  // PREVIOUSLY this asserted only that the order CHANGED. A table that shuffled rows at random
  // would have passed. Reimplement the documented comparator independently and compare against
  // what the page actually produces -- so a wrong sort now fails instead of looking like a sort.
  //
  // The spec, read off table.js: numeric when EVERY key parses as a number, otherwise lowercase
  // lexicographic; empty/null sorts last; TIES fall back to the original index (stable).
  const t = tables.find(function (x) { return x.querySelector(".sort-arrow"); });
  if (t) {
    const headerRow = (t.tHead && t.tHead.rows.length) ? t.tHead.rows[t.tHead.rows.length - 1] : t.rows[0];
    const body = t.tBodies[0] || t;
    const dataRows = function () {
      // identity-based header exclusion, mirroring table.js dataRows(). A !tHead conditional
      // leaks the header row for theadless tables (see section 3c for the measured failure).
      return Array.from(body.rows || []).filter(function (r) {
        if (r === headerRow) return false;
        return r.getAttribute("data-drawer") !== "1";
      });
    };
    const keyAt = function (r, i) {
      const c = r.cells[i];
      if (!c) return "";
      return (c.getAttribute("data-sort") || c.textContent || "").trim();
    };

    // PICK A COLUMN WITH DISTINCT KEYS, not merely the first sortable one. The first sortable
    // column here is "when (UTC)", whose values are ISO timestamps. table.js's NUMRE
    // (/-?\d[\d,]*\.?\d*/) matches the "2026" prefix, so num() returns 2026 for EVERY row --
    // MEASURED: 1 distinct sort key across 126 rows. Sorting on that column is a no-op, so a test
    // that clicked it would assert nothing about ordering and would pass on an inverted
    // comparator. That is exactly what happened on the first run of this section.
    //
    // Choosing a column with genuinely distinct keys is what makes the assertions below able to
    // fail. The column choice is itself part of the test's validity.
    const sortableCols = Array.from(headerRow.cells)
      .map(function (th, i) { return th.querySelector && th.querySelector(".sort-arrow") ? i : -1; })
      .filter(function (i) { return i >= 0; });
    check("sortable columns exist (" + sortableCols.length + ")", sortableCols.length > 0);
    const bodyAll = t.tBodies[0] || t;
    // EXCLUDE DRAWERS AND THE HEADER, the same two filters table.js's dataRows() applies. This
    // probe omitted the drawer filter, so it sampled 64 expandable-detail rows that carry ONE cell
    // each. Their cell[11] was undefined, so the column-distinctness measurement and the chosen
    // column were computed over the wrong population -- which is why section 4 disagreed with
    // section 3c on the same table. MEASURED: 129 body rows of which 64 are data-drawer rows.
    let probeRows = Array.from(bodyAll.rows || []).filter(function (r) {
      if (r === headerRow) return false;
      return r.getAttribute("data-drawer") !== "1";
    });
    // Count distinct SORT KEYS, not distinct raw text. Using the text is what picked the date
    // column: 126 different timestamps look like 126 distinct values, but table.js's NUMRE matches
    // only the "2026" prefix, so the KEY is identical for every row. A column is only useful for
    // testing order if the keys it produces differ.
    const NUMRE_ = /-?\d[\d,]*\.?\d*/;
    const NUM_MULT = function (txt) {
      let mult = 1;
      if (/[kK]\b|[kK]$/.test(txt)) mult = 1e3;
      if (/[mM]\b|[mM]$/.test(txt)) mult = 1e6;
      if (/[bB]\b|[bB]$/.test(txt)) mult = 1e9;
      const m = txt.match(NUMRE_);
      if (!m) return null;
      const v = parseFloat(m[0].replace(/,/g, ""));
      return isNaN(v) ? null : v * mult;
    };
    const sortKey = function (r, i) {
      const c = r.cells[i];
      if (!c) return null;
      // data-sort FIRST, exactly as table.js's cellText() does. Reading textContent only made
      // section 4 disagree with section 3c on the same table, which is how the mismatch surfaced.
      const txt = (c.getAttribute("data-sort") || c.textContent || "").trim();
      if (!txt) return null;
      const n = NUM_MULT(txt);
      return n === null ? txt.toLowerCase() : n;   // mirrors table.js: numeric if it parses
    };
    const distinct = function (i) {
      const s = new Set(probeRows.map(function (r) { return String(sortKey(r, i)); }));
      return s.size;
    };
    // prefer the column with the MOST distinct values; tie-break on the lowest index for determinism
    let ci = -1, best = 0;
    sortableCols.forEach(function (i) {
      const d = distinct(i);
      if (d > best) { best = d; ci = i; }
    });
    check("a column with distinct keys was chosen (col " + ci + ", " + best + " distinct)",
          ci >= 0 && best > 1,
          "sorting on a constant key cannot demonstrate anything");
    if (ci >= 0) {
      // PROPERTY-BASED, NOT MIRROR-BASED. The first version of this reimplemented the comparator
      // and compared -- which shares any edge-case bug the production code has (identical
      // coercion, identical empty handling), so both agree and the test passes on a broken spec.
      // These properties encode NO algorithm: a shared misconception has nowhere to hide.
      const rowsBefore = dataRows();
      const rawKeys = rowsBefore.map(function (r) { return keyAt(r, ci); });
      // NUMERIC CLASSIFICATION MUST MATCH table.js, not my own idea of numeric. The page treats a
      // cell as numeric when its NUMRE match parses -- which is true of "$11.1M" (matches "11.1",
      // scaled by the M suffix) AND of "2026-10-08T..." (matches "2026"). Requiring the WHOLE
      // string to parse, as the first version did, classified the TVL column as LEXICAL and
      // asserted the wrong ordering. Use the same helper the page uses.
      const numeric = rawKeys.length > 0 && rawKeys.every(function (v) {
        return v !== "" && NUM_MULT(v) !== null;
      });
      const countBefore = rowsBefore.length;
      const nk = function (v) {
        return numeric ? NUM_MULT(v) : v.toLowerCase();
      };

      // DRIVE TO A KNOWN DIRECTION, do not assume "the first click is ascending". Section 3c
      // already clicked every header, and this DOM is shared, so a naive single click here lands
      // on DESCENDING and every ordering assertion below inverts. That is not a flaky test -- it
      // is a test reading state a previous section left behind. Click until the page reports the
      // direction we want, with a bound so a header that never sets the attribute fails loudly
      // instead of looping.
      var clicks = 0;
      while (headerRow.cells[ci].getAttribute("data-sort-dir") !== "asc" && clicks < 3) {
        headerRow.cells[ci].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        clicks++;
      }
      check("the sort direction can be driven to ascending", clicks < 3,
            "clicked " + clicks + " times; dir=" + headerRow.cells[ci].getAttribute("data-sort-dir"));
      const ascKeys = dataRows().map(function (r) { return keyAt(r, ci); });

      // P1 NON-DECREASING -- the DEFINING property of an ascending sort. No comparator needed.
      var nonDecreasing = true;
      for (var i = 1; i < ascKeys.length; i++) {
        var p = nk(ascKeys[i - 1]), c = nk(ascKeys[i]);
        var pn = (typeof p === "number" && Number.isNaN(p)) || p === "";
        var cn = (typeof c === "number" && Number.isNaN(c)) || c === "";
        if (pn || cn) continue;               // empties sort last; do not over-constrain
        if (typeof p === "number" && typeof c === "number") { if (p > c) nonDecreasing = false; }
        else if (String(p).localeCompare(String(c)) > 0) nonDecreasing = false;
      }
      check("P1 ascending order is non-decreasing (" + (numeric ? "numeric" : "lexical") + ")",
            nonDecreasing, "got " + JSON.stringify(nk(ascKeys[0])) + " .. " + JSON.stringify(nk(ascKeys[ascKeys.length - 1])));

      // P2 STABILITY -- equal keys keep their PRE-SORT relative order. This is the property the
      // tie-break exists to provide, and it is the exact thing a naive re-sort would break.
      var pos = {};
      rawKeys.forEach(function (k, i) { (pos[k] = pos[k] || []).push(i); });
      var seen = {}, stable = true;
      dataRows().forEach(function (r) {
        var k = keyAt(r, ci);
        seen[k] = seen[k] || 0;
        if (pos[k][seen[k]] === undefined) stable = false;
        seen[k]++;
      });
      check("P2 ties keep their original relative order (stable)", stable,
            "keys: " + new Set(rawKeys).size + " distinct of " + rawKeys.length);

      // P4 NO LOSS -- the multiset of keys is unchanged. Catches a sort that drops or duplicates rows.
      var bag = function (a) { return a.slice().sort().join("\u0001"); };
      check("P4 sorting loses and duplicates nothing", bag(rawKeys) === bag(ascKeys));

      // P5 row count
      check("P5 row count is unchanged by sorting", dataRows().length === countBefore,
            countBefore + " -> " + dataRows().length);

      // P3 IDEMPOTENCE -- asc, desc, asc returns to the same ascending order.
      var ascOnce = ascKeys.slice();
      // two more clicks from a known "asc" returns to "asc" -- the round trip P3 asserts
      headerRow.cells[ci].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      headerRow.cells[ci].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      check("P3 asc -> desc -> asc returns to the same order",
            JSON.stringify(dataRows().map(function (r) { return keyAt(r, ci); })) === JSON.stringify(ascOnce));

      // DESCENDING: keys must be non-increasing. (NOT "the reverse of ascending" -- ties keep
      // original order in both directions, so with duplicates the reverse is a different list.)
      headerRow.cells[ci].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      const descKeys = dataRows().map(function (r) { return keyAt(r, ci); });
      var nonIncreasing = true;
      for (var j = 1; j < descKeys.length; j++) {
        var dp = nk(descKeys[j - 1]), dc = nk(descKeys[j]);
        var dpn = (typeof dp === "number" && Number.isNaN(dp)) || dp === "";
        var dcn = (typeof dc === "number" && Number.isNaN(dc)) || dc === "";
        if (dpn || dcn) continue;
        if (typeof dp === "number" && typeof dc === "number") { if (dp < dc) nonIncreasing = false; }
        else if (String(dp).localeCompare(String(dc)) < 0) nonIncreasing = false;
      }
      check("descending order is non-increasing", nonIncreasing);

      // duplicate keys must form ONE CONTIGUOUS RUN
      check("duplicate keys form one contiguous run, not scattered",
            (function () {
              const keys = descKeys.map(nk);
              const closed = new Set();
              let prev = null;
              for (let i = 0; i < keys.length; i++) {
                const k = keys[i];
                if (k !== prev) {
                  if (closed.has(k)) return false;
                  if (prev !== null) closed.add(prev);
                  prev = k;
                }
              }
              return true;
            })());

      // KEYBOARD parity: the header is role=button and must sort on Enter too, or the table is
      // unusable without a mouse. Sorting by keyboard is real behaviour, not decoration.
      const th = headerRow.cells[ci];
      const dirBefore = th.getAttribute("data-sort-dir");
      th.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      // ARIA CONTRACT. Not role="button": a <th> is implicitly a columnheader, and aria-sort is
      // only supported on columnheader -- role=button would make aria-sort IGNORED, shipping
      // markup that looks accessible and announces nothing. Assert the role is NOT overridden and
      // that aria-sort tracks data-sort-dir rather than drifting from it.
      check("the header keeps its columnheader role (role=button would void aria-sort)",
            !th.getAttribute("role"), "role=" + th.getAttribute("role"));
      check("the header is keyboard-focusable", th.getAttribute("tabindex") === "0");
      {
        const want = { asc: "ascending", desc: "descending" };
        const dirNow = th.getAttribute("data-sort-dir");
        check("aria-sort agrees with data-sort-dir (" + dirNow + ")",
              th.getAttribute("aria-sort") === (want[dirNow] || "none"),
              "aria-sort=" + th.getAttribute("aria-sort") + " dir=" + dirNow);
        // at most ONE column may report a direction
        const directed = Array.from(headerRow.cells).filter(function (c) {
          const a = c.getAttribute("aria-sort");
          return a === "ascending" || a === "descending";
        });
        check("only one column reports a sort direction (" + directed.length + ")",
              directed.length === 1, "a grid may not have two sorted columns");
        // every OTHER sortable header must say "none", not carry a stale direction
        const stale = Array.from(headerRow.cells).filter(function (c) {
          return c.querySelector && c.querySelector(".sort-arrow")
                 && !c.getAttribute("aria-sort");
        });
        check("every sortable header declares an aria-sort (" + stale.length + " missing)",
              stale.length === 0);
      }
      check("Enter on the header sorts it (keyboard parity)",
            th.getAttribute("data-sort-dir") !== dirBefore,
            "dir stayed " + dirBefore);
      // Space must ALSO sort. The previous line here was `check("Space ...", true)`, which can
      // never fail -- a fake assertion of exactly the kind this suite exists to eliminate.
      const dirBeforeSpace = th.getAttribute("data-sort-dir");
      th.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: " ", bubbles: true }));
      check("Space on the header sorts it too",
            th.getAttribute("data-sort-dir") !== dirBeforeSpace,
            "dir stayed " + dirBeforeSpace);
    }
  } else {
    check("a sortable table was found", false);
  }

  console.log("\n=== 4b. filter and sort COMPOSE: filtering preserves the sorted order ===");
  // The filter and the sort were tested separately and never together, which is where integration
  // bugs live. Two properties matter and both are checked on EVERY table:
  //   (i)  a filtered view is a SUBSEQUENCE of the sorted view -- not merely "fewer rows", but the
  //        same rows in the same relative order;
  //   (ii) clearing the filter restores the exact sorted view, including rows the filter hid.
  // Note (i) is deliberately a subsequence check, not a re-sort: the clicked column here is
  // second-resolution timestamps with many TIES, so re-sorting the filtered subset would impose
  // an order among equal keys that the page never promised. Subsequence is the honest property.
  {
    const visibleRows = function (tb, hr) {
      const bd = tb.tBodies[0] || tb;
      return Array.from(bd.rows || []).filter(function (r) {
        if (r === hr) return false;
        if (r.getAttribute("data-drawer") === "1") return false;
        return r.style.display !== "none";
      });
    };
    const rowText = function (r) { return (r.textContent || "").replace(/\s+/g, " ").trim(); };
    let composed = 0, skipped = [];
    tables.forEach(function (tb, ti) {
      const flt = tb.previousElementSibling;
      if (!flt || flt.tagName !== "INPUT") { skipped.push(ti + ":no-filter"); return; }
      const hr = (tb.tHead && tb.tHead.rows.length) ? tb.tHead.rows[tb.tHead.rows.length - 1] : tb.rows[0];
      if (!hr || !hr.cells.length) { skipped.push(ti + ":no-header"); return; }

      // drive this table's first sortable header to a known direction
      let th = null;
      for (let i = 0; i < hr.cells.length; i++) {
        if (hr.cells[i].querySelector && hr.cells[i].querySelector(".sort-arrow")) { th = hr.cells[i]; break; }
      }
      if (!th) { skipped.push(ti + ":no-sortable"); return; }
      let n = 0;
      while (th.getAttribute("data-sort-dir") !== "asc" && n < 3) {
        th.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        n++;
      }

      const sorted = visibleRows(tb, hr).map(rowText);
      if (!sorted.length) { skipped.push(ti + ":empty"); return; }

      // filter on a token that exists, so some rows are hidden but not all
      const needle = sorted[0].trim().split(/\s+/)[0];
      flt.value = needle;
      flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      const filtered = visibleRows(tb, hr).map(rowText);

      // (i) subsequence
      let k = 0;
      for (let i = 0; i < sorted.length && k < filtered.length; i++) {
        if (sorted[i] === filtered[k]) k++;
      }
      const isSubsequence = (k === filtered.length);
      let hidSomething = filtered.length < sorted.length;
      // A needle matching EVERY row cannot test "filtering preserves order" -- it tests nothing.
      // All 40 liquidations in a burst share one date, so the first cell's first token is not
      // discriminating for that table; requiring hidSomething there failed the FIXTURE, not the
      // code (subsequence and restoredExactly were both true). Retry once with a rarer token
      // from the second cell before concluding the filter is broken.
      if (!hidSomething && sorted[0].trim().split(/\s+/).length > 1) {
        const rarer = sorted[0].trim().split(/\s+/).slice(1).join(" ").trim();
        if (rarer.length > 2) {
          flt.value = rarer;
          flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
          const f2 = visibleRows(tb, hr).map(rowText);
          if (f2.length && f2.length < sorted.length) {
            filtered.length = 0; Array.prototype.push.apply(filtered, f2);
            hidSomething = true;
          }
        }
      }

      flt.value = "";
      flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      const restored = visibleRows(tb, hr).map(rowText);
      const restoredExactly = JSON.stringify(restored) === JSON.stringify(sorted);

      check("table[" + ti + "] filtered view keeps the sorted order (" + filtered.length + "/" + sorted.length + ")",
            isSubsequence && hidSomething && restoredExactly,
            "subsequence=" + isSubsequence + " hidSomething=" + hidSomething + " restoredExactly=" + restoredExactly);
      composed++;
    });
    check("tables where filter x sort composition was verified: " + composed,
          composed > 0, "skipped: " + skipped.join(", "));
  }

  console.log("\n=== 4c. a drawer survives open -> filter -> clear ===");
  // THREE dimensions now decide a row's visibility: the chain tab, the text filter, and whether a
  // drawer is OPEN. They were all writing style.display directly and clobbering each other. The
  // last one found: applyVisibility forced every drawer row to display:none AND the drawer row's
  // own iteration then clobbered the decision its parent had just made. Measured symptom: clicking
  // a row set class="open" but the drawer never appeared.
  //
  // State is now class="open" and visibility is DERIVED from (parent visible && open). This asserts
  // the full lifecycle on EVERY table that has drawers.
  {
    let checked = 0, skipped = [];
    tables.forEach(function (tb, ti) {
      const flt = tb.previousElementSibling;
      const bd = tb.tBodies[0] || tb;
      const rows = Array.from(bd.rows || []);
      let pair = null;
      rows.forEach(function (r, i) {
        if (r.getAttribute("data-drawer") !== "1" || pair) return;
        const p = rows[i - 1];
        if (p && p.getAttribute("data-drawer") !== "1"
            && p.style.display !== "none"
            && p.getAttribute("data-extra-row") !== "1") pair = [p, r];
      });
      if (!pair) { skipped.push(ti + ":no-drawer"); return; }
      const parent = pair[0], dr = pair[1];
      const shown = function () { return dr.style.display !== "none"; };
      const openState = function () { return parent.classList.contains("open"); };

      const closed0 = !shown() && !openState();
      parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      const opened = shown() && openState();
      let filtered = true, restored = true;
      if (flt) {
        // a needle the parent cannot match, so the parent AND its drawer must hide
        flt.value = "zzzznotpresent";
        flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
        filtered = !shown();
        flt.value = "";
        flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
        restored = shown() && openState();
      }
      parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      const closedOnce = !shown() && !openState();

      // ACCESSIBILITY + SEARCHABILITY, asserted per table, not per component.
      // MEASURED BEFORE: 602 expandable rows, 0 with tabindex, 0 with aria-expanded -- a drawer was
      // pointer-only and its open state was unannounced, so its contents were unreachable
      // non-visually.
      const reachable = parent.getAttribute("tabindex") === "0";
      const announced0 = parent.getAttribute("aria-expanded") === "false";
      parent.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      const kbOpens = parent.getAttribute("aria-expanded") === "true" && shown();
      parent.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: " ", bubbles: true }));
      const kbCloses = parent.getAttribute("aria-expanded") === "false" && !shown();
      check("table[" + ti + "] drawer: keyboard-reachable and announced",
            reachable && announced0 && kbOpens && kbCloses,
            "tabindex=" + reachable + " ariaInitial=" + announced0
            + " enterOpens=" + kbOpens + " spaceCloses=" + kbCloses);

      // FOCUS IS NOT STRANDED IN A CLOSED DRAWER. MEASURED BEFORE: focus an anchor inside an open
      // drawer, close it, and focus stayed on the now-hidden anchor -- the next Tab continues from
      // inside a display:none subtree. The disclosure row that owns the drawer must receive focus.
      {
        parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));   // open
        const inner = dr.querySelector("a, button, input");
        if (inner) {
          inner.focus();
          const focusedInside = doc.activeElement === inner;
          parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); // close
          const rescued = doc.activeElement === parent;
          const strandedInHidden = doc.activeElement === inner;
          check("table[" + ti + "] focus escapes a closing drawer (" + (focusedInside ? "was inside" : "n/a") + ")",
                !focusedInside || (rescued && !strandedInHidden),
                "focus left on a hidden node: " + strandedInHidden);
        }
        // and focus that was NOT inside must not be yanked
        const outside = doc.querySelector("input.tfilter, #global-search");
        if (outside) {
          outside.focus();
          parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          check("table[" + ti + "] toggling does not steal focus from elsewhere",
                doc.activeElement === outside, "focus moved away from a field the user was in");
        }
      }
      if (parent.classList.contains("open")) parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

      // NO SEARCHABILITY ASSERTION HERE, DELIBERATELY. The caveat "a term present only in the
      // drawer would hide the row" was checked and is NOT a real gap: MEASURED across all 602
      // drawers, every .dv value is a copy of a cell already in the parent row -- 602 duplicate,
      // 0 add novel text. There is nothing in a drawer that is not already searchable, so there is
      // no behaviour to assert. Writing one anyway would have been a test that cannot fail for the
      // right reason, which is exactly what this suite exists to avoid.
      //
      // What IS asserted: the merge must not make every row match a header word. That was a real
      // regression I introduced (indexing the whole drawer, whose labels repeat the column names)
      // and it is covered by section 5 below.
      if (parent.classList.contains("open")) parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

      // STATE-SYNC INVARIANT under a filter that hides the parent while the drawer is open.
      // The three representations of "this disclosure is open" must never disagree:
      //   class "open"  <->  aria-expanded="true"  <->  drawer visible when the parent is visible
      // MEASURED on the current build: they agree at every step (opened / parent-hidden / cleared).
      // Asserted because the caveat is that an async re-render or a programmatic close could
      // desynchronise them -- and a disagreement is invisible without checking all three.
      if (flt) {
        parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));   // ensure open
        if (!parent.classList.contains("open")) parent.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        flt.value = "zzzznotpresent";
        flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
        const hiddenInSync = parent.classList.contains("open")
                             === (parent.getAttribute("aria-expanded") === "true")
                             && dr.style.display === "none";
        flt.value = "";
        flt.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
        const parentVisible = parent.style.display !== "none";
        const restoredInSync = parent.classList.contains("open")
                               === (parent.getAttribute("aria-expanded") === "true")
                               && (dr.style.display !== "none") === parentVisible;
        check("table[" + ti + "] class, aria-expanded and visibility never disagree",
              hiddenInSync && restoredInSync,
              "whileHidden=" + hiddenInSync + " afterClear=" + restoredInSync);
      }

      check("table[" + ti + "] drawer lifecycle: closed -> open -> hidden -> restored -> closed",
            closed0 && opened && filtered && restored && closedOnce,
            "closed=" + closed0 + " opened=" + opened + " hiddenByFilter=" + filtered
            + " restored=" + restored + " closedInOneClick=" + closedOnce);
      checked++;
    });
    check("tables whose drawer lifecycle was verified: " + checked, checked > 0,
          "skipped: " + skipped.join(", "));
  }

  console.log("\n=== 5. the filter actually hides non-matching rows ===");
  const f = doc.querySelector("input.tfilter");
  if (f) {
    const table = f.nextElementSibling;
    const body = table.tBodies[0] || table;
    // Identify the header row by IDENTITY, not by index. `if (!table.tHead) rows.slice(1)`
    // assumed the header is always the first body row and skipped it only when there was no
    // <thead>. With a REAL <thead> the header is not in tBodies at all, so slicing was wrong
    // in the other direction: the first DATA row got dropped and "restore all rows" then
    // compared 5 against 6. Same defect as the earlier table.rows/index bug.
    const hdrRow = (table.tHead && table.tHead.rows.length)
      ? table.tHead.rows[table.tHead.rows.length - 1] : null;
    let rows = Array.from(body.rows || []).filter(function (r) {
      if (hdrRow && r === hdrRow) return false;
      return r.getAttribute("data-drawer") !== "1";
    });
    if (rows.length) {
      const needle = (rows[0].textContent || "").trim().split(/\s+/)[0];
      f.value = needle;
      f.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      const visible = rows.filter(function (r) { return r.style.display !== "none"; }).length;
      check("filtering hides some rows (needle=" + JSON.stringify(needle) + ")", visible < rows.length,
            "no row was hidden");
      f.value = "";
      f.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      const restored = rows.filter(function (r) { return r.style.display !== "none"; }).length;
      check("clearing the filter restores all rows", restored === rows.length,
            restored + " of " + rows.length);
    } else {
      check("a filterable table has rows", false);
    }
  } else {
    check("a filter input was found", false);
  }

  console.log("\n=== 6. the page still makes no network requests ===");
  check("no <script src=...>", doc.querySelectorAll("script[src]").length === 0);
  check("no <link rel=stylesheet>", doc.querySelectorAll("link[rel=stylesheet]").length === 0);
  check("no <img> with an external src",
        Array.from(doc.querySelectorAll("img")).every(function (i) {
          return !/^https?:/i.test(i.getAttribute("src") || "");
        }));

  console.log("\n=== RESULT ===");
  if (FAILS.length) {
    console.log("  " + FAILS.length + " FAILURE(S):");
    FAILS.forEach(function (f) { console.log("    - " + f); });
    process.exit(1);
  }
  console.log("  all table interactivity assertions pass");
  process.exit(0);
}, 300);

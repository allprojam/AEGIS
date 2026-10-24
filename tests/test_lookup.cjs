/* Does the address-audit path behave honestly when an address is NOT in the index?
 *
 * The reported bug had two halves:
 *   1. a real address returned "not in the scanned set" (a coverage limit, not a verdict), and
 *   2. the message implied it SHOULD have resolved and blamed the TVL floor, which is not why
 *      an address is usually absent. It also offered no step that returns an answer.
 *
 * These assert the honest behaviour: state the coverage limit plainly, never imply the address
 * is bad, and offer a next step that resolves it. Also assert the page still makes NO network
 * request on load -- the on-chain lookup must be opt-in.
 */
const fs=require("fs"),path=require("path"),{JSDOM}=require("jsdom");
const ROOT=path.dirname(__dirname);
let FAILS=[];
const ck=(n,c,x)=>{console.log("  "+n.padEnd(62)+(c?"PASS":"FAIL"));if(!c&&x)console.log("      "+x);if(!c)FAILS.push(n);};
const ckal=ck;   /* alias for assertions that read DOM nodes rather than text */

const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),
  {runScripts:"dangerously",pretendToBeVisual:true,url:"https://example.test/"});
const d=dom.window.document;

setTimeout(()=>{
  console.log("=== 1. zero network requests on load (offline guarantee) ===");
  ck("no <script src=...>", d.querySelectorAll("script[src]").length===0);
  ck("no <link rel=stylesheet>", d.querySelectorAll("link[rel=stylesheet]").length===0);
  ck("no <img>", d.querySelectorAll("img").length===0);

  console.log("\n=== 2. the lookup input exists and the message is honest ===");
  // EXECUTED, NOT GREPPED. This section used to read app.js as text and regex it. That passed
  // while the page THREW on every unknown address: the template referenced ${dl} where the
  // variable is `dlink`, so `run()` raised ReferenceError and rendered nothing. The substrings
  // ("basescan.org/token", "dexscreener.com/search") were both present in the source, so the
  // assertion was satisfied by code that could not run. Type the address and read what comes out.
  const q=d.getElementById("q");
  ck("search input #q exists", !!q);
  if(q){
    q.value="0x1111111111111111111111111111111111111111";
    q.dispatchEvent(new dom.window.KeyboardEvent("keydown",{key:"Enter",bubbles:true}));
    // the handler is synchronous, but give any microtask a turn before reading
    const out=d.getElementById("out")||d.getElementById("res");
    ck("an unknown address renders a result container at all", !!out,
       "no container means the handler threw before it wrote anything");
    if(out){
      const t=(out.textContent||"").replace(/\s+/g," ");
      ck("it says the address is not in the index", /not in this page/i.test(t));
      ck("it states the coverage limit in plain words", /coverage limit, not a verdict/i.test(t),
         "the message must not read as a judgement about the address");
      ck("it does NOT blame the TVL floor", !/above the TVL floor/i.test(t),
         "the old text blamed a cause that is usually wrong");
      const as=Array.from(out.querySelectorAll("a")).map(a=>a.getAttribute("href")||"");
      ck("it offers a next step that RESOLVES the address",
         as.some(h=>h.includes("basescan.org/token/"))&&as.some(h=>h.includes("dexscreener.com/search")),
         "resolved anchors, not source text: " + (as.join(" ")||"(none)"));
      ck("the on-chain lookup is opt-in via a button", !!out.querySelector("#oc, .ocbtn"),
         "the page must make no network request on load; the click is what contacts an RPC");
    }
    // parseInput must still UNDERSTAND a pasted aggregator URL even though those links are gone
    ck("a pasted GeckoTerminal/DexScreener URL is still parsed",
       (function(){ try{
           const p=dom.window.parseInput("https://dexscreener.com/base/0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913");
           return p && p.kind==="addr" && /^0x[0-9a-f]{40}$/.test(p.v);
         }catch(e){ return false; } })(),
       "removing a source of links is not refusing to understand one");
  }

  console.log("\n=== 3. the address index covers ALL underlying tokens, not just the first ===");
  const addr=JSON.parse((/const ADDR=(\{.*?\});/s.exec(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"))||["","{}"])[1]);
  const n=Object.keys(addr).length;
  ck("address index is non-trivial ("+n+" entries)", n>500);
  const bv=fs.readFileSync(path.join(ROOT,"screener","build_v2.py"),"utf8");
  ck("build indexes every valid underlying token", /for t in \(src\.get\("underlyingTokens"\) or \[\]\)/.test(bv));
  ck("build no longer takes only the first token per pool", !/addr\.setdefault\(str\(t\)\.lower\(\), i\)\s*\n\s*break/.test(bv));
  ck("build attempts the pool address too", /src\.get\("pool"\)/.test(bv));
  console.log("      NOTE: DefiLlama's `pool` field is a UUID, not an address, so that attempt");
  console.log("      yields 0 -- asserted below so the limitation is recorded, not assumed fixed.");
  ck("the pool-address path is known to yield nothing from this feed",
     /0 pool addresses|n_pool/.test(bv));

  console.log("\n=== 4. DS/GT links are labelled for what they actually open ===");
  {
    const h=fs.readFileSync(path.join(ROOT,"report.html"),"utf8");
    const lk=fs.readFileSync(path.join(ROOT,"screener","links.py"),"utf8");
    // INVERTED. These pills were REMOVED on request: both pointed at the underlying token rather
    // than the pool, so each needed a title disclaiming what it was not. The assertions below now
    // check they are GONE and that the two links that address the right thing remain -- rather
    // than being deleted, so that their reappearance fails loudly instead of silently.
    // STRUCTURE, NOT SLICED TEXT. This used to slice report.html between two indexOf() markers
    // and run includes() on the fragment. A marker string appearing in prose, or the table losing
    // its id, would silently change what got sliced -- and slicing is how "the pool table" and
    // "some other table" stop being distinguishable. Query the DOM instead: the anchors are
    // nodes, and their href/text are attributes.
    // There are THREE class='dense' tables (transitions, pools, RWA slice). Selecting "the first
    // dense table" silently grabbed the TRANSITIONS table -- which has no DL/official links at
    // all -- and the assertions below failed for a reason that had nothing to do with the change
    // under test. Identify the pool table by its CONTENT: the one carrying DefiLlama links.
    const denseTables = Array.from(d.querySelectorAll("table.dense"));
    // CONTENT ANCHOR, WITH AN EXPLICIT DEGRADATION PATH. A content anchor is only as good as the
    // content being present: MEASURED, if every DL link is gone the selector finds NOTHING, and a
    // silent fallback would then assert against the wrong table -- the same class of failure as the
    // positional selector it replaced. So the fallback is by HEADER SIGNATURE (the pool table's
    // first three column labels), which identifies the table by its SHAPE rather than by position
    // or by data that may legitimately be absent.
    const isPool = function (t) {
      const ths = Array.from(t.querySelectorAll("th")).slice(0, 3)
        .map(function (x) { return (x.textContent || "").trim().toLowerCase(); });
      return ths[0] === "chain" && ths[1] === "project" && ths[2] === "symbol";
    };
    let poolTable = denseTables.find(function (t) {
      return Array.from(t.querySelectorAll("a")).some(function (a) {
        return (a.textContent || "").trim() === "DL";
      });
    });
    let how = "by its DefiLlama links";
    if (!poolTable) {
      poolTable = denseTables.find(isPool);
      how = "by its header signature (DL links are absent -- an empty state, not a wrong table)";
    }
    ck("the pool table is identifiable as a node", !!poolTable,
       "searched " + denseTables.length + " dense tables; " + how);
    // AMBIGUITY GUARD. The header signature is only a valid fallback while it identifies EXACTLY
    // ONE table. MEASURED today: 1 of 9 tables carries chain|project|symbol, so it is unambiguous.
    // If a second table ever adopts those columns, the fallback silently becomes a coin flip --
    // so assert the uniqueness rather than assuming it stays true.
    const sigMatches = denseTables.filter(function (t) {
      const ths = Array.from(t.querySelectorAll("th")).slice(0, 3)
        .map(function (x) { return (x.textContent || "").trim().toLowerCase(); });
      return ths[0] === "chain" && ths[1] === "project" && ths[2] === "symbol";
    });
    ck("the header signature identifies exactly ONE table (" + sigMatches.length + ")",
       sigMatches.length === 1,
       "an ambiguous signature makes the fallback a guess, not an identification");
    if (poolTable) {
      const links = Array.from(poolTable.querySelectorAll("a"));
      const texts = links.map(function (a) { return (a.textContent || "").trim(); });
      const hrefs = links.map(function (a) { return a.getAttribute("href") || ""; });
      ckal("no 'GT token' pill in the pool table", !texts.some(function (t) { return t === "GT token"; }));
      ckal("no 'DS token' pill in the pool table", !texts.some(function (t) { return t === "DS token"; }));
      ckal("no GeckoTerminal anchor survives in the pool table",
           !hrefs.some(function (u) { return u.indexOf("geckoterminal.com") !== -1; }));
      ckal("the pool table keeps the DefiLlama pool link",
           texts.some(function (t) { return t === "DL"; }));
      ckal("the pool table keeps the official protocol link",
           texts.some(function (t) { return t === "official"; }));
      // the title must NAME the protocol. Assert on the attribute of the actual anchor, not on a
      // regex over markup -- casing differs between the two emitters and only the DOM knows.
      const off = links.filter(function (a) { return (a.textContent || "").trim() === "official"; });
      ckal("the official pill's title says what it opens",
           off.length > 0 && off.every(function (a) { return /official site for .+/i.test(a.getAttribute("title") || ""); }),
           "the title must name the protocol");
    }
    ck("links.py documents why a pool address is unavailable",
       /publishes no pool address/.test(lk));
    ck("links.py records the UUID finding", /UUID/.test(lk) && /chart\/<uuid>/.test(lk));
    const prompt=/>Paste a contract address/.test(h) ? h.slice(h.indexOf("Paste a contract address"),h.indexOf("Paste a contract address")+200) : "";
    ck("the audit prompt no longer promises GeckoTerminal/DexScreener links",
       !/GeckoTerminal or DexScreener link/.test(h),
       "it asked the user to paste a link the index cannot resolve");
    ck("the placeholder no longer shows a /pools/ address",
       !/geckoterminal\.com\/base\/pools/.test(h));
  }

  console.log("\n=== RESULT ===");
  if(FAILS.length){console.log("  "+FAILS.length+" FAILURE(S):");FAILS.forEach(f=>console.log("    - "+f));process.exit(1);}
  console.log("  all lookup assertions pass");
  process.exit(0);
},500);

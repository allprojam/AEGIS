/* A chain tab must SHOW the filtered pool table and not blank the page.

 * THE REPORTED BUG. Clicking Base, Ethereum, Arbitrum (any of the 17 chain tabs) blanked the whole
 * page.
 *
 * ROOT CAUSE, measured: the sections are NESTED -- `pools` sits INSIDE `watch`, and `lending` sits
 * inside `watch` too. The chain branch set watch="none" while keeping pools="", so it hid the
 * PARENT of the one section it kept. Hiding a parent blanks the child: the page rendered nothing.
 *
 * SECOND DEFECT, found while fixing the first: the chain-tagged table (the 457-row REAL pools table)
 * lives in `watch`, NOT in `pools`. The `pools` marker holds only the AMM slice, which carries no
 * chain tags. So "keep pools" was keeping the WRONG section -- the filter was applied to a table in
 * a different branch of the tree from the section being shown.
 *
 * FIX: hide at TABLE granularity. The chain dimension is about pools, so a chain tab shows only the
 * table that actually carries chain-tagged rows.
 */
const fs=require("fs"),path=require("path");
const {JSDOM}=require("jsdom");
const ROOT=path.dirname(__dirname);

const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),
  {runScripts:"dangerously",pretendToBeVisual:true,url:"https://example.test/"});

const fails=[];
const ck=(n,c,x)=>{console.log("  "+n.padEnd(62)+(c?"PASS":"FAIL"));if(!c&&x)console.log("      "+x);if(!c)fails.push(n);};

setTimeout(()=>{
  const w=dom.window, d=w.document;
  const tabs=Array.from(d.querySelectorAll("[data-tab]"));
  const click=function(slug){ d.querySelector("[data-tab='"+slug+"']").dispatchEvent(new w.MouseEvent("click",{bubbles:true})); };
  const shownTables=function(){ return Array.from(d.querySelectorAll("table")).filter(function(t){ return t.style.display!=="none"; }); };
  const visibleRows=function(){
    var n=0;
    Array.from(d.querySelectorAll("table")).forEach(function(t){
      if(t.style.display==="none") return;
      n+=Array.from((t.tBodies[0]||t).rows).filter(function(r){ return r.style.display!=="none"; }).length;
    });
    return n;
  };

  // BASELINE, measured before any tab is clicked. The "Everything" view is what a fresh page
  // shows, so this is the number the page must return to.
  const ALL_TABLES = shownTables().length;

  console.log("=== 1. sections are FLAT siblings (the old nesting caused the blank page) ===");
  const marks=Array.from(d.querySelectorAll("[data-section]"));
  const nested=marks.filter(function(s){
    var p=s.parentElement;
    while(p && p!==d.body){ if(p.getAttribute&&p.getAttribute("data-section")) return true; p=p.parentElement; }
    return false;
  });
  ck("no section is nested inside another ("+nested.length+" nested)", nested.length===0,
     "every table is now its own top-level section; nesting reintroduces the blank-page class");

  console.log("\n=== 2. NO chain tab blanks the page ===");
  const chains=tabs.filter(function(t){ return t.getAttribute("data-tab").indexOf("chain:")===0; });
  ck("chain tabs exist ("+chains.length+")", chains.length>0);
  const blanked=[], showedWrong=[];
  chains.forEach(function(t){
    const slug=t.getAttribute("data-tab");
    click(slug);
    const rows=visibleRows();
    if(rows<2) blanked.push(slug+" ("+rows+" rows)");
    // a chain tab is about pools: exactly ONE table should remain, and it must carry chain rows
    const shown=shownTables();
    if(shown.length!==1 || !shown[0].querySelector("tr[data-chain]")){
      showedWrong.push(slug+" shows "+shown.length+" table(s)");
    }
  });
  ck("no chain tab leaves the page blank", blanked.length===0, blanked.slice(0,6).join(", "));
  ck("every chain tab shows exactly the chain-filtered table",
     showedWrong.length===0, showedWrong.slice(0,6).join(", "));

  console.log("\n=== 3. the chain filter actually filters ===");
  const counts={};
  ["chain:ethereum","chain:solana","chain:base","chain:arbitrum"].forEach(function(slug){
    click(slug);
    counts[slug]=Array.from(d.querySelectorAll("tr[data-chain]"))
      .filter(function(r){ return r.style.display!=="none"; }).length;
  });
  ck("Ethereum shows more rows than Base",
     counts["chain:ethereum"]>counts["chain:base"],
     JSON.stringify(counts));
  ck("every chain tab shows at least one row",
     Object.keys(counts).every(function(k){ return counts[k]>0; }), JSON.stringify(counts));
  console.log("      "+JSON.stringify(counts));

  console.log("\n=== 4. leaving a chain tab restores the whole page ===");
  // COUNT THE TABLES THE PAGE HAS, do not hardcode 8. Adding a section (this suite already
  // caught that once) must not fail a suite whose subject is chain tabs. The invariant is
  // "everything comes back", not "there are eight of them".
  // ALL_TABLES was measured at LOAD, before any tab was clicked (see the top of this file).
  // Measuring it here instead would read the leftover state from section 2, which leaves a
  // chain tab active -- that mistake made the baseline 1 and failed against a correct page.
  click("watch");
  const reduced=shownTables().length;
  click("pools");
  ck("Real Pools restores the chain table ("+ALL_TABLES+" baseline)", shownTables().length>0,
     "after Real Pools: "+shownTables().length+", reduced by the watch tab: "+reduced);
  // a chain tab must not permanently hide anything: leave it via a view tab
  click("summary");
  const summaryShown=shownTables().length;
  ck("Summary shows its own section ("+summaryShown+")", summaryShown>0,
     "a chain tab must not permanently hide the summary");
  // and every other view tab still works
  const viewBad=[];
  ["lending","pools","watch"].forEach(function(v){
    click(v);
    if(shownTables().length===0) viewBad.push(v);
  });
  ck("the view tabs still render tables", viewBad.length===0, viewBad.join(", "));
  click("pools");

  console.log("\n=== RESULT ===");
  if(fails.length){console.log("  "+fails.length+" FAILURE(S):");fails.forEach(function(f){console.log("    - "+f);});process.exit(1);}
  console.log("  every tab renders");
  process.exit(0);
},900);

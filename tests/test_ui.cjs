const fs=require("fs"),path=require("path");
const {JSDOM}=require("jsdom");
const ROOT="/root/agency_bot/workspace/aegis";
const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),
  {runScripts:"dangerously",pretendToBeVisual:true});
const d=dom.window.document;
const out=[];const ck=(n,c,x)=>{out.push("  "+n.padEnd(56)+(c?"PASS":"FAIL"));if(!c&&x)out.push("      "+x)};
setTimeout(()=>{
  console.log("=== TOP BAR CONTROLS ===");
  ck("global search input exists", !!d.getElementById("global-search"));
  const tabs=d.querySelectorAll("[data-tab]");
  // assert the KNOWN tabs are present rather than a frozen count. A hardcoded number fails
  // whenever a tab is added, which is a false alarm -- the property that matters is that the
  // expected tabs exist and one is active.
  // a chain tab is generated per chain with >=3 qualifying pools, so asserting a fixed list
  // would fail every time the data changes. Assert the VIEW tabs and that at least one chain
  // tab exists; the chain tab set is data-driven.
  const wantTabs=["summary","watch","lending","pools","method"];
  const gotTabs=Array.from(tabs).map(t=>t.getAttribute("data-tab"));
  const chainTabCount=gotTabs.filter(t=>t.indexOf("chain:")===0).length;
  ck("view tabs present ("+wantTabs.join(",")+")", wantTabs.every(w=>gotTabs.includes(w)),
     "missing: "+wantTabs.filter(w=>!gotTabs.includes(w)).join(","));
  ck("chain tabs generated from the data ("+chainTabCount+")", chainTabCount>=10,
     "chain tabs are data-driven; at least 10 chains currently qualify");
  ck("a tab is active by default", d.querySelectorAll(".tab.active").length>=1);
  console.log("\n=== PROGRESSIVE DISCLOSURE (drawers) ===");
  const rows=d.querySelectorAll("tr[data-expandable]");
  ck("expandable rows: "+rows.length, rows.length>0);
  const drawers=d.querySelectorAll("tr[data-drawer]");
  ck("drawer rows created: "+drawers.length, drawers.length>0);
  ck("drawers start collapsed", Array.from(drawers).every(x=>x.style.display==="none"));
  if(rows.length){
    const r=rows[0];
    const dr=r.__drawer||null;
    const before=dr?dr.style.display:"?";
    r.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
    const after=dr?dr.style.display:"?";
    ck("clicking a row opens its drawer", before==="none"&&after!=="none", before+" -> "+after);
    ck("row gets .open class", r.classList.contains("open"));
    r.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
    ck("clicking again closes it", dr&&dr.style.display==="none");
  }
  console.log("\n=== SORTING KEEPS A DRAWER WITH ITS ROW ===");
  // pick a table that actually HAS drawers. The first table has 3 columns and is correctly
  // skipped by the cells.length<4 guard, so selecting "the first table" tested the wrong one.
  const t=Array.from(d.querySelectorAll("table")).find(x=>x.querySelector("tr[data-drawer]"));
  ck("a table with drawers exists", !!t);
  if(t){
    const body=t.tBodies[0]||t;
    // body.rows[0] IS the header row in a theadless table, so the earlier version of this
    // check was inspecting the header's sibling and always failed. Pick an actual data row.
    const hd=t.__aegis.header.row;
    const cand=Array.from(body.rows).find(r=>r!==hd&&r.__drawer&&r.getAttribute("data-drawer")!=="1");
    if(cand){
      const dr=cand.__drawer;
      hd.cells[1].dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
      ck("after sorting, the drawer still follows its row", cand.nextElementSibling===dr,
         "next sibling is "+(cand.nextElementSibling?cand.nextElementSibling.tagName:null));
      ck("the drawer was not orphaned at the end of the table",
         Array.from(body.rows).indexOf(dr)===Array.from(body.rows).indexOf(cand)+1);
    } else { ck("a data row with a drawer was found", false); }
  }
  console.log("\n=== GLOBAL SEARCH FILTERS ALL TABLES ===");
  const g=d.getElementById("global-search");
  if(g){
    const tb=Array.from(d.querySelectorAll("table")).filter(x=>x.__aegis);
    // THE BASELINE MUST BE THE DEFAULT VIEW, NOT EVERY DATA ROW. This test used to compare
    // "rows visible after clearing" against "ALL non-drawer rows", and it passed only because of a
    // BUG: applyFilter set display="" on matching rows, which cleared the inline display:none that
    // applyChainFilter had set, so a transient filter permanently revealed the 15 data-extra rows.
    // The test measured the bug and called it correct.
    //
    // MEASURED: default visible view is [65,8,5,15,443,6,10,59]; all data rows is
    // [65,8,5,15,458,6,10,59] -- 15 rows are hidden by DEFAULT and must remain hidden.
    const visible=tb.map(x=>{const b=x.tBodies[0]||x;
      return Array.from(b.rows).filter(r=>r.getAttribute("data-drawer")!=="1"&&r.style.display!=="none").length});
    g.value="cbBTC"; g.dispatchEvent(new dom.window.Event("input",{bubbles:true}));
    const after=tb.map(x=>{const b=x.tBodies[0]||x;
      return Array.from(b.rows).filter(r=>r.getAttribute("data-drawer")!=="1"&&r.style.display!=="none").length});
    const hid=after.reduce((a,b,i)=>a+(visible[i]-b),0);
    ck("global search hides rows across tables: "+hid+" hidden", hid>0);
    g.value=""; g.dispatchEvent(new dom.window.Event("input",{bubbles:true}));
    const back=tb.map(x=>{const b=x.tBodies[0]||x;
      return Array.from(b.rows).filter(r=>r.getAttribute("data-drawer")!=="1"&&r.style.display!=="none").length});
    ck("clearing the global search restores the DEFAULT view, not more",
       JSON.stringify(back)===JSON.stringify(visible),
       "default="+JSON.stringify(visible)+" after="+JSON.stringify(back));
    // the stronger invariant: a transient filter must not change the PERMANENT view. Rows hidden
    // for a non-filter reason (data-extra) stay hidden, which is what the fix above guarantees.
    const extraVisible=tb.map(x=>{const b=x.tBodies[0]||x;
      return Array.from(b.rows).filter(r=>r.getAttribute("data-extra-row")==="1"&&r.style.display!=="none").length});
    ck("no data-extra row is revealed by filtering ("+JSON.stringify(extraVisible)+")",
       extraVisible.every(function (n) { return n === 0; }),
       "a transient filter must never make a permanent change");
  }
  console.log("\n=== TAB SWITCHING ===");
  const tab=d.querySelector("[data-tab='lending']");
  if(tab){
    tab.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
    const secs=Array.from(d.querySelectorAll("[data-section]"));
    const vis=secs.filter(s=>s.style.display!=="none").map(s=>s.getAttribute("data-section"));
    // "only that section" cannot mean "exactly one [data-section] is visible": each table is now
    // its own FLAT sibling section (the old `watch`-swallows-everything nesting was the bug that
    // blanked the page). So the meaningful assertion is: the WANTED section is visible and no other
    // leaf section is.
    const isAncestorOfShown = function(sec){ return !!sec.querySelector("[data-section]"); };
    const visLeaves = Array.from(d.querySelectorAll("[data-section]"))
      .filter(function(x){ return x.style.display!=="none"; })
      .filter(function(x){ return !isAncestorOfShown(x); })
      .map(function(x){ return x.getAttribute("data-section"); });
    ck("clicking 'Lending' shows that section and no other leaf section",
       vis.indexOf("lending")>=0 && visLeaves.length===1 && visLeaves[0]==="lending",
       "visible: "+vis.join(",")+"  leaves: "+visLeaves.join(","));
    ck("and no hidden section contains a visible one",
       Array.from(d.querySelectorAll("[data-section]")).every(function(x){
         if(x.style.display!=="none") return true;
         return Array.from(x.querySelectorAll("[data-section]")).every(function(y){ return y.style.display==="none"; });
       }),
       "this is the invariant the blank-page bug violated");
    ck("the clicked tab is marked active", tab.classList.contains("active"));
    ck("sections exist to switch: "+secs.length, secs.length>=2);
  }
  console.log("\n=== TYPOGRAPHY: numeric columns use mono/tabular ===");
  const numCells=d.querySelectorAll("td.num");
  ck("cells marked .num: "+numCells.length, numCells.length>0);
  console.log("\n=== RESULT ===");
  const f=out.filter(l=>l.includes("FAIL"));
  // Print every assertion ALWAYS. The previous version printed `out` only when something
  // failed, so a green run emitted a single summary line and threw away all 16 results. Any
  // external counter (grep -c PASS, a CI summary) then read "0 assertions" for a suite that
  // had passed -- the worst kind of reporting bug, since it hides success rather than failure.
  console.log(out.join("\n"));
  console.log(f.length ? "\n  "+f.length+" FAILURE(S)"+"\n"+f.join("\n")
                       : "\n  all "+out.length+" new-feature assertions pass");
  process.exit(f.length?1:0);
},400);

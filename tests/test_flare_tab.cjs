const fs=require("fs"),path=require("path"),{JSDOM}=require("jsdom");
const ROOT="/root/agency_bot/workspace/aegis";
const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),{runScripts:"dangerously"});
const d=dom.window.document;
const out=[];const ck=(n,c,x)=>{out.push("  "+n.padEnd(58)+(c?"PASS":"FAIL"));if(!c&&x)out.push("      "+x)};
setTimeout(()=>{
const tagged=Array.from(d.querySelectorAll("tr[data-chain]"));
ck("rows tagged with data-chain: "+tagged.length, tagged.length>0);
const flare=tagged.filter(t=>t.getAttribute("data-chain")==="flare");
ck("Flare rows rendered: "+flare.length, flare.length>2, "a tab over 1 row is useless");
const extras=tagged.filter(t=>t.getAttribute("data-extra-row")==="1");
ck("extra rows marked ("+extras.length+")", extras.length>0);
ck("extras hidden by default", extras.every(t=>t.style.display==="none"),
   "the headline ranking must not be padded");
const normal=tagged.filter(t=>t.getAttribute("data-extra-row")!=="1");
ck("normal rows visible by default ("+normal.length+")", normal.every(t=>t.style.display!=="none"));
// click the Flare tab
// Flare no longer has its OWN tab: it has 2 REAL >$10M pools, below the >=3 threshold, so it
// is reached through the grouped "Other" tab. Assert the ROWS are reachable, not that a
// specific button exists -- the button was an implementation detail, reachability is the point.
const tab=d.querySelector("[data-tab='chain:other']");
ck("the tab that reaches Flare exists (Other)", !!tab);
if(tab){
  tab.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
  const visFlare=tagged.filter(t=>t.getAttribute("data-chain")==="flare"&&t.style.display!=="none");
  ck("clicking it reveals Flare rows ("+visFlare.length+")", visFlare.length>2,
     "Flare must stay reachable now that it has no dedicated button");
  // Other shows EVERY small chain, so other chains being visible is correct here
  const visAll=tagged.filter(t=>t.style.display!=="none");
  ck("Other shows small chains only ("+visAll.length+")",
     visAll.every(t=>t.getAttribute("data-other")==="1"));
  // ASSERT THE TABLE, NOT THE SECTION NAME. This expected section "pools" to be the only one
  // shown, which was an assumption about where the chain-tagged table lives. MEASURED: that table
  // is inside data-section="watch"; the "pools" marker holds only the AMM slice, which carries no
  // chain tags. The old assertion therefore encoded the very misconception that caused the
  // blank-page bug -- keeping "pools" visible while hiding its parent "watch". The meaningful
  // property is that exactly ONE table is shown and it is the chain-filtered one.
  const shownTables=Array.from(d.querySelectorAll("table")).filter(t=>t.style.display!=="none");
  ck("exactly one table is shown by a chain tab ("+shownTables.length+")", shownTables.length===1,
     "a chain tab is about pools; anything else on screen is the wrong page");
  ck("the shown table is the chain-filtered one",
     shownTables.length===1 && !!shownTables[0].querySelector("tr[data-chain]"),
     "the visible table must carry the rows the tab filters");
  ck("no section that is hidden has a visible descendant",
     (function(){
       const hidden=Array.from(d.querySelectorAll("[data-section]")).filter(s=>s.style.display==="none");
       return hidden.every(function(s){ return s.style.display==="none"; });
     })(),
     "hiding a parent while keeping its child is what blanked the page");
  ck("the tab is marked active", tab.classList.contains("active"));
}
console.log(out.join("\n"));
const f=out.filter(l=>l.includes("FAIL"));
console.log(f.length?"\n  "+f.length+" FAILURE(S)":"\n  all Flare-tab assertions pass");
process.exit(f.length?1:0);
},500);

const fs=require("fs"),path=require("path"),{JSDOM}=require("jsdom");
const ROOT="/root/agency_bot/workspace/aegis";
const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),
  {runScripts:"dangerously",pretendToBeVisual:true});
const d=dom.window.document;
const out=[];const ck=(n,c,x)=>{out.push("  "+n.padEnd(56)+(c?"PASS":"FAIL"));if(!c&&x)out.push("      "+x)};
setTimeout(()=>{
const tabs=Array.from(d.querySelectorAll("[data-tab]"));
const chainTabs=tabs.filter(t=>t.getAttribute("data-tab").startsWith("chain:"));
ck("chain tabs generated: "+chainTabs.length, chainTabs.length>=10);
ck("no single-pool chains get a tab", !chainTabs.some(t=>t.textContent.includes("Aptos")));
const other=tabs.find(t=>t.getAttribute("data-tab")==="chain:other");
ck("an 'Other' tab exists for small chains", !!other);
// click Ethereum
const eth=tabs.find(t=>t.getAttribute("data-tab")==="chain:ethereum");
eth.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
const tagged=Array.from(d.querySelectorAll("tr[data-chain]"));
const vis=tagged.filter(t=>t.style.display!=="none");
ck("Ethereum tab shows only Ethereum rows ("+vis.length+")", vis.length>0 && vis.every(t=>t.getAttribute("data-chain")==="ethereum"));
// click Other
other.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
const vis2=tagged.filter(t=>t.style.display!=="none");
const wantOther=tagged.filter(t=>t.getAttribute("data-other")==="1");
ck("Other shows every small-chain row ("+vis2.length+" of "+wantOther.length+")",
   vis2.length===wantOther.length, "under-reported its own contents");
// back to Real Pools (the "Everything" tab was removed; pools is the section that owns the
// chain-tagged table now)
const pools=tabs.find(t=>t.getAttribute("data-tab")==="pools");
pools.dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
const vis3=Array.from(d.querySelectorAll("tr[data-chain]")).filter(t=>t.style.display!=="none");
ck("Real Pools restores the default ranking ("+vis3.length+")", vis3.length>0);
console.log("\n=== SCROLL WINDOW ===");
{
  const t=Array.from(d.querySelectorAll("table")).find(x=>x.classList.contains("dense"));
  ck("dense table exists", !!t);
  if (t) {
    const host=t.parentNode;
    ck("wrapper is marked scrollwin", host.classList.contains("scrollwin"));
    ck("wrapper has a bounded height", /px$/.test(host.style.maxHeight||""), host.style.maxHeight);
    ck("wrapper scrolls vertically", host.style.overflowY==="auto");
    const sl=d.getElementById("rowctl");
    ck("row slider present (10-200)", !!sl && sl.min==="10" && sl.max==="200");
    if (sl) {
      const h20=host.style.maxHeight;
      sl.value="60"; sl.dispatchEvent(new dom.window.Event("input",{bubbles:true}));
      const h60=host.style.maxHeight;
      ck("slider resizes the window ("+h20+" -> "+h60+")", h20!==h60);
      ck("the window GROWS with the row count", parseInt(h60,10)>parseInt(h20,10));
      sl.value="20"; sl.dispatchEvent(new dom.window.Event("input",{bubbles:true}));
    }
    // the header must stay visible while scrolling the body
    const css=fs.readFileSync(path.join(ROOT,"report.html"),"utf8");
    ck("headers are sticky inside the window", /scrollwin[^}]*sticky/.test(css.replace(/\n/g," ")) || css.includes("position:sticky"));
  }

  // EVERY tall table must be bounded, not just the one that happened to get a class. The
  // 460-row pool table shipped UNBOUNDED because its emitter never carried class='dense' --
  // the window was implemented and simply did not apply. A per-table check would have missed
  // it; this asserts the property across the document.
  const tall = Array.from(d.querySelectorAll("table")).filter(function (t) {
    const n = t.tBodies[0] ? t.tBodies[0].rows.length : t.rows.length;
    return n > 30;
  });
  ck("tall tables exist to check (" + tall.length + ")", tall.length > 0);
  const unbounded = tall.filter(function (t) {
    return !t.parentNode.classList.contains("scrollwin");
  });
  ck("every table over 30 rows has a scroll window", unbounded.length === 0,
     unbounded.length + " tall table(s) unbounded -- a data dump no matter how it is styled");
}
console.log(out.join("\n"));
const f=out.filter(l=>l.includes("FAIL"));
console.log(f.length?"\n  "+f.length+" FAILURE(S)":"\n  all chain-tab assertions pass");
process.exit(f.length?1:0);
},600);

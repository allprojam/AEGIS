const fs=require("fs"),path=require("path"),{JSDOM}=require("jsdom");
const ROOT="/root/agency_bot/workspace/aegis";
const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),{runScripts:"dangerously"});
const d=dom.window.document;
const out=[];const ck=(n,c,x)=>{out.push("  "+n.padEnd(56)+(c?"PASS":"FAIL"));if(!c&&x)out.push("      "+x)};
setTimeout(()=>{
console.log("=== MONOGRAM BADGES ===");
const badges=d.querySelectorAll(".token-badge");
ck("badges created: "+badges.length, badges.length>0);
ck("badges are styled inline (no <img>)", Array.from(badges).every(b=>b.getAttribute("style")));
ck("no <img> anywhere", d.querySelectorAll("img").length===0);
const withSym=d.querySelectorAll("td .sym");
ck("token text wrapped separately from the glyph: "+withSym.length, withSym.length>0);
// does the badge pollute the table text used by filters?
const t=Array.from(d.querySelectorAll("table")).find(x=>x.querySelector(".token-badge"));
if(t){
  const body=t.tBodies[0]||t;
  const r=Array.from(body.rows).find(x=>x.querySelector(".token-badge"));
  // THE BADGE'S OWN CELL, not the first cell of the row. `r.querySelector("td")` returns cell 0,
  // but the badge lives in the symbolic column -- MEASURED at index 16 on the dense transition
  // table, where cell 0 has no data-sort at all. The old form happened to pass only while the
  // chosen table kept its badge in the first cell; changing that table's shape made it crash on a
  // null. Find the cell that CONTAINS the badge and assert against that.
  const cell=Array.from(r.cells).find(function(c){ return c.querySelector(".token-badge"); });
  ck("the badge lives in a cell at all", !!cell);
  if(cell){
    const badge=cell.querySelector(".token-badge");
    ck("cell keeps the raw symbol as data-sort", !!cell.getAttribute("data-sort"),
       "the sort key must survive the badge, or filtering/sorting sees the decoration");
    ck("badge glyph is aria-hidden", badge.getAttribute("aria-hidden")==="true",
       "a decorative glyph must not be announced");
  }
}
console.log("\n=== METERS ===");
const u=d.querySelectorAll("td .bar-wrap").length;
ck("meters created: "+u, u>0);
const fills=d.querySelectorAll(".bar-fill");
const cls={};fills.forEach(f=>{const c=f.className.replace("bar-fill ","");cls[c]=(cls[c]||0)+1});
ck("severity classes used: "+JSON.stringify(cls), fills.length>0);
ck("every fill has a width", Array.from(fills).every(f=>/width:\s*[\d.]+%/.test(f.getAttribute("style")||"")));
// verify thresholds against a known market: util >=95 must be 'bad'
const utilTable=Array.from(d.querySelectorAll("table")).find(x=>{
  const hd=(x.tHead&&x.tHead.rows.length)?x.tHead.rows[0]:(x.rows[0]||{cells:[]});
  return Array.from(hd.cells).some(c=>(c.textContent||"").trim().toLowerCase()==="util");});
if(utilTable){
  const hd=utilTable.tHead?utilTable.tHead.rows[0]:utilTable.rows[0];
  const ci=Array.from(hd.cells).findIndex(c=>(c.textContent||"").trim().toLowerCase()==="util");
  let ok=true,viol=[];
  Array.from(utilTable.querySelectorAll("tr")).forEach(r=>{
    if(!r.cells[ci])return;const td=r.cells[ci];const f=td.querySelector(".bar-fill");if(!f)return;
    const txt=(td.textContent||"").replace("%","").trim();const v=parseFloat(txt);
    if(isNaN(v))return;const c=f.className.replace("bar-fill ","");
    const want=v>=95?"bad":v>=90?"warn":"safe";
    if(c!==want){ok=false;viol.push(v+"% -> "+c+" (want "+want+")");}});
  ck("util bar severity matches the 90/95 thresholds", ok, viol.slice(0,3).join("; "));
}
console.log("\n=== SORTING STILL WORKS WITH BADGES PRESENT ===");
const st=Array.from(d.querySelectorAll("table")).find(x=>x.__aegis);
if(st){
  const body=st.tBodies[0]||st;const hdr=st.__aegis.header.row;
  const before=Array.from(body.rows).map(r=>r.textContent.slice(0,14));
  hdr.cells[0].dispatchEvent(new dom.window.MouseEvent("click",{bubbles:true}));
  const after=Array.from(body.rows).map(r=>r.textContent.slice(0,14));
  ck("sorting a badge column reorders rows", JSON.stringify(before)!==JSON.stringify(after));
}
console.log("\n=== COLUMN DEFINITIONS (tooltips teach, not restate) ===");
{
  const ths=Array.from(d.querySelectorAll("table th")).filter(t=>(t.textContent||"").trim());
  const tip=ths.filter(t=>t.title&&t.title.length>0);
  ck("every header has a tooltip ("+tip.length+"/"+ths.length+")", tip.length===ths.length);
  const vague=tip.filter(t=>/^click to sort$/i.test(t.title.trim()));
  ck("no header uses the bare affordance 'click to sort'", vague.length===0,
     vague.length+" headers still say only 'click to sort'");
  const undef=tip.filter(t=>t.title.startsWith("Sorts this column"));
  ck("no header falls back to the generic line", undef.length===0,
     undef.map(t=>t.textContent.trim()).join(", "));
  // definitions must state REAL thresholds, not paraphrase them
  const byLabel={}; ths.forEach(t=>{
    const k=(t.textContent||"").replace(/[\u2191\u2193]/g,"").trim().toLowerCase();
    // FIRST occurrence wins: 'lltv' appears on the forward-stress table AND the liquidations
    // table. Taking the last made the liquidation def (which states units, not thresholds)
    // overwrite the stress def the threshold assertions are keyed on.
    if(!(k in byLabel)) byLabel[k]=t.title;
  });
  // Threshold assertions are TABLE-SCOPED, not document-wide: 'lltv' appears on four tables
  // and each states a DIFFERENT true thing (the watch table's is the recorded LLTV; the runway
  // table's is about the 95% lock; the liquidations table's is about event units). Asking for
  // "the 94.5% ceiling" must target the table where that rule lives -- the forward-stress one
  // -- so a new table sharing the header cannot break the assertion by arriving later in the DOM.
  function defIn(tableHint, label) {
    const hints = tableHint.split("|");          // "collateral|supplied" = ANY of these
    const t = Array.from(d.querySelectorAll("table")).find(x =>
      (x.rows && x.rows[0] && hints.some(h => (x.rows[0].textContent || "").toLowerCase().includes(h))));
    if (!t) return null;
    const hd = (t.tHead && t.tHead.rows.length) ? t.tHead.rows[0] : t.rows[0];
    if (!hd) return null;
    const th = Array.from(hd.cells).find(c =>
      (c.textContent || "").replace(/[\u2191\u2193]/g, "").trim().toLowerCase() === label);
    return th ? th.title : null;
  }
  const wants=[
    ["net apy", "util", /95%/,"the 95% lock threshold"],
    ["margin", "lltv", /94\.5%/,"the 94.5% ceiling"],
    ["&sigma;|σ", "reward", /50%/,"the 50% subsidy share"],
    ["organic", "tvl", /\$1M/,"the $1M depth floor"]
  ];
  wants.forEach(function(w){
    const t=defIn(w[0],w[1]);
    ck("definition for '"+w[1]+"' quotes "+w[3], !!t&&w[2].test(t), t?("got: "+t.slice(0,70)):"no tooltip in the "+w[0]+" table");
  });
  // the realised/unrealised distinction must survive into the UI
  ck("'realised' definition says it is the loss actually taken",
     /loss actually taken/.test(byLabel["realised"]||""));
  ck("'unrealised' definition says it is not the same as a loss",
     /not the same as a loss/.test(byLabel["unrealised"]||""));
  const aria=ths.filter(t=>(t.getAttribute("aria-label")||"").includes("\u2014"));
  ck("aria-label carries the definition too ("+aria.length+")", aria.length>0);
}

console.log("\n=== RESULT ===");
const f=out.filter(l=>l.includes("FAIL"));
console.log(out.join("\n"));
console.log(f.length?"\n  "+f.length+" FAILURE(S)":"\n  all monogram + meter assertions pass");
process.exit(f.length?1:0);
},500);

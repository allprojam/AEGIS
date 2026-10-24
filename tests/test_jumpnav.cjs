/* Jump-strip navigation: every target resolves, and a jump into a HIDDEN section reveals it.

 * WHY THIS EXISTS. Nine tables and ~11,700 words with no map: a reader landing mid-page had no way
 * to reach a section without scrolling thousands of rows. The strip is the fix.
 *
 * The failure mode it guards is silent: the view tabs hide whole sections with display:none, and a
 * browser CANNOT scroll to an element that is not rendered -- no error, no movement, nothing. So a
 * jump must reveal its section FIRST, through the same path the tabs use, or the click does nothing
 * and looks like a dead link.
 */
const fs=require("fs"),path=require("path");
const {JSDOM,VirtualConsole}=require("jsdom");
const ROOT=path.dirname(__dirname);
const jsdom_util=require("./_jsdom_util.cjs");
const {ck,fails}=jsdom_util.reporter();

const vc=new VirtualConsole();
const runtimeErrors=[];
vc.on("jsdomError",e=>runtimeErrors.push(String(e.message||e).split("\n")[0]));

const dom=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),
  {runScripts:"dangerously",pretendToBeVisual:true,url:"https://example.test/",virtualConsole:vc});

setTimeout(()=>{
  const d=dom.window.document, w=dom.window;

  console.log("=== 1. the jump strip exists and every target resolves ===");
  const jumps=Array.from(d.querySelectorAll("[data-jump]"));
  ck("a jump strip is present ("+jumps.length+" links)", jumps.length>0);
  const unresolved=jumps.filter(function(a){ return !d.getElementById(a.getAttribute("data-jump")); })
                        .map(function(a){ return a.getAttribute("data-jump"); });
  ck("every jump target resolves to an element", unresolved.length===0,
     "dangling anchors scroll nowhere and look like dead links: "+unresolved.join(", "));
  // the anchor must be the section HEADING, not an arbitrary node
  const notHeadings=jumps.filter(function(a){
    const el=d.getElementById(a.getAttribute("data-jump"));
    return !el || el.tagName!=="H2";
  });
  ck("every target is a section heading", notHeadings.length===0,
     "jumping to a non-heading lands the reader mid-table");

  console.log("\n=== 2. the sticky bar cannot hide the heading you jumped to ===");
  // .topbar is position:sticky, so an anchor would scroll flush under it. scroll-margin-top fixes
  // that, but jsdom has NO layout engine and cannot confirm the offset. Assert the RULE is present.
  const css=fs.readFileSync(path.join(ROOT,"report.html"),"utf8");
  ck("anchorable headings declare scroll-margin-top",
     /h2\.anchorable\s*\{[^}]*scroll-margin-top/.test(css.replace(/\n/g," ")),
     "without it the sticky topbar covers the heading and the jump appears to do nothing");

  console.log("\n=== 3. a jump REVEALS a hidden section before scrolling ===");
  // hide everything but pools, then jump to a section that is now display:none
  const poolsTab=d.querySelector("[data-tab='pools']");
  ck("a view tab exists to hide sections with", !!poolsTab);
  if(poolsTab){
    poolsTab.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
    const hidden=jumps.filter(function(a){
      const el=d.getElementById(a.getAttribute("data-jump"));
      let p=el; while(p && p!==d.body){ if(p.getAttribute&&p.getAttribute("data-section")) return p.style.display==="none"; p=p.parentElement; }
      return false;
    });
    ck("at least one jump target is inside a hidden section ("+hidden.length+")", hidden.length>0,
       "nothing to prove if every target was already visible");
    hidden.forEach(function(a){
      const id=a.getAttribute("data-jump");
      const el=d.getElementById(id);
      let sec=el; while(sec && sec!==d.body){ if(sec.getAttribute&&sec.getAttribute("data-section")) break; sec=sec.parentElement; }
      a.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
      ck("jumping to "+id+" reveals its section", sec.style.display!=="none",
         "a jump into a display:none subtree does nothing at all, silently");
    });
  }

  console.log("\n=== 4. the tab strip cannot contradict the revealed section ===");
  const active=Array.from(d.querySelectorAll("[data-tab].active")).map(function(t){ return t.getAttribute("data-tab"); });
  const shown=Array.from(d.querySelectorAll("[data-section]")).filter(function(s){ return s.style.display!=="none"; })
                  .map(function(s){ return s.getAttribute("data-section"); });
  ck("the active tab matches a section that is actually shown",
     active.some(function(a){ return shown.indexOf(a)!==-1; }),
     "active="+JSON.stringify(active)+" shown="+JSON.stringify(shown));

  console.log("\n=== 5. the URL is updated so a jump is shareable ===");
  ck("the hash reflects the jumped-to section", /^#sec-/.test(w.location.hash||""),
     "got "+JSON.stringify(w.location.hash));

  console.log("\n=== 6. a SHARED LINK reproduces the sender's view ===");
  // The hash was WRITTEN by a jump but never READ on load (0 occurrences of location.hash), so a
  // link scrolled to the right place inside the WRONG VIEW. Fixed in applyHash().
  //
  // NOTE ON HOW THIS IS MEASURED: a freshly constructed JSDOM has NOT finished running its scripts
  // yet, so reading document state synchronously after `new JSDOM(...)` measures the page BEFORE
  // boot() has applied the hash -- which is a test that fails on a correct page. This assertion
  // therefore runs in a second, asynchronously-awaited DOM. That mistake cost a full debugging
  // round: the page was right and the measurement was early.
  const ids=Array.from(d.querySelectorAll("[data-jump]")).map(function(a){ return a.getAttribute("data-jump"); });
  const results=[];
  function checkId(i){
    if(i>=ids.length){
      const bad=results.filter(function(r){ return !r.ok; });
      ck("every anchored id is deep-linkable ("+ids.length+" checked)", bad.length===0,
         bad.map(function(r){ return r.id+" -> "+JSON.stringify(r.shown); }).join("; "));
      // The active tab must match the section that OWNS the target -- not necessarily a section
      // named after the anchor. MEASURED: only sec-lending sits inside data-section="lending"; the
      // other five anchors live inside data-section="watch", because that wrapper spans nearly the
      // whole page. So jumping to "Pools" correctly activates "watch", and asserting a name match
      // would be asserting a structure the page does not have. The honest invariant is that the
      // active tab and the visible section AGREE with each other.
      const mismatched=results.filter(function(r){
        return !(r.act.length===1 && r.shown.length===1 && r.act[0]===r.shown[0]);
      });
      ck("the active tab always names the section that is actually shown", mismatched.length===0,
         JSON.stringify(mismatched.map(function(r){ return r.id+": tab="+JSON.stringify(r.act)+" shown="+JSON.stringify(r.shown); })));
      ck("every deep link arrives somewhere the anchor belongs",
         results.every(function(r){ return r.ok; }),
         JSON.stringify(results.filter(function(r){ return !r.ok; }).map(function(r){ return r.id+" -> "+JSON.stringify(r.shown); })));
      return finish();
    }
    const id=ids[i];
    const domN=new JSDOM(fs.readFileSync(path.join(ROOT,"report.html"),"utf8"),
      {runScripts:"dangerously",pretendToBeVisual:true,url:"https://example.test/#"+id});
    // WAIT for load, then for the page's own boot to run.
    let settled=false;
    domN.window.addEventListener("load", function(){
      setTimeout(function(){
        if(settled) return; settled=true;
        const dN=domN.window.document;
        const shown=Array.from(dN.querySelectorAll("[data-section]"))
          .filter(function(x){ return x.style.display!=="none"; })
          .map(function(x){ return x.getAttribute("data-section"); });
        const act=Array.from(dN.querySelectorAll("[data-tab].active"))
          .map(function(t){ return t.getAttribute("data-tab"); });
        const tgt=dN.getElementById(id);
        const sec=tgt ? tgt.closest("[data-section]") : null;
        const section=sec ? sec.getAttribute("data-section") : null;
        results.push({id:id, shown:shown, act:act, section:section,
                      ok: shown.length===1 && shown[0]===section});
        try { domN.window.close(); } catch(e){}
        checkId(i+1);
      }, 60);
    });
    // a broken page must not hang the suite. The deadline tracks the DOCUMENT SIZE: a fresh jsdom
    // parsing a 2.75MB report takes longer to reach `load` than a 2.6MB one, and a fixed guard
    // starts reporting "(timeout)" for pages that are merely big -- a test failure that is really
    // a stopwatch failure. Measured: at 4s, EVERY anchor timed out once the all-venues table was
    // added (9 of 9), which is the signature of a stopwatch, not nine broken anchors.
    setTimeout(function(){
      if(settled) return;
      settled=true;
      results.push({id:id, shown:["(timeout)"], act:[], section:null, ok:false});
      try { domN.window.close(); } catch(e){}
      checkId(i+1);
    }, 15000);
  }

  function finish(){
    console.log("\n=== 7. no runtime errors from the jump path ===");
    ck("the jump handlers ran cleanly", runtimeErrors.length===0, runtimeErrors.join(" | "));
    console.log("\n=== RESULT ===");
    if(fails.length){console.log("  "+fails.length+" FAILURE(S):");fails.forEach(function(f){console.log("    - "+f);});process.exit(1);}
    console.log("  all jump-navigation assertions pass");
    process.exit(0);
  }

  checkId(0);

  return;   // checkId owns the rest of the run

  console.log("\n=== 7. no runtime errors from the jump path ===");
  ck("the jump handlers ran cleanly", runtimeErrors.length===0, runtimeErrors.join(" | "));

  console.log("\n=== RESULT ===");
  if(fails.length){console.log("  "+fails.length+" FAILURE(S):");fails.forEach(f=>console.log("    - "+f));process.exit(1);}
  console.log("  all jump-navigation assertions pass");
  process.exit(0);
},900);

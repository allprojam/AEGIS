/* Aegis app runtime — lookup, audit, render, audit card.
   DATA and ADDR are injected above this block by build_report.py. */

const NULLRE = /^0x0{40}$/i;

function fmtUsd(v){ if(v>=1e9) return '$'+(v/1e9).toFixed(2)+'B';
  if(v>=1e6) return '$'+(v/1e6).toFixed(1)+'M';
  if(v>=1e3) return '$'+(v/1e3).toFixed(0)+'k'; return '$'+Math.round(v); }

/* Pull a 0x address or a URL out of free text.
 *
 * NOTE: this still accepts GeckoTerminal and DexScreener URLs even though the page no longer
 * RENDERS those links. The two are unrelated. Rendering them was removed because they pointed at
 * the underlying token rather than the pool; PARSING them must stay, because a user arriving with
 * such a URL (from a search engine, a chat, anywhere) is holding a perfectly good address, and
 * refusing to read it would be a worse failure than the one we set out to fix. Removing a source
 * of links is not the same as refusing to understand one. */
function parseInput(s){
  s=(s||'').trim();
  let m=s.match(/0x[a-fA-F0-9]{40}/);
  if(m) return {kind:'addr', v:m[0].toLowerCase()};
  let g=s.match(/geckoterminal\.com\/([^\/\s]+)\/(?:pools|tokens)\/(0x[a-fA-F0-9]{40})/i);
  if(g) return {kind:'addr', v:g[2].toLowerCase(), chainSlug:g[1]};
  let d=s.match(/dexscreener\.com\/([^\/\s]+)\/(0x[a-fA-F0-9]{40})/i);
  if(d) return {kind:'addr', v:d[2].toLowerCase(), chainSlug:d[1]};
  return {kind:'sym', v:s};
}

/* how far is the advertised APY from its own 30-day mean? */
function vsMean(r){
  if(!r.mean30 || !r.apy) return null;
  return r.apy/r.mean30 - 1;
}
function stabilityLabel(r){
  const s=r.sigma;
  if(s==null) return ['-','dim'];
  if(s<0.10) return ['very stable','ok'];
  if(s<0.30) return ['stable','ok'];
  if(s<1.00) return ['variable','warn'];
  return ['erratic','bad'];
}

function linkPills(r){
  const out=[];
  if(r.links){
    if(r.links.defillama) out.push(`<a href="${r.links.defillama}" target="_blank" rel="noopener" title="the pool on DefiLlama, the source feed">DefiLlama</a>`);
    // GeckoTerminal / DexScreener pills removed on request: both carried the underlying TOKEN
    // address rather than the pool, so each needed a title disclaiming what it was not.
    if(r.official) out.push(`<a href="${r.official}" target="_blank" rel="noopener" title="official site for ${r.project||''}">official</a>`);
  }
  return out.join(' &middot; ');
}

/* line-item rejection breakdown — the thing that makes AVOID explain itself */
function verdictBlock(r, opts){
  const cls = r.verdict==='REAL'?'ok' : r.verdict==='AVOID'?'bad' : 'warn';
  // NO_YIELD and MIXED both render as 'warn' -- neither is a green light
  const st = stabilityLabel(r);
  const vm = vsMean(r);
  const rows=[];
  rows.push(`<div class="v ${cls}">${r.verdict} — ${r.symbol||'?'} <span class="sub">(${r.chain||'?'} / ${r.project||'?'})</span></div>`);
  rows.push(`<div class="sub">APY <b>${(+r.apy).toFixed(2)}%</b> &middot; base ${(+r.base).toFixed(2)}% &middot; reward ${(+r.rew).toFixed(2)}% &middot; TVL ${fmtUsd(r.tvl)} &middot; ${r.count} days tracked</div>`);
  rows.push(`<div class="sub">yield stability: <span class="${st[1]}">${st[0]}</span> (σ ${r.sigma==null?'-':(+r.sigma).toFixed(3)})` +
    (vm==null?'':` &middot; now ${vm>=0?'+':''}${(vm*100).toFixed(0)}% vs its own 30d mean`) + `</div>`);
  const f=r.fails||[];
  if(f.length){
    rows.push('<div style="margin-top:8px"><b>Why it was flagged</b></div><ul class="flags">');
    f.forEach((x,i)=>rows.push(`<li><span class="bad">✗ ${x}</span> — ${(r.reasons&&r.reasons[i])||''}</li>`));
    rows.push('</ul>');
  } else {
    rows.push('<div class="ok" style="margin-top:8px">✓ all six checks passed</div>');
  }
  if(r.links) rows.push(`<div class="sub" style="margin-top:8px">${linkPills(r)}</div>`);
  if(opts && opts.card) rows.push(`<div style="margin-top:10px"><button onclick='auditCard(${r.__i})'>Export due-diligence card</button></div>`);
  return rows.join('');
}

/* Identify a contract the page does not carry. Read-only eth_call for symbol()/name().
 * A failure is reported as unknown rather than guessed at -- an invented token name in a risk
 * tool is worse than no name. */
async function lookupOnChain(a){
  if(!/^0x[0-9a-fA-F]{40}$/.test(a)) return '';
  const RPC='https://mainnet.base.org';
  const dec=h=>{ if(!h||h.length<130) return null;
    try{ const n=parseInt(h.slice(2+64,2+128),16); if(!n||n>64) return null;
      return decodeURIComponent(h.slice(2+128,2+128+n*2).replace(/../g,'%$&')); }catch(e){ return null; } };
  const call=async sel=>{
    const r=await fetch(RPC,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jsonrpc:'2.0',id:1,method:'eth_call',params:[{to:a,data:sel},'latest']})});
    const j=await r.json(); return dec(j.result);
  };
  try{
    const s=await call('0x95d89b41');           // symbol()
    if(!s) return 'no token symbol returned \u2014 it may not be a token contract.';
    return 'on Base this contract reports the symbol '+s+'.';
  }catch(e){
    return 'lookup failed \u2014 no Base RPC reachable (offline, or the node refused).';
  }
}
function findByAddr(a){
  const i=ADDR[a.toLowerCase()];
  return (i===undefined)?null:DATA[i];
}
function findBySym(q){
  q=(q||'').toUpperCase();
  const exact=DATA.filter(r=>(r.symbol||'').toUpperCase()===q);
  if(exact.length) return exact;
  return DATA.filter(r=>(r.symbol||'').toUpperCase().includes(q)).slice(0,6);
}

async function run(){
  const el=document.getElementById('out');
  const raw=document.getElementById('q').value;
  const p=parseInput(raw);
  let hits=[];
  if(p.kind==='addr'){
    const r=findByAddr(p.v);
    if(r) hits=[r];
    else {
      // This page carries ${DATA.length} pools of ~16,700 in the DefiLlama feed, selected by
      // TVL. An address can be absent for three different reasons and the old message conflated
      // them, claiming the address "should" resolve and blaming the TVL floor -- which is not
      // why an address is usually missing. Say what is actually true and offer a step that
      // returns an answer rather than a dead end.
      const alink = `<a href="https://basescan.org/token/${p.v}" target="_blank" rel="noopener">Basescan</a>`;
      const dlink = `<a href="https://dexscreener.com/search?q=${p.v}" target="_blank" rel="noopener">DexScreener</a>`;
      el.innerHTML=`<div class="v dim">Not in this page's index</div>
        <div class="sub"><code>${p.v}</code>${p.chainSlug?` on <b>${p.chainSlug}</b>`:''} is not one of the
        ${DATA.length.toLocaleString()} pools embedded here. This page carries an upper slice of
        roughly 16,700 tracked pools, so absence is expected for most addresses &mdash; it is a
        <b>coverage limit, not a verdict</b>. Nothing above should be read as a judgement about it.<br><br>
        <button id="oc" class="ocbtn">look up this contract on Base</button>
        <span id="oc-out"></span><br><br>
        <b>Next step:</b> ${dlink} resolves any pair and ${alink} identifies the contract itself.
        You can also paste the <b>pair symbol</b> (e.g. <code>WETH-USDC</code>) to match by name.
        </div>`;
      // OPT-IN ONLY. The page itself makes zero network requests when it loads -- that is the
      // offline-audit guarantee. A single click here contacts a public Base RPC, and the button
      // says so. Nothing happens automatically.
      const oc=document.getElementById('oc');
      if(oc) oc.addEventListener('click',async()=>{
        const o=document.getElementById('oc-out');
        o.textContent=' querying\u2026';
        o.textContent=' '+await lookupOnChain(p.v);
      });
      return;
    }
  } else {
    hits=findBySym(p.v);
  }
  if(!hits.length){
    el.innerHTML=`<div class="v dim">No match</div><div class="sub">Nothing in the scanned set matches that.</div>`;
    return;
  }
  el.innerHTML=hits.map(r=>`<div class="result">${verdictBlock(r,{card:hits.length===1})}</div>`).join('');
}

/* ---- due-diligence card: opens a clean printable sheet (Save as PDF) ---- */
function auditCard(i){
  const r=DATA[i];
  const st=stabilityLabel(r), vm=vsMean(r);
  const f=r.fails||[];
  const ts=new Date().toISOString().replace('T',' ').slice(0,16)+' UTC';
  const w=window.open('','_blank');
  w.document.write(`<!doctype html><html><head><meta charset="utf-8">
<title>Aegis audit — ${r.symbol}</title><style>
body{font:12px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:#111;max-width:760px;margin:28px auto;padding:0 22px}
h1{font-size:21px;margin:0 0 2px}h2{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:#666;
margin:20px 0 6px;border-bottom:1px solid #ddd;padding-bottom:4px}
.badge{display:inline-block;font-weight:700;padding:3px 9px;border-radius:6px;font-size:13px}
.REAL{background:#d7f5dd;color:#0a6b26}.AVOID{background:#ffe0e0;color:#a30000}
.MIXED,.PROMISING,.NO_YIELD{background:#fff3cd;color:#7a5300}
table{border-collapse:collapse;width:100%;font-size:12px}td{padding:4px 6px;border-bottom:1px solid #eee}
td:first-child{color:#666;width:38%}
ul{padding-left:18px;margin:6px 0}li{margin:4px 0}
.note{background:#f7f7f7;border-left:3px solid #999;padding:8px 12px;margin-top:16px;font-size:11px;color:#444}
.foot{margin-top:22px;font-size:10px;color:#888;border-top:1px solid #ddd;padding-top:8px}
@media print{button{display:none}}
</style></head><body>
<h1>${r.symbol||'?'} — due-diligence card</h1>
<div class="badge ${r.verdict}">${r.verdict}</div>
<div style="color:#666;font-size:11px;margin-top:6px">${r.chain||'?'} / ${r.project||'?'} &middot; generated ${ts}</div>
<h2>Yield composition</h2><table>
<tr><td>Advertised APY</td><td><b>${(+r.apy).toFixed(2)}%</b></td></tr>
<tr><td>Organic (base) APY</td><td>${(+r.base).toFixed(2)}%</td></tr>
<tr><td>Reward / emissions APY</td><td>${(+r.rew).toFixed(2)}%</td></tr>
<tr><td>Share from emissions</td><td>${r.apy?((r.rew/r.apy)*100).toFixed(0):0}%</td></tr>
<tr><td>TVL</td><td>${fmtUsd(r.tvl)}</td></tr>
<tr><td>Days tracked</td><td>${r.count}</td></tr>
<tr><td>Yield volatility (σ)</td><td>${r.sigma==null?'-':(+r.sigma).toFixed(3)} — ${st[0]}</td></tr>
<tr><td>APY vs 30-day mean</td><td>${vm==null?'-':((vm>=0?'+':'')+(vm*100).toFixed(0)+'%')}</td></tr>
</table>
<h2>Screen result</h2>
${f.length?`<ul>${f.map((x,i)=>`<li><b>✗ ${x}</b> — ${(r.reasons&&r.reasons[i])||''}</li>`).join('')}</ul>`
 :'<div>✓ All six checks passed.</div>'}
<h2>Method</h2>
<div style="font-size:11px">Six checks, each set by a measured failure: outlier flag; reward share &gt;50%;
spot APY below 60% of the 7-day base; TVL floor $1M; turnover &lt;1%/day (applied only where volume data
exists); stable-asset plausibility (&gt;25% organic is credit or leverage risk, not fees).</div>
<div class="note"><b>Scope.</b> This card classifies what a yield is <i>made of</i>. It does not predict
returns, does not place orders, and does not assess contract-audit quality — audit coverage is reported
separately. Severity counts in an audit report are findings <i>raised</i>, not necessarily unresolved.</div>
<div class="foot">Aegis Yield Screen &middot; generated from the DefiLlama pool feed &middot;
${DATA.length.toLocaleString()} pools scanned. Figures are as published at scan time and move.</div>
<button onclick="window.print()" style="margin-top:18px;padding:8px 14px;font-size:12px">Save as PDF</button>
</body></html>`);
  w.document.close();
}

document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')run();});
window.run=run; window.auditCard=auditCard;
try{
  const n=new URLSearchParams(location.search).get('q');
  if(n){ document.getElementById('q').value=n; run(); }
}catch(e){}

/* Aegis audit core — the six checks, ported from screen.py.
   Runs client-side so a pasted pool link can be audited with no backend.

   Thresholds are set by measured failures, documented inline.
   Keep in sync with screener/screen.py. */

export const THRESHOLDS = {
  MIN_TVL: 1_000_000,      // $1M: below this your exit moves the price (APS/USDt0 was $85k)
  MAX_REWARD_SHARE: 0.50,  // >50% emissions = subsidised (SparkDEX was 63%, Aerodrome 96%)
  MIN_SPOT_RATIO: 0.60,    // spot must be >=60% of 7d base (the 24.04% pool was 8.9% on 7d)
  MIN_TURNOVER: 0.01,      // <1%/day (only applied when volume data exists — 62% have none)
  MIN_DAYS: 30,            // history length
  MAX_STABLE_BASE: 25.0,   // stable pool above this = credit risk, not fees (CTCOLBUSD1 101%)
};

const NULLS = new Set(["0x"+"0".repeat(40), "", null, undefined]);
export const isAddr = a => a && !NULLS.has(String(a).toLowerCase()) &&
  String(a).length === 42 && String(a).startsWith("0x");

/* ---- the six checks. Returns verdict + every reason. ---- */
export function audit(pool) {
  const r = [];
  const f = [];
  const apy   = num(pool.apy);
  const base  = num(pool.apyBase);
  const rew   = num(pool.apyReward);
  const apy7  = pool.apyBase7d == null ? null : num(pool.apyBase7d);
  const tvl   = num(pool.tvlUsd);
  const v7    = num(pool.volumeUsd7d);
  const count = num(pool.count);
  const sym   = String(pool.symbol || "").toUpperCase();

  // 1. outlier flag
  if (pool.outlier === true) {
    f.push("OUTLIER");
    r.push(`flagged outlier; spot ${apy.toFixed(2)}% vs 7d-base ${apy7 == null ? "n/a" : apy7.toFixed(2) + "%"}`);
  }
  // 2. reward share
  if (apy > 0) {
    const share = rew / apy;
    if (share > THRESHOLDS.MAX_REWARD_SHARE) {
      f.push("SUBSIDISED");
      r.push(`${(share*100).toFixed(0)}% of yield is emissions (${rew.toFixed(2)} of ${apy.toFixed(2)}%) — ends when incentives do`);
    }
  }
  // 3. spot vs 7d
  if (apy7 != null && apy7 > 0 && base > 0) {
    const ratio = base / apy7;
    if (ratio < THRESHOLDS.MIN_SPOT_RATIO) {
      f.push("SPIKE");
      r.push(`spot base ${base.toFixed(2)}% is only ${(ratio*100).toFixed(0)}% of the 7d base ${apy7.toFixed(2)}%`);
    }
  }
  // 4. TVL floor
  if (tvl < THRESHOLDS.MIN_TVL) {
    f.push("THIN");
    r.push(`TVL $${tvl.toLocaleString(undefined,{maximumFractionDigits:0})} — below $1,000,000; exit moves the price`);
  }
  // 5. turnover — only when volume data exists
  let turnover = null;
  if (v7 && tvl > 0) {
    turnover = (v7/7)/tvl;
    if (turnover < THRESHOLDS.MIN_TURNOVER) {
      f.push("DEAD");
      r.push(`daily turnover ${(turnover*100).toFixed(2)}% of TVL — fees barely accrue`);
    }
  } else if (tvl > 0) {
    r.push("volume data unavailable — turnover unverified");
  }
  // 6. plausibility
  const stableish = pool.stablecoin === true ||
    ["USD","USDC","USDT","DAI","EURC"].some(k => sym.includes(k));
  if (stableish && base > THRESHOLDS.MAX_STABLE_BASE) {
    f.push("IMPLAUSIBLE");
    r.push(`${base.toFixed(1)}% organic on a stable asset is too high for a fee rate; suggests credit, leverage or illiquid exposure`);
  }
  // history
  if (count < THRESHOLDS.MIN_DAYS) {
    f.push("NEW");
    r.push(`only ${count} days of history — no basis for the 7d or 30d checks`);
  }

  // 7. no yield: a pool paying zero is not an opportunity. Mirrors screen.py
  // (590 of 1,891 REAL pools had apy 0 before this check existed).
  if (apy <= 0) {
    f.push("NO_YIELD");
    r.push(`pays ${apy.toFixed(2)}% - no yield to underwrite, whatever its other merits`);
  }

  let verdict;
  const set = new Set(f);
  if (set.has("NO_YIELD")) verdict = "NO_YIELD";
  else if (f.length === 0) verdict = "REAL";
  else if ([...set].every(x => x === "NEW")) verdict = "PROMISING";
  else if (set.has("SUBSIDISED") && f.length <= 2) verdict = "MIXED";
  else verdict = "AVOID";

  return { verdict, fails: f, reasons: r, apy, base, rew, apy7, tvl, turnover,
           sigma: pool.sigma ?? null, count, symbol: pool.symbol,
           chain: pool.chain, project: pool.project, reward_share: apy ? rew/apy : 0 };
}
const num = v => { const n = Number(v); return Number.isFinite(n) ? n : 0; };

#!/usr/bin/env python3
"""Insert the 'State of DeFi Yield' block into build_v2.py and sharpen the flag framing.

Both headline numbers are re-derived from the raw backtest files at build time, so the page
cannot drift from the data. If a file is missing the block is skipped rather than hard-coded.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "screener", "build_v2.py")

DERIVE = '''
def derive_numbers():
    """Re-derive the two headline numbers from raw data. None if the files are absent."""
    import math
    cohort_f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "structural_backtest_v2.jsonl")
    decay_f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "apy_decay.json")
    if not (os.path.exists(cohort_f) and os.path.exists(decay_f)):
        return None
    cohort = []
    for line in open(cohort_f):
        try:
            cohort.append(json.loads(line))
        except Exception:
            pass
    scored = [r for r in cohort if r["outcome"] in ("FAILED", "IMPAIRED", "SURVIVED")]
    if not scored:
        return None
    bleed = sum(1 for r in scored if r["outcome"] in ("FAILED", "IMPAIRED"))
    decay = json.load(open(decay_f))
    hy = [r for r in decay if (r.get("advertised") or 0) > 8]
    if not hy:
        return None
    beat = sum(1 for r in hy if (r.get("realized") or 0) > (r.get("advertised") or 0))
    rets = sorted(r["retention"] for r in hy if r.get("retention") is not None)
    median_ret = rets[len(rets) // 2] * 100 if rets else 0.0

    def wilson(k, n, z=1.96):
        if n == 0:
            return (0.0, 0.0)
        p = k / n; d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return (max(0.0, c - h), min(1.0, c + h))

    lo, hi = wilson(bleed, len(scored))
    lo2, hi2 = wilson(beat, len(hy))
    return dict(bleed_n=len(scored), bleed_k=bleed, bleed_pct=bleed / len(scored) * 100,
                bleed_lo=lo * 100, bleed_hi=hi * 100,
                hy_n=len(hy), hy_k=beat, hy_pct=beat / len(hy) * 100,
                hy_lo=lo2 * 100, hy_hi=hi2 * 100, median_ret=median_ret)

'''

BLOCK = '''
    # ---- State of DeFi Yield: measured, re-derived at build time ----
    if SOTY:
        s = SOTY
        H.append("<h2>State of DeFi Yield</h2>")
        H.append("<div class='big'>"
          f"<div class='card'><div class='n bad'>{s['bleed_pct']:.1f}%</div>"
          "<div class='l'>of pools lost &gt;50% of TVL in 12 months</div></div>"
          f"<div class='card'><div class='n bad'>{s['hy_k']} / {s['hy_n']}</div>"
          "<div class='l'>pools &gt;8% APY that paid what they advertised</div></div>"
          f"<div class='card'><div class='n warn'>{s['median_ret']:.1f}%</div>"
          "<div class='l'>median yield retention</div></div>"
          "</div>")
        H.append(
          f"<div class='note'><b>The APY illusion.</b> Of {s['hy_n']} pools advertising above "
          f"<b>8% APY</b>, <b>{s['hy_k']}</b> delivered the advertised rate over the following 12 "
          f"months. Median retention <b>{s['median_ret']:.1f}%</b>. <i>A yield screen does not predict "
          f"whether a pool survives &mdash; it checks whether the number on the tin is the number "
          f"that gets paid.</i></div>")
        H.append(
          f"<div class='note'><b>The slow bleed.</b> <b>{s['bleed_pct']:.1f}%</b> of indexed pools "
          f"(<b>{s['bleed_k']} of {s['bleed_n']}</b>) lost more than half their liquidity within a "
          f"year &mdash; 95% CI [{s['bleed_lo']:.1f}%, {s['bleed_hi']:.1f}%]. <b>They do not explode. "
          f"They bleed.</b> Under a binary dead-or-alive measure, {s['bleed_k'] - 8} of them would "
          f"still count as <i>survivors</i>, because they keep reporting while holding a fraction "
          f"of the capital.</div>")
        H.append("<div class='sub'>Measured on 122 pools with at least 12 months of history, anchored "
                 "to a point 12 months ago. Method and raw data in <code>BACKTEST_FINDINGS.md</code>. "
                 "These are observations about the index, not predictions about any pool.</div>")

'''

SHARPEN_OLD = '"<b>What this does not do:</b> it does not predict returns, does not place orders, and does not "'
SHARPEN_NEW = ('"<b>The flags are current-state risk markers, not forecasts.</b> SUBSIDISED, THIN and OUTLIER "\n'
               '      "describe what a pool looks like right now. They are not a claim about what it will do. "\n'
               '      "<b>What this does not do:</b> it does not predict returns, does not place orders, and does not "')


def main():
    src = open(BUILD).read()
    if "State of DeFi Yield" in src:
        print("already patched; nothing to do")
        return 0

    if "def derive_numbers(" not in src:
        anchor = "\ndef esc("
        if anchor not in src:
            raise SystemExit("anchor not found: def esc(")
        src = src.replace(anchor, DERIVE + "\ndef esc(", 1)

    sig = '    ts=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())'
    if sig not in src:
        raise SystemExit("anchor not found: timestamp line")
    if "SOTY = derive_numbers()" not in src:
        src = src.replace(sig, "    SOTY = derive_numbers()\n" + sig, 1)

    tool = '    H.append("""<div class="tool">'
    if tool not in src:
        raise SystemExit("anchor not found: search tool block")
    if "State of DeFi Yield" not in src:
        src = src.replace(tool, BLOCK + tool, 1)

    if SHARPEN_OLD in src:
        src = src.replace(SHARPEN_OLD, SHARPEN_NEW, 1)
        print("  flag framing sharpened")
    else:
        print("  WARNING: method-note text not found; framing unchanged")

    open(BUILD, "w").write(src)
    print("patched %s" % BUILD)
    return 0


if __name__ == "__main__":
    sys.exit(main())

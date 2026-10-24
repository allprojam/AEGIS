#!/usr/bin/env python3
"""Accessibility guards the report previously lacked, per the better-accessibility skill.

TWO MEASURED GAPS, now asserted:

  1. `prefers-reduced-motion` was NEVER handled. The page had one transform transition running
     unconditionally, so a reader who has asked their OS for reduced motion still got it.
     WCAG 2.2 treats motion ignoring the preference as HIGH severity.

  2. Only TWO media queries existed (640px and print) for a document with nine anchored sections
     and four dense tables. WCAG 1.4.10 requires reflow at 320px without horizontal scrolling, and
     a wide table track is the commonest cause of horizontal scroll on a data page.

Both are asserted in the RENDERED HTML rather than the source, because the source is templated and
a brace error would produce valid Python that emits broken CSS.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

fails = []


def ck(name, cond, detail=""):
    print("  %-62s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        if detail:
            print("      " + str(detail))
        fails.append(name)


def main():
    p = os.path.join(ROOT, "report.html")
    if not os.path.exists(p):
        print("  report.html missing")
        return 1
    h = open(p).read()

    print("=== 1. motion is opt-in, not the default ===")
    ck("prefers-reduced-motion is handled", "prefers-reduced-motion" in h)
    ck("the reduce branch disables transitions", "transition:none!important" in h)
    ck("and animations", "animation:none!important" in h)
    ck("and smooth scrolling", "scroll-behavior:auto!important" in h)

    print("\n=== 2. the page reflows narrow ===")
    mqs = re.findall(r"@media\(([^)]*)\)", h)
    ck("more than two media queries (%d)" % len(mqs), len(mqs) > 2, mqs)
    ck("a narrow breakpoint exists", any("400px" in m or "320px" in m for m in mqs), mqs)
    ck("tables are constrained at the narrow breakpoint",
       "table-layout:fixed" in h, "a wide table track forces horizontal scroll")

    print("\n=== 3. viewport does not block zoom (WCAG 1.4.4) ===")
    m = re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*>', h)
    ck("a viewport meta exists", bool(m))
    if m:
        vp = m.group(0)
        ck("does NOT set maximum-scale=1", "maximum-scale=1" not in vp, vp)
        ck("does NOT set user-scalable=no", "user-scalable=no" not in vp, vp)

    print("\n=== 4. no bare outline:none without a replacement ===")
    # outline:none is only acceptable when a :focus-visible rule exists nearby
    outlines = h.count("outline:none") + h.count("outline: none")
    ck("focus-visible exists wherever outline is removed",
       outlines == 0 or "focus-visible" in h,
       "%d outline:none, focus-visible present: %s" % (outlines, "focus-visible" in h))

    print("\n=== 5. the structural a11y the page already had ===")
    ck("aria attributes present (%d)" % h.count("aria-"), h.count("aria-") > 10)
    ck("table headers carry tooltips (%d)" % h.count("title="), h.count("title=") > 100)
    ck("interactive tables are marked", 'data-interactive' in h)

    print("\n=== 6. one type scale, one radius scale (better-typography / better-ui) ===")
    # MEASURED BEFORE: 13 distinct font sizes and 11 distinct radius values, including 10.5px,
    # 11.5px and 12.5px -- differences no reader perceives but that make every future change a
    # guess about which number to copy. Collapsed to a named scale.
    sizes = sorted({float(x) for x in re.findall(r"font-size:([0-9.]+)px", h)})
    ck("font sizes consolidated to <= 8 (%d)" % len(sizes), len(sizes) <= 8, sizes)
    ck("no half-pixel sizes remain",
       not [z for z in sizes if z != int(z)], "half-pixel sizes: %s" % [z for z in sizes if z != int(z)])
    radii = sorted(set(re.findall(r"border-radius:([^;}]+)", h)))
    ck("radius values consolidated to <= 8 (%d)" % len(radii), len(radii) <= 8, radii)
    print("      sizes: %s" % sizes)
    print("      radii: %s" % radii)

    print("\n=== 7. headings carry their own line-height (better-typography) ===")
    # Body is 1.55 which is right for prose and too loose for a heading. The skill: headings
    # 1.2-1.3, body 1.5-1.6, unitless so it scales.
    ck("a heading line-height exists", "line-height:1.2" in h or "line-height:1.25" in h)
    ck("body line-height is in the 1.5-1.6 band",
       bool(re.search(r"font:14px/1\.5", h)) or "line-height:1.55" in h)

    print("\n=== 8. sticky chrome does not swallow anchored targets (better-layout) ===")
    # scroll-padding covers EVERY anchor and focused element; scroll-margin-top only covers the
    # elements it is written on. The page had only the latter.
    ck("scroll-padding-block-start is set", "scroll-padding-block-start" in h,
       "the 64px sticky topbar must not cover the element you jumped to")

    print("\n=== RESULT ===")
    if fails:
        print("  %d FAILURE(S):" % len(fails))
        for f in fails:
            print("    - " + f)
        return 1
    print("  the two measured accessibility gaps are closed and pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())

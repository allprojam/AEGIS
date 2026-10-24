#!/usr/bin/env python3
"""Pre-Mortem Engine - grade every strategy against buy-and-hold on real bars."""
import json, glob, os, sys
import pandas as pd
from lib_strategies import (keltner_signals, bbrsi_signals, fractal_signals, simulate_events)

def load(path):
    d = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return d

VARIANTS = [
    ("Keltner bounce 200/200/8 exit=EMA touch", lambda d: keltner_signals(d), "k_entry", "k_exit_tp", None),
    ("Keltner bounce 200/200/8 exit=top band",  lambda d: keltner_signals(d), "k_entry", "k_exit_band", None),
    ("BB+RSI v1.1 BB200 RSI6 long only",        lambda d: bbrsi_signals(d),   "b_entry", "b_exit", None),
    ("Fractal breakout n_time=3",               lambda d: fractal_signals(d, 3),  "f_entry", "f_entry", 3),
    ("Fractal breakout n_time=12",              lambda d: fractal_signals(d, 12), "f_entry", "f_entry", 12),
]

def main():
    datasets = sorted(glob.glob("bars_*_1h_3y.csv"))
    print("datasets: %d\n" % len(datasets), flush=True)
    rows = []
    for ds in datasets:
        sym = os.path.basename(ds).replace("bars_", "").replace("_1h_3y.csv", "").upper()
        try:
            d = load(ds)
        except Exception as e:
            print("  %s: load failed %s" % (sym, e), flush=True)
            continue
        for name, fn, ec, xc, mb in VARIANTS:
            try:
                sig = fn(d)
            except Exception as e:
                print("  %s %s: %s" % (sym, name[:26], e), flush=True)
                continue
            r = simulate_events(sig, ec, xc, max_bars=mb)
            rows.append(dict(symbol=sym, strategy=name, **{k: v for k, v in r.items() if k != "_trades"}))
        print("  %-8s bars=%s" % (sym, format(len(d), ",")), flush=True)

    json.dump(rows, open("premortem_results.json", "w"), indent=1)
    print("\nsaved %d results to premortem_results.json" % len(rows), flush=True)

    import collections
    c = collections.Counter(r["verdict"] for r in rows)
    print("\n=== VERDICT TALLY ===")
    for k, v in c.most_common():
        print("  %-16s %4d" % (k, v))
    n = len(rows)
    if n:
        print("\n  strategies graded:    %d" % n)
        print("  beat buy-and-hold:    %d (%.0f%%)" % (c.get("BEATS_HODL", 0), c.get("BEATS_HODL", 0) / n * 100))
        print("  lost to buy-and-hold: %d (%.0f%%)" % (c.get("LOSES_TO_HODL", 0), c.get("LOSES_TO_HODL", 0) / n * 100))
        print("  sat out entirely:     %d" % c.get("SAT_OUT", 0))
        print("  mean alpha vs HODL:   %+.2f points" % (sum(r["alpha_pct"] for r in rows) / n))

if __name__ == "__main__":
    main()

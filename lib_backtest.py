import json, pandas as pd
from lib_strategies import keltner_signals, bbrsi_signals, fractal_signals, simulate_events
raw = pd.read_csv("bars_cb_5m_30d.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
print(f"bars: {len(raw)}  ({pd.to_datetime(raw.time.iloc[0],unit='s')} -> {pd.to_datetime(raw.time.iloc[-1],unit='s')})\n")
tests = [
 ("Keltner bounce 200/200/8  exit=EMA touch", keltner_signals(raw),          "k_entry", "k_exit_tp",   None),
 ("Keltner bounce 200/200/8  exit=top band",  keltner_signals(raw),          "k_entry", "k_exit_band", None),
 ("BB+RSI v1.1 BB200 RSI6 (long only)",       bbrsi_signals(raw),             "b_entry", "b_exit",      None),
 ("Fractal Breakout n_time=3",                fractal_signals(raw, n_time=3), "f_entry", "f_entry",     3),
 ("Fractal Breakout n_time=12",               fractal_signals(raw, n_time=12),"f_entry", "f_entry",     12),
]
for name, d, ec, xc, mb in tests:
    r = simulate_events(d, ec, xc, max_bars=mb)
    print(f"{name}")
    print(f"   trades={r['trades']:<5} net=${r['net_usd']:<10} win={r['win_rate']} "
          f"avgWin={r['avg_win_bps']}bps avgLoss={r['avg_loss_bps']}bps avgHold={r['avg_bars']}bars dd=${r['max_dd_usd']}")

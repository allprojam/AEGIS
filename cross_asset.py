"""Does the Keltner family transfer to BTC, or was ETH a fluke?
Also: does the BEST ETH config (chosen in-sample) survive on BTC?"""
import itertools, pandas as pd, numpy as np
from lib_strategies import keltner_signals, simulate_events

def run(path, label):
    d0 = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    mid = len(d0)//2
    rows=[]
    for klen, atrlen, dev, ex in itertools.product([100,200,300],[50,100,200],[6,8,10],["ema","band"]):
        xc = "k_exit_tp" if ex=="ema" else "k_exit_band"
        d = keltner_signals(d0, klen=klen, atrlen=atrlen, dev=dev)
        f = simulate_events(d, "k_entry", xc)
        h1 = simulate_events(keltner_signals(d0.iloc[:mid].reset_index(drop=True),klen,atrlen,dev), "k_entry", xc)
        h2 = simulate_events(keltner_signals(d0.iloc[mid:].reset_index(drop=True),klen,atrlen,dev), "k_entry", xc)
        rows.append({"klen":klen,"atrlen":atrlen,"dev":dev,"exit":ex,"n":f["trades"],"net":f["net_usd"],
                     "win":f["win_rate"],"H1":h1["net_usd"],"H2":h2["net_usd"],
                     "pos": f["net_usd"]>0, "both": (h1["net_usd"]>0 and h2["net_usd"]>0)})
    s=pd.DataFrame(rows)
    bh = 100*(d0.close.iloc[-1]/d0.close.iloc[0]-1)
    print(f"\n===== {label}  ({len(d0)} bars, buy&hold {bh:+.1f}%) =====")
    print(f"cells {len(s)}  positive {(s.pos).sum()} ({(s.pos).mean():.0%})  "
          f"both-halves {(s.both).sum()} ({(s.both).mean():.0%})  median net {s.net.median():.2f}")
    print("top 5:"); print(s.sort_values('net',ascending=False).head(5)[["klen","atrlen","dev","exit","n","net","win","H1","H2"]].to_string(index=False))
    return s

eth = run("bars_cb_5m_180d.csv", "ETH")
btc = run("bars_btc_5m_180d.csv", "BTC")

# out-of-sample: pick best on ETH, see how that SAME config does on BTC
best = eth.sort_values("net", ascending=False).iloc[0]
m = btc[(btc.klen==best.klen)&(btc.atrlen==best.atrlen)&(btc.dev==best.dev)&(btc.exit==best["exit"])]
print(f"\n===== OUT-OF-SAMPLE: best ETH config applied to BTC =====")
print(f"config: klen={best.klen} atrlen={best.atrlen} dev={best.dev} exit={best['exit']}")
print(f"  ETH net ${best.net:+.2f} ({best.n:.0f} trades, win {best.win:.2f}, H1 {best.H1:+.2f} / H2 {best.H2:+.2f})")
if len(m):
    r=m.iloc[0]
    print(f"  BTC net ${r.net:+.2f} ({r.n:.0f} trades, win {r.win:.2f}, H2 {r.H2:+.2f})  ->  {'TRANSFERS' if r.net>0 else 'FAILS on BTC'}")
# overlap of winners
ethw=set(zip(eth[eth.pos][['klen','atrlen','dev','exit']].values.tolist()))
btcw=set(zip(btc[btc.pos][['klen','atrlen','dev','exit']].values.tolist()))
print(f"\nconfigs profitable on BOTH assets: {len(ethw & btcw)} / {len(ethw|btcw)}")

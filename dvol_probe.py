"""Feasibility probe: is free options data available to test the variance risk premium?
Deribit publishes DVOL (30-day implied vol index) with a PUBLIC api -- no key, no cost."""
import json, urllib.request, time
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())

now = int(time.time()*1000)
start = int(time.mktime(time.strptime("2020-01-01","%Y-%m-%d"))*1000)

print("=== DVOL (implied vol index) ===")
try:
    u = (f"https://www.deribit.com/api/v2/public/get_volatility_index_data"
         f"?currency=BTC&start_timestamp={start}&end_timestamp={now}&resolution=1D")
    j = get(u)
    d = j.get("result",{}).get("data",[])
    print(f"BTC DVOL: {len(d)} daily points")
    if d:
        import datetime as dt
        f0=dt.datetime.utcfromtimestamp(d[0][0]/1000).date(); l0=dt.datetime.utcfromtimestamp(d[-1][0]/1000).date()
        print(f"  range {f0} -> {l0}   first close {d[0][4]:.2f}  last close {d[-1][4]:.2f}")
except Exception as e:
    print("  FAIL", str(e)[:120])

print("\n=== index price history (for realized vol) ===")
try:
    u = (f"https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
         f"?instrument_name=BTC-PERPETUAL&start_timestamp={start}&end_timestamp={now}&resolution=1D")
    j = get(u)
    r = j.get("result",{})
    print(f"BTC-PERPETUAL daily: {len(r.get('close',[]))} bars, status={r.get('status')}")
except Exception as e:
    print("  FAIL", str(e)[:120])

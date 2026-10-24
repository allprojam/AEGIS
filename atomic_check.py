import json, sys, datetime as dt
import pandas as pd
sys.path.insert(0,"/root/agency_bot/workspace")
import tv_client as tv
from pine_port import compute

JS = ("(function(){var b=window.TradingViewApi._activeChartWidgetWV.value()"
      "._chartWidget.model().mainSeries().bars();var n=b.size();var out=[];"
      "for(var i=0;i<n;i++){var v=b.valueAt(i);out.push(v[0]+','+v[1]+','+v[2]+','+v[3]+','+v[4])}"
      "return n+'#'+out.join('|')})()")

# 1) bars, 2) study values, 3) bars again - if bars changed between 1 and 3, a new bar formed
b1 = json.loads(tv.call("ui_evaluate", {"expression": JS}))["result"].split("#",1)[1]
vals = json.loads(tv.call("data_get_study_values", {}))
b2 = json.loads(tv.call("ui_evaluate", {"expression": JS}))["result"].split("#",1)[1]
print("bars stable across the read:", b1 == b2)

rows = [r.split(",") for r in b2.split("|")]
df = pd.DataFrame(rows, columns=["time","open","high","low","close"]).astype(float)
d = compute(df); L = d.iloc[-1]

def g(name, key):
    for s in vals.get("studies", []):
        if name in s.get("name",""):
            v = (s.get("values") or {}).get(key)
            return float(str(v).replace(",","").replace("\u2212","-")) if v is not None else None
    return None

ch = {"HMA1": g("Hull","HMA1"), "HMA2": g("Hull","HMA2"), "HMA3": g("Hull","HMA3"),
      "line": g("Bollinguer","Linea Macd BB\""), "up": g("Bollinguer","Banda Superior\""),
      "lo": g("Bollinguer","Banda Inferior\"")}
print(f"{'':10} {'chart':>12} {'port':>12} {'diff':>10}")
for k, pk in (("HMA1","hma1"),("HMA2","hma2"),("HMA3","hma3")):
    c, p = ch[k], L[pk]
    print(f"{k:10} {c:12.3f} {p:12.3f} {p-c:+10.3f}")
for k, pk in (("line","bbmacd"),("up","banda_supe"),("lo","banda_inf")):
    c, p = ch[k], L[pk]
    print(f"MACD-BB {k:4} {c:12.3f} {p:12.3f} {p-c:+10.3f}")
print("last bar:", dict(df.iloc[-1][["time","open","close"]]))

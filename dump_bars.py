import csv, json, sys
sys.path.insert(0,"/root/agency_bot/workspace")
import tv_client as tv
JS = ("(function(){var b=window.TradingViewApi._activeChartWidgetWV.value()"
      "._chartWidget.model().mainSeries().bars();var n=b.size();var out=[];"
      "for(var i=0;i<n;i++){var v=b.valueAt(i);out.push(v[0]+','+v[1]+','+v[2]+','+v[3]+','+v[4]+','+v[5])}"
      "return n+'#'+out.join('|')})()")
res = json.loads(tv.call("ui_evaluate", {"expression": JS}))
s = res["result"]
n, body = s.split("#", 1)
rows = [r.split(",") for r in body.split("|")]
print("bars from TV page:", n, "parsed:", len(rows))
with open("bars_tv.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["time","open","high","low","close","volume"]); w.writerows(rows)
print("first:", rows[0]); print("last :", rows[-1])

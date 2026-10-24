import json, sys, datetime as dt
sys.path.insert(0,"/root/agency_bot/workspace")
import tv_client as tv
expr = ("(function(){var c=window.TradingViewApi._activeChartWidgetWV.value();"
        "var b=c._chartWidget.model().mainSeries().bars();"
        "var n=b.size(); var li=b.lastIndex(); var out={size:n,lastIndex:String(li),last_time:String(b.valueAt(li)[0]),"
        "last_open:b.valueAt(li)[1],last_close:b.valueAt(li)[4],realLast:String(b.lastIndex())};"
        "out.t1=String(b.valueAt(li-1)[0]); out.o1=b.valueAt(li-1)[1];"
        "out.t2=String(b.valueAt(li-2)[0]); out.o2=b.valueAt(li-2)[1];"
        "return JSON.stringify(out)})()")
r = json.loads(tv.call("ui_evaluate", {"expression": expr}))
print("chart:", json.dumps(r.get("result"), indent=2))
print()
rowsc = list(__import__('csv').reader(open("bars_ethusd_5m.csv")))
hdr, rows = rowsc[0], rowsc[1:]
print("csv rows:", len(rows))
for r_ in rows[-4:]:
    print("  ", r_[0], dt.datetime.utcfromtimestamp(int(r_[0])).isoformat(), "open", r_[1], "close", r_[4])

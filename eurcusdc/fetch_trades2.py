import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0xE846373C1a92B167b4E9cd5d8E4d6B1Db9E90EC7"
rows=[]; cursor=None
for page in range(40):
    u=f"https://api.geckoterminal.com/api/v2/networks/base/pools/{P}/trades?trade_volume_in_usd_greater_than=0"
    if cursor: u+=f"&before_timestamp={cursor}"
    for attempt in range(5):
        try:
            j=g(u); break
        except Exception as e:
            wait=8*(attempt+1)
            print(f"  page{page} retry{attempt} ({str(e)[:30]}) sleep {wait}s",flush=True)
            time.sleep(wait)
    else:
        print(f"page{page} giving up",flush=True); break
    d=j.get("data",[])
    if not d: break
    for t in d:
        a=t["attributes"]
        rows.append((a.get("block_timestamp"),a.get("kind"),a.get("volume_in_usd"),
                     a.get("tx_hash"),a.get("tx_from_address")))
    cursor=a.get("block_timestamp")
    print(f"page{page}: +{len(d)} total {len(rows)}",flush=True)
    time.sleep(6)
with open("trades.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["ts","kind","vol_usd","tx","from_addr"])
    w.writerows(rows)
print("DONE",len(rows),flush=True)

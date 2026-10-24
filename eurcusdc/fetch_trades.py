import json,urllib.request,time,csv,sys
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0xE846373C1a92B167b4E9cd5d8E4d6B1Db9E90EC7"
rows=[]
cursor=None
for page in range(30):
    u=f"https://api.geckoterminal.com/api/v2/networks/base/pools/{P}/trades"
    if cursor: u+=f"?trade_volume_in_usd_greater_than=0&before_timestamp={cursor}"
    else: u+="?trade_volume_in_usd_greater_than=0"
    try:
        j=g(u)
    except Exception as e:
        print(f"page{page} FAIL {e}",flush=True); break
    d=j.get("data",[])
    if not d: break
    for t in d:
        a=t["attributes"]
        rows.append((a.get("block_timestamp"),a.get("kind"),a.get("volume_in_usd"),
                     a.get("from_token_amount"),a.get("to_token_amount"),
                     a.get("tx_hash"),a.get("tx_from_address")))
    cursor=a.get("block_timestamp")
    print(f"page{page}: +{len(d)} (total {len(rows)})",flush=True)
    time.sleep(1.2)
with open("trades.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["ts","kind","vol_usd","amt_from","amt_to","tx","from_addr"])
    w.writerows(rows)
print("DONE",len(rows),flush=True)

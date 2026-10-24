import json,urllib.request,time,csv
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
P="0xf13203ddbf2c9816a79b656a1a952521702715d92fea465b84ae2ed6e94a7f22"
rows=[]; cursor=None
for page in range(12):
    u=f"https://api.geckoterminal.com/api/v2/networks/base/pools/{P}/trades?trade_volume_in_usd_greater_than=0"
    if cursor: u+=f"&before_timestamp={cursor}"
    for att in range(5):
        try: j=g(u); break
        except Exception as e:
            print(f"  p{page} att{att} {str(e)[:35]}",flush=True); time.sleep(10*(att+1))
    else: 
        print(f"p{page} giveup",flush=True); break
    d=j.get("data",[])
    if not d: break
    for t in d:
        a=t["attributes"]
        rows.append((a.get("block_timestamp"),a.get("kind"),a.get("volume_in_usd"),
                     a.get("from_token_amount"),a.get("to_token_amount"),
                     a.get("tx_hash"),a.get("tx_from_address")))
    cursor=a.get("block_timestamp")
    print(f"p{page} +{len(d)} tot {len(rows)}",flush=True)
    time.sleep(7)
with open("v4_trades.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["ts","kind","vol_usd","amt_from","amt_to","tx","from_addr"]); w.writerows(rows)
print("DONE",len(rows),flush=True)

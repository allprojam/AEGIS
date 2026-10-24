import urllib.request
FRED={"USD":"DGS3MO","JPY":"IR3TIB01JPM156N"}
for cur,fid in FRED.items():
    for attempt in range(3):
        try:
            req=urllib.request.Request(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}",
                                       headers={"User-Agent":"Mozilla/5.0"})
            body=urllib.request.urlopen(req,timeout=180).read().decode()
            open(f"fx/rate_{cur}.csv","w").write(body)
            print(f"OK {cur} {fid} {len(body)} bytes", flush=True); break
        except Exception as e:
            print(f"try{attempt} FAIL {cur} {e}", flush=True)
print("DONE", flush=True)

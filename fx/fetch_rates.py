import urllib.request
FRED={"USD":"DGS3MO","JPY":"IR3TIB01JPM156N","EUR":"IR3TIB01EZM156N","GBP":"IR3TIB01GBM156N",
      "AUD":"IR3TIB01AUM156N","CAD":"IR3TIB01CAM156N","CHF":"IR3TIB01CHM156N","NZD":"IR3TIB01NZM156N"}
for cur,fid in FRED.items():
    try:
        req=urllib.request.Request(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}",
                                   headers={"User-Agent":"Mozilla/5.0"})
        body=urllib.request.urlopen(req,timeout=25).read().decode()
        open(f"fx/rate_{cur}.csv","w").write(body)
        print(f"OK {cur} {fid} {len(body)} bytes", flush=True)
    except Exception as e:
        print(f"FAIL {cur} {e}", flush=True)
print("DONE", flush=True)

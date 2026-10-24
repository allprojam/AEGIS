import json, sys
sys.path.insert(0,"/root/agency_bot/workspace")
import tv_client as tv
p = sys.argv[1] if len(sys.argv)>1 else "pine/hma_bsm_strategy.pine"
src = open(p).read()
print(tv.call("pine_check", {"source": src}))

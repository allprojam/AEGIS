import json,urllib.request,time,sys
sys.path.insert(0,"/root/agency_bot/workspace")
from web3 import Web3
W3=Web3()
RPC="https://base.gateway.tenderly.co"
def one(m,p):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),
        headers={"Content-Type":"application/json"})
    j=json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
    if "error" in j: raise RuntimeError(str(j["error"])[:50])
    return j.get("result","0x")
def call(to,sig,args=(),out="raw"):
    d="0x"+W3.keccak(text=sig)[:4].hex()
    for a in args: d+= (a[2:].rjust(64,"0") if isinstance(a,str) else format(a,'064x'))
    try: h=one("eth_call",[{"to":to,"data":d},"latest"])
    except Exception as e: return f"REVERT"
    if h in ("0x",""): return "empty"
    if out=="addr": return "0x"+h[-40:]
    if out=="str":
        try:
            off=int(h[0:64],16); ln=int(h[off*2:off*2+64],16)
            return bytes.fromhex(h[off*2+64:off*2+64+ln*2]).decode(errors="ignore")
        except Exception: return "?"
    return int(h,16)
A="0x08FB33543aD633db94282df364AD80FEB8D9fc35"
print("=== contract identity ===")
for sig,out in (("name()","str"),("symbol()","str"),("owner()","addr"),("admin()","addr"),
                ("factory()","addr"),("pool()","addr"),("token0()","addr"),("token1()","addr"),
                ("WETH()","addr"),("usdc()","addr"),("manager()","addr"),("positionManager()","addr")):
    print(f"  {sig:<20} {call(A,sig,out=out)}"); time.sleep(0.35)
print("\n=== is it an ERC-721 (v3 position) or a vault? ===")
for sig in ("totalSupply()","balanceOf(address)","MAX_BPS()","fee()","tickLower()","tickUpper()"):
    print(f"  {sig:<22} {call(A,sig,args=(A,) if 'address' in sig else ())}"); time.sleep(0.35)
print("\n=== known selectors in its own history? check for v3 factory ===")
V3FACT="0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
print(f"  Uniswap v3 factory on Base = {V3FACT}")
# does it implement balanceOf on a known v3 NFT manager?
PM="0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
for sig in ("balanceOf(address)","ownerOf(uint256)"):
    print(f"  V3 NFPM.{sig:<18} {call(PM,sig,args=(A,) if 'address' in sig else (1,))}")

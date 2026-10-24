import json,urllib.request,time,sys
RPC="https://base.gateway.tenderly.co"
A="0x08FB33543aD633db94282df364AD80FEB8D9fc35"
WETH="0x4200000000000000000000000000000000000006"
USDC="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
def rpc(p):
    r=urllib.request.Request(RPC,data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=30).read().decode())
def one(method,params):
    return rpc([{"jsonrpc":"2.0","id":1,"method":method,"params":params}])[0].get("result")
from web3 import Web3
W3=Web3()
code=one("eth_getCode",[A,"latest"])
nonce=int(one("eth_getTransactionCount",[A,"latest"]),16)
bal=int(one("eth_getBalance",[A,"latest"]),16)
print(f"=== {A} ===")
print(f"  contract?  {'YES' if len(code)>10 else 'NO (EOA)'}   codelen {len(code)}")
print(f"  nonce      {nonce:,}")
print(f"  ETH        {bal/1e18:,.4f}")
def erc20(tok,dec,sym):
    d="0x"+W3.keccak(text="balanceOf(address)")[:4].hex()+A[2:].rjust(64,"0")
    h=one("eth_call",[{"to":tok,"data":d},"latest"])
    print(f"  {sym:<6}     {int(h,16)/10**dec:,.6f}")
erc20(WETH,18,"WETH"); time.sleep(0.3)
erc20(USDC,6,"USDC")

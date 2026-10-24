"""Decode Uniswap v4 Pool.Slot0 with correct bit positions, and cross-validate."""
import json, urllib.request, math
RPC="https://base.gateway.tenderly.co"
def call(m,p):
    r=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=20).read().decode())
PM="0x498581fF718922c3f8e6a244956aF099B2652b2b"
PID=bytes.fromhex("f13203ddbf2c9816a79b656a1a952521702715d92fea465b84ae2ed6e94a7f22")

def keccak_slot(pid_bytes, slot):
    from web3 import Web3
    return Web3().keccak(pid_bytes + slot.to_bytes(32,"big")).hex()

print("=== POOLS_SLOT scan ===")
vals={}
for s in range(0,12):
    k=keccak_slot(PID,s)
    try:
        r=call("eth_getStorageAt",[PM,"0x"+k,"latest"])
        v=r.get("result","0x")
        if v and v!="0x"+"0"*64:
            vals[s]=v
            print(f"  slot {s}: {v}")
    except Exception as e: pass

if 6 in vals:
    V=int(vals[6],16)
    print(f"\n=== DECODING slot0 at POOLS_SLOT=6 ===")
    sqrt = V & (2**160-1)
    tick = (V >> 160) & 0xFFFFFF
    proto= (V >> 184) & 0xFFFFFF
    lpfee= (V >> 208) & 0xFFFFFF
    if tick >= 2**23: tick -= 2**24
    print(f"  sqrtPriceX96 = {sqrt}")
    print(f"  tick         = {tick}")
    print(f"  protocolFee  = {proto}  (lower 12 bits {proto & 0xFFF}, upper 12 bits {proto>>12})")
    print(f"  lpFee        = {lpfee} hundredths-of-a-bip = {lpfee/10000:.6f}% = {lpfee/100:.4f} bp")
    # cross-validate: price from sqrtPriceX96 vs price from tick
    p_sqrt = (sqrt/2**96)**2
    p_tick = 1.0001**tick
    print(f"\n  CROSS-VALIDATION (must agree, or the decode is wrong)")
    print(f"    price from sqrtPriceX96 = {p_sqrt:.10f}")
    print(f"    price from tick 1.0001^{tick} = {p_tick:.10f}")
    print(f"    ratio {p_sqrt/p_tick:.8f}  -> {'CONSISTENT' if abs(p_sqrt/p_tick-1)<0.001 else 'INCONSISTENT: decode wrong'}")
    print(f"\n  (raw price is token1/token0; USDC=token0, USDT=token1, both 6dp -> price = USDT/USDC)")
else:
    print("  slot 6 not populated")

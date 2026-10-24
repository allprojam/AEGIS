"""Recover the Uniswap v4 PoolKey by brute-forcing fee/tickSpacing/hooks against the known poolId."""
from web3 import Web3
import itertools, json

W3 = Web3()
TARGET = "f13203ddbf2c9816a79b656a1a952521702715d92fea465b84ae2ed6e94a7f22".lower()
C0 = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"   # USDC
C1 = "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2"   # USDT

def enc(addr):  return bytes.fromhex(addr[2:].rjust(64, "0"))
def enc_u24(v): return v.to_bytes(32, "big")
def enc_i24(v): return (v & (2**256-1)).to_bytes(32, "big")

def pool_id(c0, c1, fee, spacing, hooks):
    raw = enc(c0) + enc(c1) + enc_u24(fee) + enc_i24(spacing) + enc(hooks)
    return W3.keccak(raw).hex()[2:]

HOOKS = ["0x" + "0"*40,
         "0x0000000000000000000000000000000000000000"]
# known Base v4 hook addresses are unknown; brute force with null hooks first
STATIC_FEES = [100,200,300,400,500,600,700,800,900,1000,1500,2000,2500,3000,4000,5000,10000,50000,100000,0]
DYN_FEES = [0x800000, 0x800000|100, 0x800000|500, 0x800000|3000]
SPACINGS = [1,2,5,10,15,20,25,30,50,60,100,200,500,1000]

found=[]
for fee in STATIC_FEES+DYN_FEES:
    for sp in SPACINGS:
        for hk in HOOKS:
            if pool_id(C0,C1,fee,sp,hk)==TARGET:
                found.append((fee,sp,hk))
print("target poolId:", TARGET)
if found:
    for fee,sp,hk in found:
        dyn = "DYNAMIC (bit 23 set)" if fee & 0x800000 else f"STATIC = {fee/10000:.4f}% ({fee} hundredths-of-bp)"
        print(f"  MATCH -> fee={fee}  tickSpacing={sp}  hooks={hk}")
        print(f"           {dyn}")
else:
    print("  no match with null hooks across static+dynamic fee candidates")
    print("  -> the pool likely has a NON-ZERO hook address; hook address must be known to recover the key")

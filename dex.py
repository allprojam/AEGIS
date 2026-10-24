"""Base DEX routing: real executable quotes from Aerodrome and Uniswap v3.

No private keys, no signing. Read-only quoting used by the paper-trade engine.
"""
from __future__ import annotations
import itertools, json, time
from dataclasses import dataclass
from web3 import Web3

RPCS = [
    "https://base-rpc.publicnode.com",
    "https://base.drpc.org",
    "https://1rpc.io/base",
    "https://mainnet.base.org",
]
_rpc_cycle = itertools.cycle(RPCS)

WETH = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bda02913")
AERO_FACTORY = Web3.to_checksum_address("0x420DD381b31aEf6683db6B902084cB0FFECe40Da")
AERO_ROUTER = Web3.to_checksum_address("0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43")
UNI_QUOTER = Web3.to_checksum_address("0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a")
FEE_TIERS = [100, 500, 3000, 10000]

_AERO_ROUTER_ABI = [{
    "inputs": [{"name": "amountIn", "type": "uint256"},
               {"components": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"},
                               {"name": "stable", "type": "bool"}, {"name": "factory", "type": "address"}],
                "name": "routes", "type": "tuple[]"}],
    "name": "getAmountsOut", "outputs": [{"name": "amounts", "type": "uint256[]"}],
    "stateMutability": "view", "type": "function"}]

_QUOTER_ABI = [{
    "inputs": [{"components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"},
                               {"name": "amountIn", "type": "uint256"}, {"name": "fee", "type": "uint24"},
                               {"name": "sqrtPriceLimitX96", "type": "uint160"}],
                "name": "params", "type": "tuple"}],
    "name": "quoteExactInputSingle",
    "outputs": [{"name": "amountOut", "type": "uint256"}, {"name": "sqrtPriceX96After", "type": "uint160"},
                {"name": "initializedTicksCrossed", "type": "uint32"}, {"name": "gasEstimate", "type": "uint256"}],
    "stateMutability": "nonpayable", "type": "function"}]

_ERC20_ABI = [
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "a", "type": "address"}], "name": "balanceOf",
     "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]


def next_rpc() -> str:
    return next(_rpc_cycle)


def w3_for(url: str | None = None) -> Web3:
    return Web3(Web3.HTTPProvider(url or next_rpc(), request_kwargs={"timeout": 20}))


@dataclass
class Quote:
    venue: str
    amount_in: float
    amount_out: float
    fee_bps: float
    route: str

    @property
    def price(self) -> float:
        return self.amount_out / self.amount_in

    @property
    def effective_cost_pct(self) -> float:
        return self.fee_bps / 100.0


def aerodrome_quote(w3: Web3, amount_in_eth: float, stable: bool = False) -> Quote | None:
    """Exact-input quote via Aerodrome router getAmountsOut."""
    try:
        r = w3.eth.contract(address=AERO_ROUTER, abi=_AERO_ROUTER_ABI)
        amounts = r.functions.getAmountsOut(
            int(amount_in_eth * 10**18), [(WETH, USDC, stable, AERO_FACTORY)]
        ).call()
        out = amounts[1] / 10**6
        # Aerodrome volatile/stableswap fee is 30bps by default on this pool class
        return Quote("aerodrome", amount_in_eth, out, 30.0,
                     f"WETH/USDC {'stable' if stable else 'volatile'} pool 0xcDAC0d6c")
    except Exception:
        return None


def uniswap_v3_quotes(w3: Web3, amount_in_eth: float,
                      tiers: list[int] | None = None) -> list[Quote]:
    """Quote every fee tier; QuoterV2 is a state-override call so use eth_call."""
    out: list[Quote] = []
    q = w3.eth.contract(address=UNI_QUOTER, abi=_QUOTER_ABI)
    for fee in (tiers or FEE_TIERS):
        try:
            res = q.functions.quoteExactInputSingle(
                (WETH, USDC, int(amount_in_eth * 10**18), fee, 0)
            ).call()
            amt = res[0] if isinstance(res, (list, tuple)) else res
            out.append(Quote("uniswap_v3", amount_in_eth, amt / 10**6, fee / 100.0,
                             f"WETH/USDC fee={fee/1_000_000:.2%}"))
        except Exception:
            continue
    return out


def best_quote(amount_in_eth: float = 1.0) -> dict:
    """Best executable route across venues, plus the full ladder."""
    w3 = w3_for()
    ladder: list[Quote] = []
    for stable in (False, True):
        q = aerodrome_quote(w3, amount_in_eth, stable)
        if q:
            ladder.append(q)
    ladder.extend(uniswap_v3_quotes(w3, amount_in_eth))
    if not ladder:
        return {"ok": False, "error": "no venue returned a quote"}
    ladder.sort(key=lambda q: q.amount_out, reverse=True)
    best = ladder[0]
    return {
        "ok": True,
        "block": w3.eth.block_number,
        "rpc": w3.provider.endpoint_uri,
        "amount_in_eth": amount_in_eth,
        "best": {"venue": best.venue, "route": best.route, "price": best.price,
                 "amount_out_usdc": best.amount_out, "fee_bps": best.fee_bps},
        "ladder": [{"venue": q.venue, "route": q.route, "price": q.price,
                    "amount_out_usdc": q.amount_out, "fee_bps": q.fee_bps} for q in ladder],
        "spread_best_worst_pct": (ladder[0].amount_out / ladder[-1].amount_out - 1) * 100 if len(ladder) > 1 else 0.0,
    }


if __name__ == "__main__":
    import sys
    amt = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    print(json.dumps(best_quote(amt), indent=2))

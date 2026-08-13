"""Shared on-chain balance lookups (TON / EVM / Solana) via raw RPC.

Used by both the `/api/wallet/balance` endpoint and the Telegram bot so a single
network only needs one implementation. Deliberately avoids the `solana`/`solana-py`
package (which is not installed on some hosts).
"""
import logging

logger = logging.getLogger(__name__)


async def chain_balance(network: str, address: str) -> dict:
    """Return `{status, network, address, symbol, balance, usdEstimate}` for a wallet."""
    import httpx

    network = network.lower()
    base = 0.0
    symbol = ""
    usd = None

    async with httpx.AsyncClient(timeout=8) as client:
        if network == "ton":
            symbol = "TON"
            try:
                r = await client.get(
                    "https://toncenter.com/api/v2/getAddressInformation",
                    params={"address": address},
                )
                info = r.json().get("result", {}) or {}
                base = float(int(info.get("balance", 0) or 0)) / 10**9
            except Exception as e:
                logger.warning("TON balance failed %s: %s", address, e)
                return {"status": "error", "network": network, "address": address, "balance": None}

        elif network in ("evm", "ethereum", "eth", "bsc", "bnb", "polygon"):
            rpc_by_chain = {
                "eth": "https://cloudflare-eth.com",
                "ethereum": "https://cloudflare-eth.com",
                "evm": "https://cloudflare-eth.com",
                "bsc": "https://bsc-dataseed.binance.org",
                "bnb": "https://bsc-dataseed.binance.org",
                "polygon": "https://polygon-rpc.com",
            }
            rpc = rpc_by_chain.get(network, "https://cloudflare-eth.com")
            symbol = "ETH"
            try:
                r = await client.post(
                    rpc,
                    json={"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [address, "latest"]},
                )
                wei = r.json().get("result", "0x0")
                base = int(wei, 16) / 10**18
            except Exception as e:
                logger.warning("EVM balance failed %s (%s): %s", address, network, e)
                return {"status": "error", "network": network, "address": address, "balance": None}

        elif network in ("solana", "sol"):
            symbol = "SOL"
            try:
                r = await client.post(
                    "https://api.mainnet-beta.solana.com",
                    json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]},
                )
                result = r.json().get("result", {}) or {}
                base = float(result.get("value", 0) or 0) / 10**9
                symbol = "SOL"
            except Exception as e:
                logger.warning("Solana balance failed %s: %s", address, e)
                return {"status": "error", "network": network, "address": address, "balance": None}
        else:
            return {"status": "error", "network": network, "address": address, "balance": None}

    # Optional USD estimate via Binance.
    usd_symbol = {"TON": "TONUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}.get(symbol)
    if usd_symbol:
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                pr = await c.get(
                    "https://api.binance.com/api/v3/ticker/price",
                    params={"symbol": usd_symbol},
                )
                price = float(pr.json().get("price", 0) or 0)
                usd = round(base * price, 2)
        except Exception:
            usd = None

    return {
        "status": "success",
        "network": network,
        "address": address,
        "symbol": symbol,
        "balance": round(base, 8),
        "usdEstimate": usd,
    }


def map_wallet_network(network: str) -> str:
    """Normalize a user-facing network string to a chain_balance() network key."""
    n = (network or "").lower()
    if network == "TON":
        return "ton"
    if n in ("solana", "sol"):
        return "solana"
    if any(x in n for x in ("bsc", "bnb", "smart chain")):
        return "bsc"
    if "polygon" in n:
        return "polygon"
    return "evm"
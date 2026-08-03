"""
Jupiter API Client for Solana DEX Trading
==========================================
Provides quote, swap, and price functionality via Jupiter's v6 API.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Jupiter API endpoints
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
JUPITER_PRICE_URL = "https://price.jup.ag/v4/price"
JUPITER_TOKEN_LIST_URL = "https://tokens.jup.ag/tokens?tags=verified"

# Solana token addresses
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


@dataclass
class SwapQuote:
    """Quote from Jupiter for a swap."""
    input_mint: str
    output_mint: str
    input_amount: int  # in lamports or smallest unit
    output_amount: int  # in smallest unit
    price_pure: float  # raw price
    price_impact_pct: float
    route_plan: List[Dict]
    context_slot: int
    background: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "input_mint": self.input_mint,
            "output_mint": self.output_mint,
            "input_amount": self.input_amount,
            "output_amount": self.output_amount,
            "price_pure": self.price_pure,
            "price_impact_pct": self.price_impact_pct,
            "route_plan": self.route_plan,
            "context_slot": self.context_slot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@dataclass
class TokenPrice:
    """Price data for a token."""
    mint: str
    price: float
    id: str  # token symbol or mint
    symbol: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "mint": self.mint,
            "price": self.price,
            "symbol": self.symbol or self.mint[:8],
            "confidence": self.confidence,
        }


class JupiterClient:
    """Client for Jupiter v6 API."""

    def __init__(self, wsol_amount: float = 0.1):
        self.base_url = "https://quote-api.jup.ag/v6"
        self.http_client = httpx.AsyncClient(
            base_url="https://quote-api.jup.ag",
            timeout=30.0,
            headers={"Content-Type": "application/json"}
        )
        # Default WSOL amount for USD pricing
        self._wsol_amount = wsol_amount

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,  # in smallest unit (lamports for SOL)
        slippage_bps: int = 100,  # 1% slippage
        as_legacy_tx: bool = False,
    ) -> Optional[SwapQuote]:
        """Get a swap quote from Jupiter."""
        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": slippage_bps,
                "onlyDirectRoutes": "false",
                "asLegacyTx": str(as_legacy_tx).lower(),
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("/v6/quote", params=params)
                resp.raise_for_status()
                data = resp.json()

            return SwapQuote(
                input_mint=data.get("inputMint", input_mint),
                output_mint=data.get("outputMint", output_mint),
                input_amount=int(data.get("inputAmount", amount)),
                output_amount=int(data.get("outputAmount", 0)),
                price_pure=float(data.get("pricePure", 0)),
                price_impact_pct=float(data.get("priceImpactPct", 0)),
                route_plan=data.get("routePlan", []),
                context_slot=int(data.get("contextSlot", 0)),
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Jupiter quote failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Jupiter quote error: {e}")
            return None

    async def get_swap_transaction(
        self,
        quote_data: str,  # JSON string of quote
        publicKey: str,  # wallet public key
        wrapAndUnwrapSol: bool = True,
        prioritizationFeeLamports: Optional[int] = None,
    ) -> Optional[Dict]:
        """Get swap transaction data from Jupiter."""
        try:
            payload = {
                "quoteResponse": quote_data,
                "userPublicKey": publicKey,
                "wrapAndUnwrapSol": wrapAndUnwrapSol,
            }
            if prioritizationFeeLamports:
                payload["prioritizationFeeLamports"] = prioritizationFeeLamports

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post("/v6/swap", json=payload)
                resp.raise_for_status()
                data = resp.json()

            return data  # Contains swapTransaction (base64 encoded)
        except httpx.HTTPStatusError as e:
            logger.error(f"Jupiter swap tx failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Jupiter swap tx error: {e}")
            return None

    async def get_price(self, token_mint: str) -> Optional[TokenPrice]:
        """Get price for a token in USD."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("/v4/price", params={"ids": token_mint})
                resp.raise_for_status()
                data = resp.json()

            if "data" in data and token_mint in data["data"]:
                price_data = data["data"][token_mint]
                return TokenPrice(
                    mint=token_mint,
                    price=float(price_data.get("price", 0)),
                    id=token_mint,
                    symbol=price_data.get("symbol"),
                    confidence=float(price_data.get("conf", 1.0)),
                )
            return None
        except Exception as e:
            logger.error(f"Jupiter price fetch error for {token_mint}: {e}")
            return None

    async def get_multiple_prices(self, token_mints: List[str]) -> Dict[str, TokenPrice]:
        """Get prices for multiple tokens."""
        prices = {}
        for mint in token_mints:
            price = await self.get_price(mint)
            if price:
                prices[mint] = price
        return prices

    async def get_verified_tokens(self) -> List[Dict]:
        """Get list of verified tokens from Jupiter."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("/tokens/tokens", params={"tags": "verified"})
                resp.raise_for_status()
                data = resp.json()

            return data.get("tokens", [])
        except Exception as e:
            logger.error(f"Failed to fetch verified tokens: {e}")
            return []

    async def get_token_by_symbol(self, symbol: str) -> Optional[str]:
        """Get token mint address by symbol."""
        tokens = await self.get_verified_tokens()
        symbol_upper = symbol.upper()
        for token in tokens:
            if token.get("symbol", "").upper() == symbol_upper:
                return token.get("address")
        return None


# Global instance
_jupiter_client: Optional[JupiterClient] = None


def get_jupiter_client() -> JupiterClient:
    """Get global Jupiter client instance."""
    global _jupiter_client
    if _jupiter_client is None:
        _jupiter_client = JupiterClient()
    return _jupiter_client


# ── Convenience functions ───────────────────────────────────────────

async def sol_to_usd_price() -> float:
    """Get current SOL price in USD."""
    client = get_jupiter_client()
    price_data = await client.get_price(SOL_MINT)
    return price_data.price if price_data else 0.0


async def usd_to_sol_amount(usd_amount: float) -> int:
    """Convert USD amount to SOL lamports."""
    price = await sol_to_usd_price()
    if price <= 0:
        return 0
    sol_amount = usd_amount / price
    return int(sol_amount * 1e9)  # Convert to lamports

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

# Jupiter API endpoints.
#
# The legacy `quote-api.jup.ag`, `price.jup.ag` and `tokens.jup.ag` hosts were
# retired (they no longer resolve in DNS). Jupiter's public replacements live on
# `lite-api.jup.ag`; `datapi.jup.ag` serves asset metadata for symbol -> mint
# resolution. Verified against the live API before switching.
JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"
JUPITER_SWAP_URL = "https://lite-api.jup.ag/swap/v1/swap"
JUPITER_PRICE_URL = "https://lite-api.jup.ag/price/v3"
JUPITER_TOKEN_LIST_URL = "https://tokens.jup.ag/tokens?tags=verified"
JUPITER_ASSET_SEARCH_URL = "https://datapi.jup.ag/v1/assets/search"

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
        self.base_url = "https://lite-api.jup.ag"
        self.http_client = httpx.AsyncClient(
            base_url="https://lite-api.jup.ag",
            timeout=30.0,
            headers={"Content-Type": "application/json"}
        )
        # Default WSOL amount for USD pricing
        self._wsol_amount = wsol_amount
        # symbol -> mint cache (assets rarely change; avoids a call per trade)
        self._mint_cache: Dict[str, str] = {}

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
                resp = await client.get(JUPITER_QUOTE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            return SwapQuote(
                input_mint=data.get("inputMint", input_mint),
                output_mint=data.get("outputMint", output_mint),
            # lite-api (swap/v1) returns `inAmount`/`outAmount`; the retired v6
            # payload used `inputAmount`/`outputAmount`. Accept both so sizing
            # never silently collapses to 0.
            input_amount=int(data.get("inAmount", data.get("inputAmount", amount))),
            output_amount=int(data.get("outAmount", data.get("outputAmount", 0))),
            price_pure=float(data.get("pricePure") or 0.0),
            price_impact_pct=float(data.get("priceImpactPct") or 0.0),
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
                resp = await client.post(JUPITER_SWAP_URL, json=payload)
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
        """Get price for a token in USD (Jupiter price v3, with v4 fallback)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(JUPITER_PRICE_URL, params={"ids": token_mint})
                resp.raise_for_status()
                data = resp.json()

            # v3: {"<mint>": {"usdPrice": ...}}; legacy v4: {"data": {"<mint>": {"price": ...}}}
            entry = None
            if isinstance(data, dict):
                if isinstance(data.get(token_mint), dict):
                    entry = data[token_mint]
                elif isinstance(data.get("data"), dict) and isinstance(data["data"].get(token_mint), dict):
                    entry = data["data"][token_mint]
            if entry is None:
                return None

            raw_price = entry.get("usdPrice", entry.get("price", 0)) or 0
            if float(raw_price) <= 0:
                return None
            return TokenPrice(
                mint=token_mint,
                price=float(raw_price),
                id=token_mint,
                symbol=entry.get("symbol"),
                confidence=float(entry.get("conf", 1.0)),
            )
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
                resp = await client.get(JUPITER_TOKEN_LIST_URL)
                resp.raise_for_status()
                data = resp.json()

            return data.get("tokens", [])
        except Exception as e:
            logger.error(f"Failed to fetch verified tokens: {e}")
            return []

    async def get_token_by_symbol(self, symbol: str) -> Optional[str]:
        """Resolve a token symbol to its Solana mint address.

        Uses Jupiter's asset search (`datapi.jup.ag`), which ranks by relevance
        and marks audited assets with `isVerified`. Verified + exact-symbol hits
        are preferred so lookalike memecoins cannot hijack a trade.
        """
        want = symbol.lstrip("$").upper()
        if not want:
            return None

        cached = self._mint_cache.get(want)
        if cached:
            return cached

        # Canonical mints that never need a lookup.
        static = {"SOL": SOL_MINT, "WSOL": SOL_MINT, "USDC": USDC_MINT, "USDT": USDT_MINT}
        if want in static:
            self._mint_cache[want] = static[want]
            return static[want]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(JUPITER_ASSET_SEARCH_URL, params={"query": want})
                resp.raise_for_status()
                assets = resp.json()
        except Exception as e:
            logger.error(f"Jupiter asset search failed for {symbol}: {e}")
            return None

        if not isinstance(assets, list) or not assets:
            logger.warning(f"No Jupiter asset found for {symbol}")
            return None

        def norm(a: Dict) -> str:
            return str(a.get("symbol") or "").lstrip("$").upper()

        verified_exact = [a for a in assets if norm(a) == want and a.get("isVerified")]
        exact = [a for a in assets if norm(a) == want]
        verified = [a for a in assets if a.get("isVerified")]
        chosen = (verified_exact or exact or verified or assets)[0]

        mint = chosen.get("id")
        if not mint:
            return None
        logger.info(f"Resolved {symbol} -> {mint} ({chosen.get('symbol')})")
        self._mint_cache[want] = mint
        return mint


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

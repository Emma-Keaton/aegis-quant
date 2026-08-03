"""
DexScreener API Client
======================
Token discovery, price feeds, and chart data for Solana DEX tokens.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TokenPair:
    """A trading pair on a DEX."""
    chain_id: str
    dex_id: str
    token_x: Dict
    token_y: Dict
    price_usd: float
    volume_24h: float
    liquidity_usd: float
    fdv: Optional[float] = None
    pair_address: str = ""

    def to_dict(self) -> Dict:
        return {
            "chain_id": self.chain_id,
            "dex_id": self.dex_id,
            "token_x_symbol": self.token_x.get("symbol"),
            "token_x_address": self.token_x.get("address"),
            "token_y_symbol": self.token_y.get("symbol"),
            "token_y_address": self.token_y.get("address"),
            "price_usd": self.price_usd,
            "volume_24h": self.volume_24h,
            "liquidity_usd": self.liquidity_usd,
            "fdv": self.fdv,
            "pair_address": self.pair_address,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class DexScreenerClient:
    """Client for DexScreener API."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(
            base_url="https://api.dexscreener.com",
            timeout=30.0
        )

    async def close(self):
        await self.http_client.aclose()

    async def search_tokens(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for tokens by name or symbol."""
        try:
            resp = await self.http_client.get(
                "/latest/dex/search",
                params={"query": query, "limit": limit}
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("pairs", [])
        except Exception as e:
            logger.error(f"DexScreener search error: {e}")
            return []

    async def get_pairs_by_tokens(self, token_addresses: List[str]) -> List[TokenPair]:
        """Get trading pairs for given token addresses."""
        try:
            tokens_param = ",".join(token_addresses)
            resp = await self.http_client.get(f"/latest/dex/tokens/{tokens_param}")
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_pair(p) for p in data.get("pairs", [])]
        except Exception as e:
            logger.error(f"DexScreener pairs error: {e}")
            return []

    async def get_solana_pairs(self, token_address: str) -> List[TokenPair]:
        """Get all Solana pairs for a token."""
        try:
            resp = await self.http_client.get(f"/latest/dex/pairs/solana/{token_address}")
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_pair(p) for p in data.get("pairs", [])]
        except Exception as e:
            logger.error(f"DexScreener solana pairs error: {e}")
            return []

    async def get_top_gainers(self, chain_id: str = "solana", limit: int = 20) -> List[TokenPair]:
        """Get top gaining tokens on Solana."""
        try:
            resp = await self.http_client.get(
                "/latest/dex/tokens",
                params={"chainId": chain_id}
            )
            resp.raise_for_status()
            data = resp.json()
            pairs = data.get("pairs", [])
            pairs.sort(
                key=lambda p: float(p.get("priceChange", {}).get("m5", 0) or 0),
                reverse=True
            )
            return [self._parse_pair(p) for p in pairs[:limit]]
        except Exception as e:
            logger.error(f"DexScreener gainers error: {e}")
            return []

    def _parse_pair(self, pair: Dict) -> TokenPair:
        """Parse a pair dict into TokenPair."""
        return TokenPair(
            chain_id=pair.get("chainId", ""),
            dex_id=pair.get("dexId", ""),
            token_x=pair.get("tokenX", {}),
            token_y=pair.get("tokenY", {}),
            price_usd=float(pair.get("priceUsd", 0) or 0),
            volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
            liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0) or 0),
            fdv=float(pair.get("fdv", 0)) if pair.get("fdv") else None,
            pair_address=pair.get("pairAddress", ""),
        )


_dex_client: Optional[DexScreenerClient] = None


def get_dex_client() -> DexScreenerClient:
    """Get global DexScreener client."""
    global _dex_client
    if _dex_client is None:
        _dex_client = DexScreenerClient()
    return _dex_client

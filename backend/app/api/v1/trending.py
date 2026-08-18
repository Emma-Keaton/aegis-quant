"""Trending tokens router — exposes the trending bucket (separate from the watchlist)."""
from fastapi import APIRouter, Depends

from app.services.trending import get_trending

router = APIRouter(prefix="/api/trending", tags=["trending"])


@router.get("")
async def trending_endpoint():
    """Return the latest trending tokens (CMC → CoinGecko → Raydium) bucket."""
    return {"status": "success", "data": get_trending()}
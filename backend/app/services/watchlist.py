"""Watchlist-driven symbol resolution for the market feeds.

The feeds should watch the *active user watchlist* (UserWhitelist), not a
hardcoded seed, so that when users add/remove tokens the market functions track
the change. Falls back to a sensible default set when no whitelist rows exist.
"""
import logging
from typing import List

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import UserWhitelist

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS: List[str] = [
    "BTC", "ETH", "SOL", "AVAX", "DOT", "TON", "PEPE", "BONK", "WIF", "DOGE",
]


async def get_active_watchlist_symbols() -> List[str]:
    """Return the set of symbols actively watched by any user (base names, upper)."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(UserWhitelist.symbol).where(UserWhitelist.active == True)
        )).scalars().all()
    return [s.upper() for s in rows if s]


async def get_watchlist_or_default() -> List[str]:
    """Watchlist base symbols, or the default seed when the watchlist is empty."""
    syms = await get_active_watchlist_symbols()
    return syms if syms else list(DEFAULT_SYMBOLS)


async def get_watchlist_usc(*_):
    """Watchlist symbols in USDT-perpetual suffix form for CCXT (e.g. 'SOL/USDT')."""
    return [f"{s}/USDT" for s in await get_watchlist_or_default()]
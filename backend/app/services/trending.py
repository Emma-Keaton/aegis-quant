"""Trending tokens poller — separate bucket from the user watchlist.

Polls CoinMarketCap trending → CoinGecko trending → Raydium (memecoin pools) at a
modest interval (default 5 min) and stores a *distinct* ``trending`` set. This is
kept independent of ``UserWhitelist`` so "trending" is always shown separately,
and users can promote a trending token onto their watchlist with one tap.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

CMC_API = "https://pro-api.coinmarketcap.com/v1"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# In-memory trending bucket: { ticker: {ticker, symbol, source, rank, price, ...} }
_trending_cache: Dict[str, dict] = {}
_trending_ts: Optional[str] = None
_poll_task: Optional[asyncio.Task] = None


def get_trending() -> dict:
    """Return the latest cached trending bucket (``{"tickers": [...], "updated": ...}``)."""
    return {
        "tickers": list(_trending_cache.values()),
        "updated": _trending_ts,
    }


async def _cmc_trending(limit: int = 20) -> List[dict]:
    """CoinMarketCap trending (24h gainers/losers). Requires CMC_API_KEY."""
    settings = get_settings()
    key = settings.CMC_API_KEY
    if not key:
        return []
    out: List[dict] = []
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            resp = await client.get(
                f"{CMC_API}/cryptocurrency/trending/gainers-losers",
                params={"time_period": "24h", "limit": limit},
                headers={"X-CMC_PRO_API_KEY": key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for item in data:
                sym = item.get("symbol", "")
                if not sym:
                    continue
                q = item.get("quotes", [{}])[0]
                out.append({
                    "ticker": sym.upper(),
                    "symbol": sym.upper(),
                    "source": "coinmarketcap",
                    "rank": len(out) + 1,
                    "price": q.get("price"),
                    "change_24h": q.get("percent_change"),
                    "volume_24h": q.get("volume_24h"),
                    "market_cap": q.get("market_cap"),
                })
        except Exception as e:
            logger.warning("CMC trending failed: %s", e)
    return out


async def _coingecko_trending(limit: int = 20) -> List[dict]:
    """CoinGecko trending endpoint (search/trending) — needs no API key."""
    out: List[dict] = []
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            resp = await client.get(f"{COINGECKO_API}/search/trending")
            resp.raise_for_status()
            for coin in resp.json().get("coins", [])[:limit]:
                item = coin.get("item", {})
                sym = item.get("symbol", "")
                if not sym:
                    continue
                out.append({
                    "ticker": sym.upper(),
                    "symbol": sym.upper(),
                    "source": "coingecko",
                    "rank": item.get("market_cap_rank") or (len(out) + 1),
                    "price": None,
                    "change_24h": None,
                })
        except Exception as e:
            logger.warning("CoinGecko trending failed: %s", e)
    return out


async def _raydium_trending(limit: int = 20) -> List[dict]:
    """Raydium trending — top-volume memecoin pools (no key needed)."""
    out: List[dict] = []
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            resp = await client.get("https://api-v3.raydium.io/v2/sdk/liquidity/mainnet.json")
            resp.raise_for_status()
            data = resp.json()
            pools = []
            for pool in data:
                price = pool.get("price")
                if not price:
                    continue
                vol = pool.get("volume24h") or pool.get("lpVolume24h") or 0
                pools.append({
                    "ticker": (pool.get("baseSymbol") or pool.get("quoteSymbol") or "?").upper(),
                    "symbol": (pool.get("baseSymbol") or pool.get("quoteSymbol") or "?").upper(),
                    "price": float(str(price)),
                    "volume_24h": float(vol) if vol else None,
                })
            pools.sort(key=lambda p: p.get("volume_24h") or 0, reverse=True)
            seen = set()
            for p in pools[: limit * 3]:
                t = p["ticker"]
                if t in seen:
                    continue
                seen.add(t)
                out.append({**p, "source": "raydium", "rank": len(out) + 1, "change_24h": None})
                if len(out) >= limit:
                    break
        except Exception as e:
            logger.warning("Raydium trending failed: %s", e)
    return out


async def poll_trending() -> List[dict]:
    """Run a single trending sweep across CMC → CoinGecko → Raydium and refresh cache."""
    cmc = await _cmc_trending()
    cg = await _coingecko_trending()
    ray = await _raydium_trending()
    merged: Dict[str, dict] = {}
    for item in cmc + cg + ray:
        t = item.get("ticker")
        if t and t not in merged:
            merged[t] = item
    global _trending_cache, _trending_ts
    _trending_cache = merged
    _trending_ts = datetime.now(timezone.utc).isoformat() + "Z"
    logger.info("Trending refresh: %d tokens", len(_trending_cache))
    return list(merged.values())


async def trending_loop() -> None:
    """Background loop that refreshes the trending bucket on an interval."""
    settings = get_settings()
    await poll_trending()
    while True:
        await asyncio.sleep(settings.TRENDING_POLL_SECONDS)
        await poll_trending()


def start_trending_poller() -> asyncio.Task:
    """Start the background trending poller (idempotent)."""
    global _poll_task
    if _poll_task and not _poll_task.done():
        return _poll_task
    _poll_task = asyncio.create_task(trending_loop())
    return _poll_task


async def stop_trending_poller() -> None:
    """Cancel the background trending poller."""
    global _poll_task
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
        _poll_task = None
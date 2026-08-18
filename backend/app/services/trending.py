"""Trending tokens poller — separate bucket from the user watchlist.

Polls CoinMarketCap trending → GeckoTerminal trending → DexScreener (memecoin
top/latest) at a modest interval (default 5 min) and stores a *distinct*
``trending`` set. Kept independent of ``UserWhitelist`` so "trending" is always
shown separately, and users can promote a trending token onto their watchlist
with one tap.
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
DEXSCREENER_API = "https://api.dexscreener.com"
GEKCO_API = "https://api.geckoterminal.com/api/v2"

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


async def _dexscreener_trending(limit: int = 20) -> List[dict]:
    """DexScreener trending — newly-launched / top-boosted Solana memecoins (free, no key)."""
    import re
    out: List[dict] = []
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            resp = await client.get(
                f"{DEXSCREENER_API}/token-profiles/latest/v1",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            profiles = resp.json() or []
            for p in profiles[:limit]:
                # Filter to Solana-minted tokens (meme-heavy chains).
                chain = (p.get("chainId") or "").lower()
                if "solana" not in chain:
                    continue
                token_addr = p.get("tokenAddress") or ""
                # Best-effort ticker: lucide a symbol from the description, else
                # a short form of the token address.
                desc = p.get("description") or ""
                m = re.search(r"\$([A-Za-z0-9]{2,10})\b", desc)
                sym = (m.group(1) if m else token_addr[:6]).upper()
                if not sym:
                    continue
                out.append({
                    "ticker": sym,
                    "symbol": sym,
                    "source": "dexscreener",
                    "rank": len(out) + 1,
                    "price": None,
                    "change_24h": None,
                    "volume_24h": None,
                    "address": token_addr,
                })
        except Exception as e:
            logger.warning("DexScreener trending failed: %s", e)
    return out


async def _geckoterminal_trending(limit: int = 20) -> List[dict]:
    """GeckoTerminal trending — free, no key. Solana trending pools + pair data."""
    out: List[dict] = []
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            resp = await client.get(
                f"{GEKCO_API}/networks/solana/trending_pools",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for pool in data[:limit]:
                attrs = pool.get("attributes", {})
                # Pool name is "SYMBOL / QUOTE" — take the first segment as ticker.
                name = attrs.get("name") or ""
                sym = (name.split("/")[0].strip() or "").upper()
                if not sym:
                    continue
                price = attrs.get("base_token_price_usd")
                pc = attrs.get("price_change_percentage") or {}
                vol = attrs.get("volume_usd") or {}
                out.append({
                    "ticker": sym,
                    "symbol": sym,
                    "source": "geckoterminal",
                    "rank": len(out) + 1,
                    "price": float(price) if price else None,
                    "change_24h": float(pc["h24"]) if pc.get("h24") is not None else None,
                    "volume_24h": float(vol["h24"]) if vol.get("h24") is not None else None,
                    "address": attrs.get("address"),
                })
        except Exception as e:
            logger.warning("GeckoTerminal trending failed: %s", e)
    return out


async def poll_trending() -> List[dict]:
    """Run a single trending sweep across CMC → GeckoTerminal → DexScreener and refresh cache."""
    cmc = await _cmc_trending()
    gt = await _geckoterminal_trending()
    dx = await _dexscreener_trending()
    merged: Dict[str, dict] = {}
    for item in cmc + gt + dx:
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
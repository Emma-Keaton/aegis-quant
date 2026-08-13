"""QuantDinger market data fetcher.

Fetches live price data from **CoinGecko** (primary) and falls back to **CoinLore**
if a ticker is missing. The data is stored in ``app.state.market_data`` for the
rest of the backend to consume.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any
import httpx
from fastapi import FastAPI

# Update interval – 30 seconds as before
FETCH_INTERVAL = 30

# Cache of symbol → CoinGecko ID mapping (populated on first fetch)
_SYMBOL_ID_MAP: Dict[str, str] = {}

COINGECKO_API = "https://api.coingecko.com/api/v3"
COINLORE_API = "https://api.coinlore.com/api"
COINBASE_API = "https://api.coinbase.com/v2"
BINANCE_API = "https://api.binance.com/api/v3"

async def _populate_symbol_map() -> None:
    """Populate ``_SYMBOL_ID_MAP`` with ``symbol -> coingecko_id``.

    Uses the ``/coins/list`` endpoint which returns all supported coins.
    The mapping is cached for the lifetime of the process.
    """
    global _SYMBOL_ID_MAP
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{COINGECKO_API}/coins/list")
            resp.raise_for_status()
            data = resp.json()
            for entry in data:
                symbol = entry.get("symbol", "").upper()
                coin_id = entry.get("id")
                if symbol and coin_id:
                    _SYMBOL_ID_MAP[symbol] = coin_id
        except Exception as e:
            # If CoinGecko fails, we leave the map empty and rely on fallback.
            print(f"[market_fetcher] Failed to load CoinGecko symbol list: {e}")

async def _fetch_price_from_coingecko(symbol: str) -> Any:
    """Fetch price for a single ``symbol`` (e.g. ``BTCUSDT``).

    Returns ``None`` if the symbol cannot be resolved.
    """
    if not _SYMBOL_ID_MAP:
        await _populate_symbol_map()
    coin_id = _SYMBOL_ID_MAP.get(symbol.upper().split("USDT")[0])
    if not coin_id:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{COINGECKO_API}/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd"},
            )
            resp.raise_for_status()
            price_data = resp.json()
            return price_data.get(coin_id, {}).get("usd")
        except Exception:
            return None

async def _fetch_price_from_coinlore(symbol: str) -> Any:
    """Fallback price fetch using CoinLore.

    CoinLore does not support arbitrary symbols directly, so we pull the
    top‑200 tickers and try to match by symbol.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{COINLORE_API}/tickers/?limit=200")
            resp.raise_for_status()
            data = resp.json()
            for ticker in data.get("data", []):
                if ticker.get("symbol") == symbol.upper():
                    # ``price_usd`` is a string; convert to float.
                    return float(ticker.get("price_usd", 0))
        except Exception:
            return None
    return None

# New fetchers – Coinbase and Binance ------------------------------------

async def _fetch_price_from_coinbase(symbol: str) -> Any:
    """Fetch price from Coinbase API.

    Coinbase expects symbols in the form ``BTC-USD``.
    """
    # Transform ``BTCUSDT`` -> ``BTC-USD`` (USDT is equivalent to USD here)
    base = symbol.upper().replace("USDT", "").replace("USD", "")
    pair = f"{base}-USD"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{COINBASE_API}/prices/{pair}/spot")
            resp.raise_for_status()
            data = resp.json()
            amount = data.get("data", {}).get("amount")
            if amount:
                return float(amount)
        except Exception:
            return None
    return None

async def _fetch_price_from_binance(symbol: str) -> Any:
    """Fetch price from Binance public ticker endpoint.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BINANCE_API}/ticker/price", params={"symbol": symbol.upper()})
            resp.raise_for_status()
            data = resp.json()
            price = data.get("price")
            if price:
                return float(price)
        except Exception:
            return None
    return None

async def fetch_market_data() -> Dict[str, Any]:
    """Collect a snapshot of market prices.

    Returns a dictionary with a UTC timestamp and a ``prices`` mapping:
    ``{"BTCUSDT": 30123.45, "ETHUSDT": 1850.12, ...}``.
    """
    # Watch the *active watchlist* so the feed tracks user changes; fall back to
    # a default seed when the watchlist is empty.
    from app.services.watchlist import get_watchlist_or_default
    base = await get_watchlist_or_default()
    symbols = [f"{s}USDT" for s in base]
    prices: Dict[str, float] = {}
    for sym in symbols:
        # Preference order: Binance (primary, free + reliable) →
        # CoinGecko → Coinbase → CoinLore (fallbacks).
        price = await _fetch_price_from_binance(sym)
        if price is None:
            price = await _fetch_price_from_coingecko(sym)
        if price is None:
            price = await _fetch_price_from_coinbase(sym)
        if price is None:
            price = await _fetch_price_from_coinlore(sym)
        if price is not None:
            prices[sym] = float(price)
    return {"timestamp": datetime.utcnow().isoformat() + "Z", "prices": prices}

async def market_fetcher_task(app: FastAPI):
    """Background coroutine that periodically updates ``app.state.market_data``.
    """
    while True:
        data = await fetch_market_data()
        app.state.market_data = data
        await asyncio.sleep(FETCH_INTERVAL)

import asyncio
import logging
from typing import List, Dict, Any

import ccxt

# Re‑use the CCXT helper from wallet_gateway for consistency
from .wallet_gateway import get_ccxt_exchange

logger = logging.getLogger("market_hub")

# In‑memory cache for ticker data (keyed by symbol)
_market_cache: Dict[str, Any] = {}
# Keep references to the polling tasks so we can cancel them on shutdown
_polling_tasks: List[asyncio.Task] = []


def get_market_data(symbol: str) -> Any:
    """Return the latest cached ticker for *symbol* (or ``None`` if not fetched yet)."""
    return _market_cache.get(symbol)


async def _poll_symbol(symbol: str, exchange_name: str, interval: float) -> None:
    """Continuously fetch ``symbol`` ticker from *exchange_name* every ``interval`` seconds.
    The result is stored in the module‑level ``_market_cache``.
    """
    exchange = get_ccxt_exchange(exchange_name)
    while True:
        try:
            # ``fetch_ticker`` is blocking in ccxt; run it in a thread pool.
            ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
            _market_cache[symbol] = ticker
            logger.debug("Fetched ticker %s: %s", symbol, ticker)
        except Exception as exc:  # pragma: no cover – defensive logging only
            logger.warning("Failed to fetch ticker %s from %s: %s", symbol, exchange_name, exc)
        await asyncio.sleep(interval)


async def start_market_feed(
    symbols: List[str] | None = None,
    interval: float = 5.0,
    exchange_name: str = "binance",
) -> None:
    """Spawn background ``asyncio`` tasks that keep ``_market_cache`` fresh.

    * ``symbols`` – list of ticker symbols to watch (defaults to ``["BTC/USDT"]``).
    * ``interval`` – seconds between fetches (use a small value in tests).
    * ``exchange_name`` – name of a CCXT exchange that supports ``fetch_ticker``.
    """
    if symbols is None:
        symbols = ["BTC/USDT"]
    # Cancel any existing tasks before starting new ones (idempotent design)
    await stop_market_feed()
    for sym in symbols:
        task = asyncio.create_task(_poll_symbol(sym, exchange_name, interval))
        _polling_tasks.append(task)
    logger.info("Market feed started for %s on %s (interval %.2fs)", symbols, exchange_name, interval)


async def stop_market_feed() -> None:
    """Cancel all polling tasks and clear the task list.
    The cached ticker data is left untouched – callers can decide whether to clear it.
    """
    for t in _polling_tasks:
        t.cancel()
    # Wait for cancellation to propagate; ignore any CancelledError.
    await asyncio.gather(*_polling_tasks, return_exceptions=True)
    _polling_tasks.clear()
    logger.info("Market feed stopped")

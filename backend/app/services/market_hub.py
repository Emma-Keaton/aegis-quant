import asyncio
import logging
from typing import List, Dict, Any, Optional

import ccxt

# Re‑use the CCXT helper from wallet_gateway for consistency
from .wallet_gateway import get_ccxt_exchange

logger = logging.getLogger("market_hub")

# In‑memory cache for ticker data (keyed by symbol)
_market_cache: Dict[str, Any] = {}
# Keep references to the polling tasks so we can cancel them on shutdown
_polling_tasks: List[asyncio.Task] = []
# Symbols the feed is currently subscribed to + the watchlist reconcile task.
_tracked_symbols: List[str] = []
_reconcile_task: Optional[asyncio.Task] = None


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


async def _reconcile_watchlist(exchange_name: str, interval: float) -> None:
    """Periodically compare the watched set to the watchlist and re-sync."""
    while True:
        await asyncio.sleep(60)
        try:
            from app.services.watchlist import get_watchlist_usc
            desired = sorted(await get_watchlist_usc())
            current = sorted(_tracked_symbols or [])
            if desired and desired != current:
                logger.info("Watchlist changed (%s -> %s) — re-syncing market feed", current, desired)
                await start_market_feed(desired, interval=interval, exchange_name=exchange_name)
        except Exception as e:  # pragma: no cover – defensive
            logger.warning("Watchlist reconcile failed: %s", e)


async def start_market_feed(
    symbols: List[str] | None = None,
    interval: float = 5.0,
    exchange_name: str = "binance",
) -> None:
    """Spawn background ``asyncio`` tasks that keep ``_market_cache`` fresh.

    * ``symbols`` – ticker symbols to watch (defaults to the *active watchlist*).
    * ``interval`` – seconds between fetches (use a small value in tests).
    * ``exchange_name`` – name of a CCXT exchange that supports ``fetch_ticker``.
    """
    global _tracked_symbols
    if symbols is None:
        from app.services.watchlist import get_watchlist_usc
        symbols = await get_watchlist_usc()
    # Cancel any existing tasks before starting new ones (idempotent design)
    await stop_market_feed()
    _tracked_symbols = list(symbols)
    for sym in symbols:
        task = asyncio.create_task(_poll_symbol(sym, exchange_name, interval))
        _polling_tasks.append(task)
    logger.info("Market feed started for %s on %s (interval %.2fs)", symbols, exchange_name, interval)

    # Keep the feed in sync with the watchlist (restart when it changes).
    if not _reconcile_task or _reconcile_task.done():
        _reconcile_task = asyncio.create_task(_reconcile_watchlist(exchange_name, interval))


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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

from app.engines.engine_a import EngineA
from app.engines.engine_b import EngineB
from app.config import get_settings
from app.services.forecasting import get_forecasting_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
engine_a: EngineA | None = None
engine_b: EngineB | None = None

# Tick/watchlist used to precompute replacement forecasts in the worker.
DEFAULT_FORECAST_TICKERS = ["SOL", "TON", "BTC", "ETH", "PEPE", "BONK", "DOGE", "WIF"]


async def precompute_forecasts() -> None:
    """Batch-precompute replacement forecasts for the watchlist into the cache.

    Runs on an interval in the worker so the API reads cached, ranked results
    instead of fitting on the request path.
    """
    settings = get_settings()
    if not settings.FORECAST_BATCH_ENABLED:
        return
    from app.services.market_service import get_market_service

    svc = get_forecasting_service()
    market = get_market_service()
    tickers = DEFAULT_FORECAST_TICKERS[: settings.FORECAST_BATCH_TOP_N]
    for ticker in tickers:
        try:
            ohlcv = await market.fetch_ohlcv(
                symbol=ticker, exchange_id="binance", timeframe="1h", limit=200
            )
            closes = [e["close"] for e in ohlcv] if ohlcv else None
            if closes and len(closes) >= 16:
                await svc.forecast(symbol=ticker, closes=closes, horizon=30, samples=30)
        except Exception as e:
            logger.warning(f"Forecast precompute failed for {ticker}: {e}")


async def start_engines():
    """Initialize and start both trading engines"""
    global engine_a, engine_b
    
    logger.info("Starting trading engines...")
    
    # Initialize Engine A
    engine_a = EngineA()
    await engine_a.initialize()
    
    # Initialize Engine B
    engine_b = EngineB()
    await engine_b.initialize()
    
    # Schedule Engine A trigger scan — cheap price/trigger poll at fast cadence.
    # Gemini analysis + execution stay gated on thresholds inside _process_signal.
    if get_settings().ENGINE_SCAN_ENABLED:
        scheduler.add_job(
            engine_a.scheduled_scan,
            IntervalTrigger(seconds=get_settings().ENGINE_A_SCAN_SECONDS),
            id="engine_a_scan",
            max_instances=1,
            replace_existing=True
        )

        # Schedule Engine B social scan. External scrapers (Twitter/Telegram/
        # CoinGecko) are rate-limited, so use a slightly wider cadence.
        scheduler.add_job(
            engine_b.run_social_scan,
            IntervalTrigger(seconds=get_settings().ENGINE_B_SCAN_SECONDS),
            id="engine_b_scan",
            max_instances=1,
            replace_existing=True
        )

    # Schedule replacement-forecast precompute (worker) — keeps the cache warm
    scheduler.add_job(
        precompute_forecasts,
        IntervalTrigger(seconds=get_settings().FORECAST_BATCH_INTERVAL_SECONDS),
        id="forecast_precompute",
        max_instances=1,
        replace_existing=True
    )
    try:
        await precompute_forecasts()
    except Exception as e:
        logger.warning(f"Initial forecast precompute skipped: {e}")
    
    # Schedule daily stats reset
    scheduler.add_job(
        reset_daily_stats,
        IntervalTrigger(hours=24),
        id="daily_stats_reset",
        max_instances=1
    )
    
    scheduler.start()
    logger.info("Engines started successfully")


async def stop_engines():
    """Stop engines gracefully"""
    global engine_a, engine_b
    
    logger.info("Stopping engines...")
    scheduler.shutdown(wait=True)
    
    if engine_a:
        await engine_a.shutdown()
    
    if engine_b:
        await engine_b.shutdown()
    
    logger.info("Engines stopped")


async def reset_daily_stats():
    """Reset daily PnL and trade counters"""
    logger.info("Resetting daily stats")
    # TODO: Reset daily drawdown, trade counts, etc.


def get_engine_a() -> EngineA:
    if engine_a is None:
        raise RuntimeError("Engine A not initialized")
    return engine_a


def get_engine_b() -> EngineB:
    if engine_b is None:
        raise RuntimeError("Engine B not initialized")
    return engine_b
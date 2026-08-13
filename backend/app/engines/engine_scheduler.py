from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
from sqlalchemy import select

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

    # Schedule copy-trade channel polling (parse → confidence → execute)
    from app.engines.engine_scheduler import copytrade_cycle
    scheduler.add_job(
        copytrade_cycle,
        IntervalTrigger(seconds=get_settings().COPYTRADE_SCAN_SECONDS),
        id="copytrade_scan",
        max_instances=1,
        replace_existing=True
    )

    # Schedule position mark-to-market (live price / unrealized PnL refresh).
    from app.engines.engine_scheduler import mark_to_market
    scheduler.add_job(
        mark_to_market,
        IntervalTrigger(seconds=15),
        id="mark_to_market",
        max_instances=1,
        replace_existing=True
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


# In-memory daily counters (reset once per day).
_daily_stats = {"trades": 0, "pnl": 0.0}


async def mark_to_market() -> None:
    """Refresh live prices / unrealized PnL for all open positions."""
    from decimal import Decimal

    from app.database import AsyncSessionLocal
    from app.models import Position
    from app.services.market_service import get_market_service

    market = get_market_service()
    async with AsyncSessionLocal() as db:
        pos_result = await db.execute(select(Position).where(Position.is_closed == False))
        positions = pos_result.scalars().all()
        for p in positions:
            sym = (p.symbol or "").upper()
            if not sym:
                continue
            try:
                ticker = await market.get_ticker(f"{sym}/USDT", exchange_id="binance")
                price = float(ticker["last"])
            except Exception:
                continue
            entry = float(p.entry_price or 0)
            delta = price - entry
            is_long = bool(p.side and p.side.value == "buy")
            signed = delta if is_long else -delta
            p.current_price = Decimal(str(price))
            p.unrealized_pnl = Decimal(str(float(p.size or 0) * signed))
        await db.commit()


async def reset_daily_stats():
    """Reset daily PnL and trade counters."""
    global _daily_stats
    _daily_stats = {"trades": 0, "pnl": 0.0}
    logger.info("Daily stats reset")


async def copytrade_cycle() -> None:
    """Poll all watched copy-trade channels: parse → confidence → execute."""
    if not get_settings().COPYTRADE_SCAN_ENABLED:
        return
    from app.services.copytrade_scanner import run_copytrade_scan_once
    try:
        await run_copytrade_scan_once()
    except Exception as e:
        logger.warning(f"Copy-trade scan cycle failed: {e}")


def get_engine_a() -> EngineA:
    if engine_a is None:
        raise RuntimeError("Engine A not initialized")
    return engine_a


def get_engine_b() -> EngineB:
    if engine_b is None:
        raise RuntimeError("Engine B not initialized")
    return engine_b
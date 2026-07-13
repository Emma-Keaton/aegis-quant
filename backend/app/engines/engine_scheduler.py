from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

from app.engines.engine_a import EngineA
from app.engines.engine_b import EngineB

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
engine_a: EngineA | None = None
engine_b: EngineB | None = None


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
    
    # Schedule Engine A full scan every 5 minutes (fallback)
    scheduler.add_job(
        engine_a.scheduled_scan,
        IntervalTrigger(minutes=5),
        id="engine_a_scan",
        max_instances=1,
        replace_existing=True
    )
    
    # Schedule Engine B social scan every 30 minutes
    scheduler.add_job(
        engine_b.run_social_scan,
        IntervalTrigger(minutes=30),
        id="engine_b_scan",
        max_instances=1,
        replace_existing=True
    )
    
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
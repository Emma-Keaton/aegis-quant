from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
from sqlalchemy import select

from app.engines.engine_a import EngineA
from app.engines.engine_b import EngineB
from app.config import get_settings
from app.services.kronos_service import get_kronos_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
engine_a: EngineA | None = None
engine_b: EngineB | None = None

# Tick/watchlist used to precompute replacement forecasts in the worker.
DEFAULT_FORECAST_TICKERS = ["SOL", "TON", "BTC", "ETH", "PEPE", "BONK", "DOGE", "WIF"]


async def precompute_forecasts() -> None:
    """Warm real Kronos forecasts for the watchlist, then score old ones.

    Runs on an interval in the worker so the API reads cached, ranked results
    instead of fitting on the request path.

    Kronos is used rather than the replacement forecaster: the replacement is
    only a fallback for when Kronos is unreachable. This also drives the
    calibration loop — every forecast recorded here is later scored against
    realised prices by `KronosService.score_pending`, which is how `confidence`
    becomes trustworthy.
    """
    settings = get_settings()
    if not settings.FORECAST_BATCH_ENABLED:
        return

    kronos = get_kronos_service()
    tickers = DEFAULT_FORECAST_TICKERS[: settings.FORECAST_BATCH_TOP_N]

    for ticker in tickers:
        try:
            await kronos.forecast_symbol(
                ticker,
                timeframe="1h",
                horizon=30,
                samples=10,
                exchange_id="binance",
                limit=200,
            )
        except Exception as exc:
            logger.warning("Kronos precompute failed for %s: %s", ticker, exc)

    # Score anything whose horizon has now elapsed.
    try:
        scored = await kronos.score_pending()
        if scored:
            logger.info("Scored %d Kronos forecasts", len(scored))
        summary = await kronos.calibration_summary()
        if summary.get("scored"):
            logger.info("Kronos calibration: %s", summary)
    except Exception as exc:
        logger.warning("Kronos scoring pass failed: %s", exc)


async def refit_learned_parameters() -> None:
    """Refit global thresholds and promote a model on accumulated evidence.

    Learned parameters and the active model are workspace-global, so this runs
    once for the whole workspace rather than per profile: every device's scored
    trades count toward the same estimate. Promotion is still gated on a
    statistically significant record, so an early run cannot install a model on
    noise.
    """
    kronos = get_kronos_service()
    try:
        outcome = await kronos.refit()
    except Exception as exc:
        logger.warning("Learned-parameter refit failed: %s", exc)
        return
    logger.info(
        "Refit: %s samples, validated=%s, promoted=%s (%s)",
        outcome.get("sample_size"),
        outcome.get("validated"),
        outcome.get("promoted_model") if outcome.get("promoted") else None,
        outcome.get("reason"),
    )


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

    # Schedule the global learner. Refitting on every forecast batch would be
    # wasteful (the gates barely move on one new sample) and would rewrite the
    # parameter history constantly; hourly is enough to keep thresholds current.
    scheduler.add_job(
        refit_learned_parameters,
        IntervalTrigger(hours=1),
        id="learned_parameter_refit",
        max_instances=1,
        replace_existing=True,
    )
    
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

    # Stop-loss / take-profit enforcement on refreshed marks. Runs right after
    # mark-to-market so triggers are evaluated against the freshest price.
    scheduler.add_job(
        manage_positions,
        IntervalTrigger(seconds=15),
        id="manage_positions",
        max_instances=1,
        replace_existing=True,
    )

    # Hot-token DEX watcher: pairs → rank → spike detection → Telegram pings.
    settings = get_settings()
    if settings.DEX_WATCH_ENABLED:
        scheduler.add_job(
            dex_watch_tick,
            IntervalTrigger(seconds=settings.DEX_WATCH_INTERVAL_SECONDS),
            id="dex_watch",
            max_instances=1,
            replace_existing=True,
        )

    # Whale-flow watcher (Helius): creates signal rows + Telegram pings.
    if settings.HELIUS_API_KEY:
        scheduler.add_job(
            whale_watch_tick,
            IntervalTrigger(seconds=settings.WHALE_WATCH_INTERVAL_SECONDS),
            id="whale_watch",
            max_instances=1,
            replace_existing=True,
        )

    # Paper→live promotion gate: evaluates evidence, records decisions, pings.
    scheduler.add_job(
        promotion_cycle,
        IntervalTrigger(hours=settings.PROMOTION_INTERVAL_HOURS),
        id="promotion_cycle",
        max_instances=1,
        replace_existing=True,
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


async def manage_positions() -> None:
    """Enforce stop-loss / take-profit on open positions."""
    try:
        from app.services.position_manager import manage_open_positions
        closed = await manage_open_positions()
        if closed:
            logger.info("SL/TP manager closed %d position(s)", closed)
    except Exception as e:
        logger.warning("Position management tick failed: %s", e)


async def dex_watch_tick() -> None:
    """Collect DEX pairs, detect spikes, persist snapshots, notify."""
    try:
        from app.services import dexwatch
        await dexwatch.tick()
    except Exception as e:
        logger.warning("Dex watch tick failed: %s", e)


async def whale_watch_tick() -> None:
    """Collect whale transactions, surface flows as signals + notifications."""
    try:
        from app.services import whale_watch
        await whale_watch.tick()
    except Exception as e:
        logger.warning("Whale watch tick failed: %s", e)


async def promotion_cycle() -> None:
    """Run the paper→live promotion gate for every active profile."""
    try:
        from app.services import promotion
        await promotion.run_cycle()
    except Exception as e:
        logger.warning("Promotion cycle failed: %s", e)


def get_engine_a() -> EngineA:
    if engine_a is None:
        raise RuntimeError("Engine A not initialized")
    return engine_a


def get_engine_b() -> EngineB:
    if engine_b is None:
        raise RuntimeError("Engine B not initialized")
    return engine_b
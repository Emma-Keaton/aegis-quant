"""Open-position management: stop-loss / take-profit enforcement.

Positions record `stop_loss`/`take_profit` at entry, but nothing ever enforced
them — a triggered row stayed open forever. This closes triggered positions
with the same accounting a manual close uses: opposite-side execution (moves
paper cash / places the live order), a realised `TradeLog`, the frozen PnL on
the row, and a circuit-breaker feed.

Closes are intentionally allowed while the breaker is open: closing reduces
exposure, and a breaker that stops you from getting out is a trap.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select

logger = logging.getLogger(__name__)


def _side_str(position) -> str:
    side = position.side
    return side.value if hasattr(side, "value") else str(side)


def trigger_hit(position, price: float) -> Optional[str]:
    """`"stop_loss"` | `"take_profit"` | None for a mark price (pure)."""
    if price is None or price <= 0:
        return None
    sl = float(position.stop_loss or 0)
    tp = float(position.take_profit or 0)
    is_long = _side_str(position) == "buy"
    if sl > 0:
        if is_long and price <= sl:
            return "stop_loss"
        if not is_long and price >= sl:
            return "stop_loss"
    if tp > 0:
        if is_long and price >= tp:
            return "take_profit"
        if not is_long and price <= tp:
            return "take_profit"
    return None


async def close_with_router(db, profile, position, *, router,
                            exit_price_hint: float = 0.0) -> float:
    """Close one position row through the router; freeze the evidence.

    Does not commit — the caller owns the transaction (matching the halt
    path's per-position failure handling). Returns realised PnL in USD.
    """
    from app.models import ExecutionType, OrderSide, OrderStatus, TradeLog

    side = _side_str(position)
    size = float(position.size or 0)
    entry = float(position.entry_price or 0)

    if size <= 0:
        # Nothing to unwind, but the row must not stay "open" forever.
        position.is_closed = True
        return 0.0

    # Position rows store bare symbols ("BTC"); the router wants venue format.
    symbol = position.symbol or ""
    if symbol and "/" not in symbol:
        symbol = f"{symbol}/USDT"
    hint = float(exit_price_hint or float(position.current_price or 0) or entry)
    result = await router.close_position(
        profile, symbol, side, size, profile.trading_mode.value, price=hint
    )
    exit_price = float(getattr(result, "price", 0) or hint)
    direction = 1 if side == "buy" else -1
    pnl = (exit_price - entry) * size * direction

    db.add(TradeLog(
        profile_id=profile.id,
        symbol=position.symbol,
        exchange=position.exchange,
        side=OrderSide.SELL if side == "buy" else OrderSide.BUY,
        execution_type=ExecutionType(profile.trading_mode.value),
        size=Decimal(str(size)),
        price=Decimal(str(exit_price)),
        total_value_usd=Decimal(str(size * exit_price)),
        status=OrderStatus.FILLED,
        realized_pnl=Decimal(str(pnl)),
        entry_price=Decimal(str(entry)),
        exit_price=Decimal(str(exit_price)),
        closed_at=datetime.now(timezone.utc),
    ))

    position.is_closed = True
    position.unrealized_pnl = Decimal(str(pnl))
    position.current_price = Decimal(str(exit_price))
    return pnl


async def _feed_breaker(pnl: float) -> None:
    try:
        from app.services import circuit_breaker
        await circuit_breaker.record_outcome(pnl)
    except Exception as exc:
        logger.warning("Breaker feed failed: %s", exc)


async def manage_open_positions() -> int:
    """Close every open position whose mark price has breached SL/TP."""
    from app.database import AsyncSessionLocal
    from app.engines.execution_router import ExecutionRouter
    from app.models import Position, Profile

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Position).where(Position.is_closed.is_(False))
        )).scalars().all()
        if not rows:
            return 0

        router = ExecutionRouter()
        closed = 0
        pnls = []
        try:
            for pos in rows:
                price = float(pos.current_price or 0)
                hit = trigger_hit(pos, price)
                if hit is None:
                    continue
                profile = await db.get(Profile, pos.profile_id)
                if profile is None:
                    continue
                try:
                    pnl = await close_with_router(
                        db, profile, pos, router=router, exit_price_hint=price
                    )
                except Exception as exc:
                    # Venue failure keeps the row open: better to retry next
                    # tick than to book a close that never happened.
                    logger.warning(
                        "SL/TP close failed for %s (%s): %s",
                        pos.symbol, hit, exc,
                    )
                    continue
                pnls.append(pnl)
                closed += 1
                logger.info(
                    "Position closed (%s) %s pnl=%.2f", hit, pos.symbol, pnl
                )
            await db.commit()
        finally:
            try:
                await router.close_all()
            except Exception:
                pass

    for pnl in pnls:
        await _feed_breaker(pnl)
    return closed

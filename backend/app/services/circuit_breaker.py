"""Global trading circuit breaker (port of beast-trader's ml/circuit.js).

States: `closed` trades normally, `warning` is advisory, `open` refuses live
orders until an operator calls `resume()`. Breakers never self-clear — a
system that auto-resumes after a drawdown trip has learned nothing.

Limits come from config (15% drawdown, 6 consecutive losses, warning at
8% / 3) and equity is the sum of paper balances plus closed-position PnL,
evaluated from the database so the state survives process restarts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import select, func

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import BreakerState, PaperBalance, Position

logger = logging.getLogger(__name__)

_MIRROR: dict = {"state": "closed", "reason": None, "daily_loss_usd": 0.0,
                 "consecutive_losses": 0, "peak_equity": None, "evaluated_at": None}


async def _get_state(db) -> BreakerState:
    state = (await db.execute(select(BreakerState).where(BreakerState.id == 1))).scalar_one_or_none()
    if state is None:
        state = BreakerState(id=1, state="closed", daily_loss_usd=0.0, consecutive_losses=0)
        db.add(state)
        await db.commit()
        await db.refresh(state)
    return state


async def _equity(db) -> float:
    total = (await db.execute(
        select(func.coalesce(func.sum(PaperBalance.balance), 0))
    )).scalar()
    return float(total or 0.0)


async def _daily_closed_pnl(db) -> float:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total = (await db.execute(
        select(func.coalesce(func.sum(Position.unrealized_pnl), 0))
        .where(Position.is_closed.is_(True))
        .where(Position.updated_at >= today_start)
    )).scalar()
    return float(total or 0.0)


def _update_mirror(state: BreakerState) -> None:
    _MIRROR.update({
        "state": state.state,
        "reason": state.reason,
        "daily_loss_usd": float(state.daily_loss_usd or 0.0),
        "consecutive_losses": int(state.consecutive_losses or 0),
        "peak_equity": state.peak_equity,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    })


async def evaluate() -> dict:
    """Recompute breaker inputs from the DB; trip (never un-trip) on breach."""
    settings = get_settings()
    if not settings.BREAKER_ENABLED:
        return {**_MIRROR, "enabled": False}
    async with AsyncSessionLocal() as db:
        state = await _get_state(db)
        if state.state == "open":
            _update_mirror(state)
            return {**_MIRROR, "enabled": True}

        equity = await _equity(db)
        daily_pnl = await _daily_closed_pnl(db)
        peak = state.peak_equity if state.peak_equity is not None else equity
        peak = max(peak, equity)

        state.peak_equity = peak
        state.daily_loss_usd = min(0.0, daily_pnl)
        reasons = []
        if peak > 0:
            drawdown_pct = (1.0 - equity / peak) * 100.0
            if drawdown_pct >= settings.BREAKER_MAX_DRAWDOWN_PCT:
                reasons.append(f"drawdown {drawdown_pct:.1f}% >= {settings.BREAKER_MAX_DRAWDOWN_PCT}%")
            elif drawdown_pct >= settings.BREAKER_WARN_DRAWDOWN_PCT and state.state == "closed":
                state.state = "warning"
                state.reason = f"drawdown {drawdown_pct:.1f}% approaching limit"
        if reasons:
            state.state = "open"
            state.reason = "; ".join(reasons)
        state.updated_at = datetime.now(timezone.utc)
        await db.commit()
        _update_mirror(state)
        return {**_MIRROR, "enabled": True, "equity": equity}


async def record_outcome(pnl_usd: float) -> dict:
    """Feed one realised trade outcome (closed position PnL)."""
    settings = get_settings()
    if not settings.BREAKER_ENABLED:
        return {**_MIRROR, "enabled": False}
    async with AsyncSessionLocal() as db:
        state = await _get_state(db)
        if state.state == "open":
            _update_mirror(state)
            return {**_MIRROR, "enabled": True}
        if pnl_usd < 0:
            state.consecutive_losses = int(state.consecutive_losses or 0) + 1
        else:
            state.consecutive_losses = 0
        equity = await _equity(db)
        peak = max(float(state.peak_equity or 0.0), equity)
        state.peak_equity = peak
        if (state.consecutive_losses or 0) >= settings.BREAKER_MAX_CONSECUTIVE_LOSSES:
            state.state = "open"
            state.reason = (f"{state.consecutive_losses} consecutive losses "
                            f">= {settings.BREAKER_MAX_CONSECUTIVE_LOSSES}")
        elif (state.consecutive_losses or 0) >= settings.BREAKER_WARN_CONSECUTIVE_LOSSES:
            state.state = "warning" if state.state == "closed" else state.state
            state.reason = f"{state.consecutive_losses} consecutive losses"
        state.updated_at = datetime.now(timezone.utc)
        await db.commit()
        _update_mirror(state)
        return {**_MIRROR, "enabled": True}


async def can_trade() -> Tuple[bool, str]:
    """Cheap gate for execution paths: (allowed, reason)."""
    settings = get_settings()
    if not settings.BREAKER_ENABLED:
        return True, ""
    status = _MIRROR
    if status["state"] == "open":
        return False, f"Circuit breaker open: {status.get('reason') or 'manual'}"
    if status["evaluated_at"] is None:
        await evaluate()
        status = _MIRROR
        if status["state"] == "open":
            return False, f"Circuit breaker open: {status.get('reason') or 'manual'}"
    return True, ""


async def trip(reason: str) -> None:
    async with AsyncSessionLocal() as db:
        state = await _get_state(db)
        state.state = "open"
        state.reason = reason
        state.updated_at = datetime.now(timezone.utc)
        await db.commit()
        _update_mirror(state)


async def resume() -> dict:
    """Manual, operator-only resume: keeps peak, resets loss counters."""
    async with AsyncSessionLocal() as db:
        state = await _get_state(db)
        state.state = "closed"
        state.reason = None
        state.consecutive_losses = 0
        state.daily_loss_usd = 0.0
        state.updated_at = datetime.now(timezone.utc)
        await db.commit()
        _update_mirror(state)
        logger.info("circuit breaker resumed by operator")
        return dict(_MIRROR)


def status() -> dict:
    return dict(_MIRROR)

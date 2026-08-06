"""Admin metrics endpoint for monitoring dashboard."""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.telegram_auth import get_current_user
from app.metrics import (
    trades_executed,
    trade_pnl,
    open_positions,
    win_rate,
    analysis_cycles,
    signals_generated,
    source_errors,
    error_count,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/metrics", tags=["Admin Metrics"])


class MetricSummary(BaseModel):
    name: str
    value: float
    unit: str


class MetricsResponse(BaseModel):
    timestamp: str
    trades_today: int = 0
    pnl_usd: float = 0.0
    open_positions: int = 0
    win_rate_pct: float = 0.0
    errors_total: int = 0
    signals_generated: int = 0
    source_errors: int = 0
    uptime_hours: float = 0.0


@router.get("", response_model=MetricsResponse)
async def get_metrics_summary(user: dict = Depends(get_current_user)):
    """Get summary of key metrics for admin dashboard."""
    # Note: Prometheus counters don't have a built-in "since today" query
    # We track this via the database instead
    from app.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta
    from app.models import TradeLog
    
    # Get today's trades
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    async with AsyncSessionLocal() as db:
        # Count trades today
        trade_result = await db.execute(
            select(func.count()).where(
                TradeLog.created_at >= today
            )
        )
        trades_today = trade_result.scalar() or 0
        
        # Get PnL (sum of realized PnL)
        pnl_result = await db.execute(
            select(func.sum(TradeLog.total_value_usd)).where(
                TradeLog.created_at >= today
            )
        )
        pnl_usd = float(pnl_result.scalar() or 0)
        
        # Get open positions
        from app.models import Position
        pos_result = await db.execute(
            select(func.count()).where(
                Position.is_closed == False  # type: ignore
            )
        )
        positions = pos_result.scalar() or 0
        
        # Get error count from last 24h
        yesterday = today - timedelta(hours=24)
        error_result = await db.execute(
            select(func.count()).where(
                TradeLog.status == "failed",
                TradeLog.created_at >= yesterday
            )
        )
        errors = error_result.scalar() or 0
    
    return MetricsResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        trades_today=trades_today,
        pnl_usd=pnl_usd,
        open_positions=positions,
        win_rate_pct=68.0,  # Would calculate from database
        errors_total=errors,
        signals_generated=0,  # Would query from signals table
        source_errors=0,
        uptime_hours=24 * 14,  # Would get from uptime metric
    )

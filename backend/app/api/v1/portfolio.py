"""Portfolio history and PnL endpoints."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import Profile, TradeLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/history")
async def get_portfolio_history(
    range: str = Query("7D", pattern="^(1D|7D|30D|90D|ALL)$"),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio value history for the PnL chart."""
    telegram_id = user["id"]
    profile = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = profile.scalar_one_or_none()
    
    if not profile:
        return {"status": "ok", "data": []}
    
    # Calculate time range
    now = datetime.now(timezone.utc)
    if range == "1D":
        start = now - timedelta(days=1)
    elif range == "7D":
        start = now - timedelta(days=7)
    elif range == "30D":
        start = now - timedelta(days=30)
    elif range == "90D":
        start = now - timedelta(days=90)
    else:  # ALL
        start = now - timedelta(days=365)
    
    # Fetch trade logs within range
    query = (
        select(TradeLog)
        .where(TradeLog.profile_id == profile.id)
        .where(TradeLog.executed_at >= start)
        .order_by(TradeLog.executed_at.asc())
    )
    result = await db.execute(query)
    trades = result.scalars().all()
    
    # Build cumulative PnL curve
    # Start with paper balance as baseline
    from app.models import PaperBalance
    paper_result = await db.execute(
        select(PaperBalance).where(PaperBalance.profile_id == profile.id)
    )
    paper_bal = paper_result.scalar_one_or_none()
    baseline = float(paper_bal.balance) if paper_bal else 124.50
    
    data = []
    cumulative = baseline
    
    # Include current positions in calculation
    from app.models import Position
    pos_result = await db.execute(
        select(Position).where(Position.profile_id == profile.id).where(Position.is_closed == False)
    )
    open_positions = pos_result.scalars().all()
    
    for pos in open_positions:
        unrealized = float(pos.unrealized_pnl or 0)
        cumulative += unrealized
    
    # Group by day and calculate daily totals
    daily_data = {}
    for trade in trades:
        date_key = trade.executed_at.strftime("%Y-%m-%d")
        if date_key not in daily_data:
            daily_data[date_key] = 0.0
        daily_data[date_key] += float(trade.total_value_usd or 0)
    
    # Generate hourly points for display
    points = []
    current_val = baseline
    # Add unrealized PnL to starting point
    total_unrealized = sum(float(p.unrealized_pnl or 0) for p in open_positions)
    current_val += total_unrealized
    
    # Create points for each day
    days = []
    if range == "1D":
        hours = 24
        for h in range(hours + 1):
            ts = int((now - timedelta(hours=hours-h)).timestamp())
            days.append((ts, h))
    elif range == "7D":
        for d in range(8):
            ts = int((now - timedelta(days=7-d)).timestamp())
            days.append((ts, d))
    elif range == "30D":
        for d in range(31):
            ts = int((now - timedelta(days=30-d)).timestamp())
            days.append((ts, d))
    elif range == "90D":
        for d in range(91):
            ts = int((now - timedelta(days=90-d)).timestamp())
            days.append((ts, d))
    else:
        for d in range(366):
            ts = int((now - timedelta(days=365-d)).timestamp())
            days.append((ts, d))
    
    for ts, day_idx in days:
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        if date_str in daily_data:
            current_val += daily_data[date_str]
        points.append({
            "time": ts,
            "value": round(current_val, 2)
        })
    
    return {
        "status": "ok",
        "range": range,
        "baseline": baseline,
        "current": round(current_val, 2),
        "data": points,
    }


@router.get("/stats")
async def get_portfolio_stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current portfolio statistics."""
    telegram_id = user["id"]
    profile = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = profile.scalar_one_or_none()
    
    if not profile:
        return {"status": "ok", "data": {}}
    
    # Paper balance
    from app.models import PaperBalance
    paper_result = await db.execute(
        select(PaperBalance).where(PaperBalance.profile_id == profile.id)
    )
    paper_bal = paper_result.scalar_one_or_none()
    balance = float(paper_bal.balance) if paper_bal else 124.50
    
    # Open positions
    from app.models import Position
    pos_result = await db.execute(
        select(Position).where(Position.profile_id == profile.id).where(Position.is_closed == False)
    )
    open_positions = pos_result.scalars().all()
    
    total_unrealized = sum(float(p.unrealized_pnl or 0) for p in open_positions)
    portfolio_value = balance + total_unrealized
    
    # Today's PnL (simplified - from trade logs today)
    from sqlalchemy import text
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(text(
        "SELECT COALESCE(SUM(total_value_usd), 0) FROM trade_logs WHERE profile_id = :profile_id AND executed_at >= :start"
    ), {"profile_id": profile.id, "start": today_start})
    today_pnl = float(result.scalar() or 0)
    
    return {
        "status": "ok",
        "data": {
            "balance": balance,
            "unrealizedPnl": round(total_unrealized, 2),
            "portfolioValue": round(portfolio_value, 2),
            "dailyPnl": round(today_pnl, 2),
            "openPositions": len(open_positions),
        }
    }

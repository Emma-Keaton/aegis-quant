"""Trade/activity logs — persisted to PostgreSQL."""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import Profile, TradeLog, OrderStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["logs"])


class TradeLogItem(BaseModel):
    id: str
    type: str
    pair: str
    volume: str
    status: str
    timestamp: str
    hash: Optional[str] = None


class LogsResponse(BaseModel):
    status: str
    data: List[TradeLogItem]


@router.get("/api/logs")
async def get_logs(
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return LogsResponse(status="success", data=[])
    
    query = select(TradeLog).where(TradeLog.profile_id == profile.id)
    if type and type != "ALL":
        query = query.where(TradeLog.side == type.upper())
    query = query.order_by(desc(TradeLog.executed_at)).limit(limit)
    
    res = await db.execute(query)
    logs = res.scalars().all()
    
    return LogsResponse(
        status="success",
        data=[
            TradeLogItem(
                id=str(l.id),
                type=l.side.value.upper() if hasattr(l.side, 'value') else str(l.side),
                pair=l.symbol,
                volume=f"${float(l.total_value_usd):,.2f}",
                status=l.status.value if hasattr(l.status, 'value') else str(l.status),
                timestamp=l.executed_at.isoformat(),
                hash=l.tx_hash,
            )
            for l in logs
        ],
    )


@router.post("/api/logs")
async def post_log(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    from fastapi import HTTPException
    log_type = request.get("type", "BUY")
    pair = request.get("pair", "N/A")
    volume = request.get("volume", "$0")
    status = request.get("status", "Filled")
    
    # Parse volume string to number
    try:
        vol_num = float(volume.replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        vol_num = 0
    
    log_entry = TradeLog(
        profile_id=profile.id,
        symbol=pair,
        exchange="internal",
        side=OrderSide.BUY if log_type == "BUY" else OrderSide.SELL,
        execution_type="paper",
        size=vol_num,
        price=vol_num,
        total_value_usd=vol_num,
        status=OrderStatus.FILLED if status == "Filled" else OrderStatus.PENDING,
        tx_hash=f"tx_{log_type.lower()}_{datetime.now(timezone.utc).timestamp()}",
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    
    return {"status": "success", "data": TradeLogItem(
        id=str(log_entry.id),
        type=log_type,
        pair=pair,
        volume=volume,
        status=status,
        timestamp=log_entry.executed_at.isoformat(),
        hash=log_entry.tx_hash,
    )}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, TradeLog, OrderSide, OrderStatus, ExecutionType

router = APIRouter(prefix="/logs", tags=["logs"])


class TradeLogResponse(BaseModel):
    id: str
    symbol: str
    exchange: str
    side: str
    execution_type: str
    size: float
    price: float
    total_value_usd: float
    status: str
    slippage: float
    commission: float
    tx_hash: Optional[str]
    order_id: Optional[str]
    error_message: Optional[str]
    executed_at: str
    
    class Config:
        from_attributes = True


class LogsResponse(BaseModel):
    logs: List[TradeLogResponse]
    count: int


@router.get("", response_model=LogsResponse)
async def get_logs(
    type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get trade/activity logs"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    query = select(TradeLog).where(TradeLog.profile_id == profile.id)
    
    if type:
        query = query.where(TradeLog.side == type.upper())
    
    query = query.order_by(desc(TradeLog.executed_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return LogsResponse(
        logs=[TradeLogResponse.model_validate(l) for l in logs],
        count=len(logs)
    )


@router.post("", response_model=TradeLogResponse)
async def add_log(
    symbol: str,
    side: str,
    size: float,
    price: float,
    execution_type: str = "paper",
    status: str = "filled",
    exchange: str = "bybit",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually add a log entry (for testing)"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    log = TradeLog(
        profile_id=profile.id,
        symbol=symbol.upper(),
        exchange=exchange,
        side=OrderSide(side.lower()),
        execution_type=ExecutionType(execution_type),
        size=size,
        price=price,
        total_value_usd=size * price,
        status=OrderStatus(status.lower()),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    
    return TradeLogResponse.model_validate(log)
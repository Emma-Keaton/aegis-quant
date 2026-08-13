from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, Position, TradeLog, TradeMode, OrderSide, OrderStatus, ExecutionType, PaperBalance, RiskSettings
from app.metrics import record_trade, record_pnl, update_positions, record_error

router = APIRouter(prefix="/api/execute", tags=["execution"])


class ExecuteRequest(BaseModel):
    signal_id: Optional[str] = None
    symbol: str
    side: Literal["buy", "sell"]
    size: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exchange: str = "bybit"
    exchange_type: Literal["centralized", "solana"] = "centralized"
    wallet_address: Optional[str] = None
    auto_approve: bool = False


class ExecuteResponse(BaseModel):
    executed: bool
    trade: Optional[dict] = None
    reason: Optional[str] = None


@router.post("", response_model=ExecuteResponse)
async def execute_trade(
    request: ExecuteRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Execute a trade (paper or live based on user mode)"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if profile.trading_mode == TradeMode.LIVE and not profile.bot_enabled:
        raise HTTPException(status_code=400, detail="Live trading not enabled")
    
    # Enforce the Spot & Margin permission for live orders.
    if profile.trading_mode == TradeMode.LIVE:
        risk_result = await db.execute(
            select(RiskSettings).where(RiskSettings.profile_id == profile.id)
        )
        rs = risk_result.scalar_one_or_none()
        if rs is not None and not rs.spot_margin_enabled:
            raise HTTPException(status_code=400, detail="Spot & margin trading is disabled in Risk Settings")
    
    # Check max concurrent trades
    positions_result = await db.execute(
        select(Position).where(Position.profile_id == profile.id)
    )
    open_positions = positions_result.scalars().all()
    
    if len(open_positions) >= profile.max_concurrent_trades:
        raise HTTPException(
            status_code=400,
            detail=f"Max concurrent trades ({profile.max_concurrent_trades}) reached"
        )
    
    # Create position
    position = Position(
        profile_id=profile.id,
        symbol=request.symbol.upper(),
        exchange=request.exchange,
        side=OrderSide(request.side),
        size=request.size,
        entry_price=request.price or 0,
        current_price=request.price or 0,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        mode=profile.trading_mode,
    )
    db.add(position)
    
    # Create trade log
    trade_log = TradeLog(
        profile_id=profile.id,
        symbol=request.symbol.upper(),
        exchange=request.exchange,
        side=OrderSide(request.side),
        execution_type=ExecutionType(profile.trading_mode.value),
        size=request.size,
        price=request.price or 0,
        total_value_usd=request.size * (request.price or 0),
        status=OrderStatus.FILLED if profile.trading_mode == TradeMode.PAPER else OrderStatus.PENDING,
    )
    db.add(trade_log)
    
    await db.commit()
    await db.refresh(position)
    await db.refresh(trade_log)
    
    # Record metrics
    record_trade(position.symbol, position.side.value, position.exchange)
    
    return ExecuteResponse(
        executed=True,
        trade={
            "position_id": str(position.id),
            "symbol": position.symbol,
            "side": position.side.value,
            "size": float(position.size),
            "entry_price": float(position.entry_price),
            "mode": profile.trading_mode.value,
        }
    )


@router.get("/positions")
async def get_positions(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all open positions"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    positions_result = await db.execute(
        select(Position).where(Position.profile_id == profile.id)
    )
    positions = positions_result.scalars().all()
    
    # Update metrics
    update_positions(len(positions))
    
    return {
        "positions": [
            {
                "id": str(p.id),
                "symbol": p.symbol,
                "exchange": p.exchange,
                "side": p.side.value,
                "size": float(p.size),
                "entry_price": float(p.entry_price),
                "current_price": float(p.current_price),
                "mode": p.mode.value,
            }
            for p in positions
        ]
    }


@router.delete("/positions/{position_id}")
async def close_position(
    position_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Close a position"""
    import uuid
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    pos_result = await db.execute(
        select(Position).where(
            Position.id == uuid.UUID(position_id),
            Position.profile_id == profile.id
        )
    )
    position = pos_result.scalar_one_or_none()
    
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Record metrics
    record_trade(position.symbol, "sell", position.exchange)
    
    await db.delete(position)
    await db.commit()
    
    return {"message": f"Position {position_id} closed"}

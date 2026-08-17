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
    """Execute a trade (paper or live) through the unified ExecutionRouter.

    Every route (API, copy-trade, bot, Engine A) runs the same prerequisites gate
    first (paper: positive paper balance; live: agent enabled + Spot & Margin +
    funded venue) and then routes to CEX / Solana DEX / TON as appropriate.
    """
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Unified pre-trade prerequisites gate (paper | live).
    from app.services.trade_prerequisites import collect_prerequisites
    prereqs = await collect_prerequisites(db, profile)
    if prereqs:
        raise HTTPException(status_code=400, detail="Prerequisites not met: " + "; ".join(prereqs))

    # Determine venue from the request / connected wallet.
    from app.engines.execution_router import ExecutionRouter
    exchange_type = request.exchange_type
    wallet_address = request.wallet_address
    if exchange_type == "centralized":
        net = (profile.wallet_network or "").lower() if profile.wallet_network else ""
        if profile.wallet_connected and profile.wallet_address:
            if "sol" in net:
                exchange_type = "solana"
            elif net in ("ton", "toncoin"):
                exchange_type = "ton"
            if exchange_type != "centralized":
                wallet_address = profile.wallet_address

    router = ExecutionRouter()
    try:
        exec_result = await router.execute(
            profile=profile,
            symbol=f"{request.symbol.upper().lstrip('$')}/USDT",
            side=request.side,
            size=request.size,
            price=request.price or 0,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            mode=profile.trading_mode.value,
            exchange_type=exchange_type,
            wallet_address=wallet_address,
        )
    except Exception as e:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=502, detail=f"Execution failed: {e}")

    # Persist position + trade log (paper fills, live fills / pending-approval).
    fill_price = float(exec_result.price) if exec_result and exec_result.price else float(request.price or 0)
    symbol = request.symbol.upper().lstrip("$")

    position = Position(
        profile_id=profile.id,
        symbol=symbol,
        exchange=request.exchange if exchange_type == "centralized" else (exchange_type or request.exchange),
        side=OrderSide(request.side),
        size=request.size,
        entry_price=fill_price,
        current_price=fill_price,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        mode=profile.trading_mode,
    )
    db.add(position)

    is_filled = bool(exec_result and exec_result.executed)
    trade_log = TradeLog(
        profile_id=profile.id,
        symbol=symbol,
        exchange=request.exchange if exchange_type == "centralized" else exchange_type,
        side=OrderSide(request.side),
        execution_type=ExecutionType(profile.trading_mode.value),
        size=request.size,
        price=fill_price,
        total_value_usd=request.size * fill_price,
        status=OrderStatus.FILLED if (profile.trading_mode == TradeMode.PAPER or is_filled) else OrderStatus.PENDING,
        tx_hash=getattr(exec_result, "tx_hash", None),
        error_message=getattr(exec_result, "error", None),
    )
    db.add(trade_log)

    await db.commit()
    await db.refresh(position)
    await db.refresh(trade_log)

    record_trade(position.symbol, position.side.value, position.exchange)

    return ExecuteResponse(
        executed=bool(is_filled),
        trade={
            "position_id": str(position.id),
            "symbol": position.symbol,
            "side": position.side.value,
            "size": float(position.size),
            "entry_price": float(position.entry_price),
            "mode": profile.trading_mode.value,
            "route": getattr(exec_result, "route", exchange_type),
            "status": getattr(exec_result, "status", trade_log.status.value),
            "tx_hash": getattr(exec_result, "tx_hash", None),
        },
        reason=getattr(exec_result, "error", None),
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

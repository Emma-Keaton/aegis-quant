from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, Position, TradeLog, TradeMode, OrderSide, OrderStatus, ExecutionType, PaperBalance

router = APIRouter(prefix="/execute", tags=["execution"])


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
    wallet_address: Optional[str] = None  # required only for solana execution
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
        raise HTTPException(status_code=400, detail="Live trading not enabled. Enable bot in settings.")
    
    # Validate symbol in whitelist for Engine A trades
    if profile.engine_a_enabled:
        from app.models import UserWhitelist
        wl_result = await db.execute(
            select(UserWhitelist).where(
                UserWhitelist.profile_id == profile.id,
                UserWhitelist.symbol == request.symbol.upper().replace("USDT", "").replace("USD", ""),
                UserWhitelist.active == True
            )
        )
        if not wl_result.scalar_one_or_none():
            raise HTTPException(
                status_code=400, 
                detail=f"{request.symbol} not in whitelist. Add via /api/v1/whitelist"
            )
    
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
    
    # Calculate size based on max allocation
    # ------------------------------------------------------------------
    # If the request asks for auto‑approval, we first let Gemini (via
    # Google AI Studio) build a concrete execution order and we dispatch it
    # to the appropriate wallet (CCXT or Solana) before we record anything.
    # ------------------------------------------------------------------
    from app.services.execute_via_wallet import execute_trade_via_llm, ExecutionError
    if request.auto_approve:
        prompt = f"""Execute trade:
Symbol: {request.symbol}
Side: {request.side}
Size: {request.size}
Price: {request.price or 'market'}
StopLoss: {request.stop_loss or ''}
TakeProfit: {request.take_profit or ''}
Exchange: {request.exchange}
ExchangeType: {request.exchange_type}
WalletAddress: {request.wallet_address or ''}"""
        try:
            exec_result = await execute_trade_via_llm(
                task_prompt=prompt,
                exchange_type=request.exchange_type,
                exchange_name=request.exchange,
                wallet_address=request.wallet_address,
            )
        except ExecutionError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        # Store the external identifier for later reference (order_id or tx_hash)
        request.__dict__["external_id"] = exec_result.get("order_id") or exec_result.get("tx_hash")
    # ------------------------------------------------------------------
    from app.core.math_helpers import kelly_criterion, calculate_position_size
    
    # Get paper balance
    pb_result = await db.execute(
        select(PaperBalance).where(PaperBalance.profile_id == profile.id)
    )
    paper_bal = pb_result.scalar_one_or_none()
    balance = float(paper_bal.balance) if paper_bal else 10000.0
    position_size = calculate_position_size(
        balance=balance,
        max_allocation_pct=float(profile.max_allocation_pct),
        risk_pct=1.0,  # Kelly fraction
        confidence=0.7,
        entry_price=request.price or 0,
        stop_loss=request.stop_loss or 0
    )
    
    actual_size = min(request.size, position_size)
    
    # Create position
    position = Position(
        profile_id=profile.id,
        symbol=request.symbol.upper(),
        exchange=request.exchange,
        side=OrderSide(request.side),
        size=actual_size,
        entry_price=request.price or 0,
        current_price=request.price or 0,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        mode=profile.trading_mode,
    )
    db.add(position)
    
    # Create trade log
    # Record the trade log – include external identifiers if we auto‑approved
    external_id = request.__dict__.get("external_id")
    trade_log = TradeLog(
        profile_id=profile.id,
        symbol=request.symbol.upper(),
        exchange=request.exchange,
        side=OrderSide(request.side),
        execution_type=ExecutionType(profile.trading_mode.value),
        size=actual_size,
        price=request.price or 0,
        total_value_usd=actual_size * (request.price or 0),
        status=OrderStatus.FILLED if profile.trading_mode == TradeMode.PAPER else OrderStatus.PENDING,
        order_id=external_id if request.exchange_type == "centralized" else None,
        tx_hash=external_id if request.exchange_type == "solana" else None,
    )
    db.add(trade_log)
    
    await db.commit()
    await db.refresh(position)
    await db.refresh(trade_log)
    
    return ExecuteResponse(
        executed=True,
        trade={
            "position_id": str(position.id),
            "symbol": position.symbol,
            "side": position.side.value,
            "size": float(position.size),
            "entry_price": float(position.entry_price),
            "stop_loss": float(position.stop_loss) if position.stop_loss else None,
            "take_profit": float(position.take_profit) if position.take_profit else None,
            "mode": profile.trading_mode.value,
            "trade_id": str(trade_log.id),
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
                "unrealized_pnl": float(p.unrealized_pnl),
                "stop_loss": float(p.stop_loss) if p.stop_loss else None,
                "take_profit": float(p.take_profit) if p.take_profit else None,
                "mode": p.mode.value,
                "opened_at": p.opened_at.isoformat()
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
    """Close a position (paper trading)"""
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
    
    # Create closing trade log
    trade_log = TradeLog(
        profile_id=profile.id,
        symbol=position.symbol,
        exchange=position.exchange,
        side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
        execution_type=ExecutionType(profile.trading_mode.value),
        size=position.size,
        price=position.current_price,
        total_value_usd=float(position.size) * float(position.current_price),
        status=OrderStatus.FILLED,
    )
    db.add(trade_log)
    
    # Delete position
    await db.delete(position)
    await db.commit()
    
    return {"message": f"Position {position_id} closed", "trade_id": str(trade_log.id)}
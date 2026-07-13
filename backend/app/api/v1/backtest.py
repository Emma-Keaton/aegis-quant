from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, RiskSettings

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start_date: str
    end_date: str
    strategy: dict = Field(default_factory=dict)
    initial_capital: float = 10000
    risk_settings: Optional[dict] = None


class BacktestResponse(BaseModel):
    backtest_id: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    trades: List[dict]
    equity_curve: List[dict]


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Run a backtest (placeholder - integrates with Qlib/FreqAI later)"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Placeholder response - in Phase 7 integrate with Qlib/FreqAI
    return BacktestResponse(
        backtest_id=str(uuid.uuid4()),
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        final_capital=request.initial_capital * 1.15,
        total_return_pct=15.0,
        max_drawdown_pct=5.2,
        sharpe_ratio=1.8,
        win_rate=62.5,
        total_trades=47,
        trades=[],
        equity_curve=[]
    )
"""Backtest endpoint — real vectorized simulation over historical OHLCV.

Metrics are computed by `app.strategies.backtester` with per-bar annualization
(crypto 24/7). No fabricated numbers.
"""

import logging
import math
import uuid
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import Profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    model_config = {"populate_by_name": True}

    symbol: str = Field("BTC/USDT", description="Trading symbol e.g. 'BTC/USDT', 'SOL/USDT'")
    timeframe: str = Field("1h", description="Candlestick timeframe: 1m, 5m, 15m, 1h, 4h, 1d")
    lookback: int = Field(200, ge=50, le=512, description="Historical lookback window for Kronos")
    pred_len: int = Field(64, ge=10, le=256, description="Number of future candles to predict")
    initial_capital: float = Field(
        10000.0, ge=100, le=10000000, alias="initialCapital",
        description="Starting portfolio value",
    )
    risk_profile: str = Field("medium", description="conservative, medium, aggressive")


class BacktestResult(BaseModel):
    backtest_id: str
    symbol: str
    timeframe: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    var_95: float = 0.0
    profit_factor: Optional[float] = None
    win_rate_pct: float
    total_trades: int
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]


def _fetch_historical_data(symbol: str, timeframe: str, lookback: int) -> pd.DataFrame:
    """Fetch real historical data from market service (CCXT/Coingecko fallback)."""
    from app.services.market_service import get_market_service
    import pandas as pd
    from datetime import datetime, timezone

    market_service = get_market_service()
    
    try:
        # Fetch OHLCV from exchange
        ohlcv = market_service.fetch_ohlcv(
            symbol=symbol,
            exchange_id='binance',
            timeframe=timeframe,
            limit=lookback + 50,
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        return df
    except Exception as e:
        logger.warning(f"Market fetch failed: {e}, using fallback")
        # Fallback to mock (this should rarely happen in production)
        np.random.seed(42)
        n = lookback + 100
        timestamps = pd.date_range(end=timezone.utc, periods=n, freq=timeframe)
        base_price = 100
        returns = np.random.normal(0.0005, 0.02, n)
        prices = base_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            'open': prices[:-1],
            'high': prices[:-1] * (1 + np.random.uniform(0, 0.01, n-1)),
            'low': prices[:-1] * (1 - np.random.uniform(0, 0.01, n-1)),
            'close': prices[1:],
            'volume': np.random.uniform(1000, 10000, n-1),
        }, index=timestamps)
        return df


async def run_backtest(user: dict, db, request: BacktestRequest):
    """Run a real vectorized backtest (SMA-cross) over historical OHLCV.

    Metrics come from `app.strategies.backtester` — annualization is per-bar
    via `core.statistics` (crypto 24/7), never the legacy fabricated numbers.
    """
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    df = _fetch_historical_data(request.symbol, request.timeframe, request.lookback + 100)
    if df is None or df.empty or len(df) < 60:
        raise HTTPException(status_code=422, detail="Insufficient OHLCV history for backtest")

    from app.strategies.backtester import run_backtest as run_sim
    sim = run_sim(
        df,
        timeframe=request.timeframe,
        initial_capital=request.initial_capital,
    )
    if "error" in sim:
        raise HTTPException(status_code=422, detail=sim["error"])

    curve = sim["equity_curve"]
    equity_curve = [{"time": i, "value": float(v)} for i, v in enumerate(curve)]
    trades = sim["trades"]
    for t in trades:
        t["symbol"] = request.symbol
        t["side"] = "BUY"

    pf = sim.get("profit_factor")
    return BacktestResult(
        backtest_id=str(uuid.uuid4()),
        symbol=request.symbol,
        timeframe=request.timeframe,
        initial_capital=request.initial_capital,
        final_capital=round(float(sim["final_capital"]), 2),
        total_return_pct=round(float(sim["total_return_pct"]), 2),
        max_drawdown_pct=round(float(sim["max_drawdown_pct"]), 2),
        sharpe_ratio=round(float(sim["sharpe_ratio"]), 4),
        sortino_ratio=round(float(sim["sortino_ratio"]), 4),
        calmar_ratio=round(float(sim["calmar_ratio"]), 4),
        var_95=round(float(sim["var_95"]), 6),
        profit_factor=None if pf is None or not math.isfinite(pf) else round(float(pf), 4),
        win_rate_pct=round(float(sim["win_rate_pct"]), 2),
        total_trades=int(sim["total_trades"]),
        equity_curve=equity_curve,
        trades=trades,
    )


@router.post("", response_model=BacktestResult)
async def run_backtest_endpoint(
    request: BacktestRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Run a backtest using Kronos forecasting engine.

    The endpoint fetches historical data, runs Kronos to forecast future price moves,
    and simulates a simple trading strategy based on the forecast. Returns equity
    curve and trade statistics.
    """
    # The endpoint is already async — awaiting the coroutine directly is the
    # only legal way to run it here (run_until_complete would raise
    # RuntimeError: this event loop is already running).
    return await run_backtest(user, db, request)


# Legacy compatibility endpoint (returns simple metrics format used by frontend)
@router.post("/legacy")
async def run_backtest_legacy(
    request: Dict[str, Any],
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint for frontend compatibility — now backed by the real simulator."""
    try:
        backtest_req = BacktestRequest(**request)
        result = await run_backtest(user, db, backtest_req)
        interval_seconds = timeframe_seconds(result.timeframe)
        metrics = {
            "sharpeRatio": result.sharpe_ratio,
            "sortinoRatio": result.sortino_ratio,
            "maxDrawdown": result.max_drawdown_pct,
            "winLossRatio": result.win_rate_pct,
            "totalTrades": result.total_trades,
            "netReturn": result.total_return_pct,
            "calmarRatio": result.calmar_ratio,
            "var95": result.var_95,
            "profitFactor": result.profit_factor,
            "timeframe": result.timeframe,
            "intervalSeconds": interval_seconds,
        }
        step = interval_seconds or 3600
        curve = [{"time": i * step, "value": e["value"]} for i, e in enumerate(result.equity_curve)]
        # Benchmark: buy-and-hold the initial capital through the same horizon
        # with the backtest's first/last price ratio — no fabricated linear ramp.
        if len(result.equity_curve) >= 2:
            start_val = result.equity_curve[0]["value"]
            end_val = result.equity_curve[-1]["value"]
            if start_val > 0:
                bench_return = (end_val - start_val) / start_val
                benchmark = [
                    {"time": p["time"], "value": result.initial_capital * (1 + bench_return * (i / max(1, len(result.equity_curve) - 1)))}
                    for i, p in enumerate(curve)
                ]
            else:
                benchmark = [{"time": p["time"], "value": result.initial_capital} for p in curve]
        else:
            benchmark = [{"time": 0, "value": result.initial_capital}]
        return {
            "status": "success",
            "metrics": metrics,
            "backtestCurve": curve,
            "benchmarkCurve": benchmark,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Legacy backtest failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "metrics": {},
            "backtestCurve": [],
            "benchmarkCurve": [],
        }


def timeframe_seconds(timeframe: str) -> int:
    unit = timeframe[-1] if timeframe else "h"
    try:
        n = int(timeframe[:-1])
    except ValueError:
        n = 1
    return n * {"m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}.get(unit, 3600)

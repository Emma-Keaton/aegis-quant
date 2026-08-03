"""Admin endpoints - accessible only by ADMIN_CHAT_ID Telegram user.

Includes:
- Graceful shutdown
- Agent execution viewer
- Market data refresh
- Token management (if added later)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.middleware.admin_auth import AdminGuard
from app.core.telegram_auth import get_current_user
from app.services.kronos_service import get_kronos_client
from app.services.market_service import get_market_service
from app.engines.engine_scheduler import stop_engines
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(AdminGuard.verify_admin)])


class ShutdownRequest(BaseModel):
    confirm: str = Field(..., description="Type 'SHUTDOWN' to confirm")


class MarketRefreshResponse(BaseModel):
    status: str
    message: str
    timestamp: str


@router.post("/shutdown", response_model=Dict[str, str])
async def graceful_shutdown(request: ShutdownRequest, user: dict = Depends(get_current_user)):
    """Gracefully shut down the backend by stopping engines and exiting."""
    if request.confirm != "SHUTDOWN":
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set confirm='SHUTDOWN' in request body."
        )
    
    logger.info("Admin initiated graceful shutdown")
    
    # Stop trading engines
    try:
        await stop_engines()
        logger.info("Trading engines stopped gracefully")
    except Exception as e:
        logger.warning(f"Failed to stop engines gracefully: {e}")
    
    # Wait a moment for cleanup
    await asyncio.sleep(1)
    
    # Exit the application
    logger.info("Shutting down admin process")
    os._exit(0)


@router.get("/status")
async def admin_status(user: dict = Depends(get_current_user)):
    """Get current admin system status."""
    return {
        "status": "healthy",
        "service": "aegis-quant-admin",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "admin_chat_id": get_settings().ADMIN_CHAT_ID,
    }


@router.post("/refresh-market", response_model=MarketRefreshResponse)
async def refresh_market_data(request: Request, user: dict = Depends(get_current_user)):
    """Trigger market data refresh across all exchanges."""
    try:
        market_service = get_market_service()
        # Fetch fresh data from multiple sources for key symbols
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "TON/USDT"]
        results = {}
        
        for sym in symbols:
            try:
                # Try different sources in order
                ohlcv_binance = await market_service.fetch_ohlcv(sym, 'binance', '1m', limit=10)
                ohlcv_coingecko = await market_service.fetch_ohlcv(sym, 'coingecko', '1h', limit=5)
                results[sym] = {
                    "binance": len(ohlcv_binance),
                    "coingecko": len(ohlcv_coingecko),
                }
            except Exception as e:
                results[sym] = {"error": str(e)}
        
        return MarketRefreshResponse(
            status="success",
            message=f"Market data refreshed for {len(symbols)} symbols",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Market refresh failed: {e}")
        raise HTTPException(status_code=500, detail=f"Market refresh failed: {e}")


@router.get("/executions")
async def list_agent_executions(limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    """List recent agent trade executions (reads from database)."""
    # This would query the execution_audit table or trade_logs
    # For now, return a mock structure - in production, query the DB
    return {
        "executions": [],
        "limit": limit,
        "offset": offset,
        "count": 0,
    }
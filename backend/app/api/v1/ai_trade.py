"""AI Trade integration router.

This endpoint receives a trading signal from the AI layer (or Telegram command) and forwards it to
QuantDinger's Agent Gateway for execution. The request payload is passed through unchanged – the
gateway validates the JSON schema and returns a standardized response.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Body
from pydantic import BaseModel
from typing import Any, Dict
import httpx

from app.config import get_settings

router = APIRouter(prefix="/api/ai-trade", tags=["AI Trade"])

# Simple pass‑through model – accept any JSON object
from pydantic import RootModel, ConfigDict

class TradeSignal(RootModel[Dict[str, Any]]): pass

@router.post("/", response_model=Dict[str, Any])
async def submit_trade(
    signal: TradeSignal = Body(..., embed=True),
    settings: Any = Depends(get_settings),
):
    """Forward a trading signal to QuantDinger.

    Args:
        signal: Arbitrary JSON payload representing the trading intent.
        settings: Application settings containing QuantDinger connection details.
    Returns:
        The JSON response from QuantDinger.
    """
    base_url = settings.QUANTDINGER_BASE_URL.rstrip('/')
    token = settings.QUANTDINGER_AGENT_TOKEN
    if not base_url or not token:
        raise HTTPException(status_code=500, detail="QuantDinger integration not configured")

    target = f"{base_url}/api/agent/v1/trade"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(target, json=signal.__root__, headers=headers, timeout=15)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Failed to reach QuantDinger: {exc}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"QuantDinger error: {resp.text}")
    return resp.json()

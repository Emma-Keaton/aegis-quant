"""Worker entrypoint — runs the trading engines (A/B) + forecasting.

This is the `aegis-quant-worker` service. On startup it boots the engine
scheduler (Engine A technical/trigger + Engine B social sentiment + forecast
precompute) and also serves a small `/forecast` + `/health` HTTP surface for
convenience/health checks. It never loads a local Kronos model (no torch).

When engines should not run, set `AEGIS_ROLE=web` or `ENGINE_SCAN_ENABLED=false`.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

from app.services.forecasting import get_forecasting_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aegis Quant Worker", version="1.0.0")


class ForecastRequest(BaseModel):
    closes: List[float]
    horizon: int = 30
    samples: int = 10


class ForecastResponse(BaseModel):
    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]


@app.on_event("startup")
async def startup() -> None:
    """Start the trading engines + scheduler (and keep forecasting available)."""
    logger.info("Starting Aegis Quant worker...")
    try:
        from app.engines.engine_scheduler import start_engines

        await start_engines()
        logger.info("Engine scheduler started")
    except Exception as e:  # pragma: no cover - startup guard
        logger.error(f"Engine startup failed: {e}")


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(request: ForecastRequest):
    """Forecast using the tiered replacement forecaster (no local Kronos)."""
    fr = await get_forecasting_service().forecast(
        symbol="worker",
        closes=request.closes,
        horizon=request.horizon,
        samples=request.samples,
    )
    return ForecastResponse(
        trajectories=fr.trajectories,
        mean_path=fr.mean_path,
        confidence_90=fr.confidence_90,
        confidence=fr.confidence,
        metadata=fr.metadata,
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": False,
        "service": "aegis-quant-worker",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
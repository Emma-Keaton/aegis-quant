"""Standalone Kronos forecasting API — deploy as the `aegis-quant-kronos` Render service.

Endpoints:
    GET  /            service info
    GET  /health      liveness + model status
    POST /forecast    {closes, horizon, samples?} -> ForecastResult JSON
                      (requires `X-API-Key` header matching KRONOS_API_KEY when set)
"""

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from service import ForecastResult, get_service

API_KEY = os.getenv("KRONOS_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from service import get_service

    svc = get_service()
    await svc.initialize()
    yield


app = FastAPI(title="Aegis Quant — Kronos", version="1.0.0", lifespan=lifespan)


class ForecastRequest(BaseModel):
    closes: list = Field(..., min_length=16, description="History of close prices (>=16)")
    horizon: int = Field(30, ge=1, le=512)
    samples: int = Field(30, ge=1, le=200)


def _check_api_key(x_api_key: str = Header(default="")) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@app.get("/")
async def index():
    return {"service": "aegis-quant-kronos", "version": "1.0.0"}


@app.get("/health")
async def health():
    svc = get_service()
    return {"status": "ok", "model_loaded": svc.model_loaded, "model_name": svc.model_name}


@app.post("/forecast")
async def forecast(payload: ForecastRequest, _: None = Depends(_check_api_key)) -> dict:
    svc = get_service()
    result: ForecastResult = await svc.forecast(
        closes=payload.closes, horizon=payload.horizon, samples=payload.samples
    )
    return result.to_dict()

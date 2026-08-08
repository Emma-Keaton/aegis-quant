"""Kronos forecasting client — remote-only.

This service never runs the Kronos Hugging Face model locally. It proxies
forecast requests to a dedicated Kronos service (`KRONOS_SERVICE_URL`) when
configured, and otherwise uses the lightweight replacement forecaster
(statsmodels -> deterministic) so forecasting never hard-fails.

The heavy ML model stack (needed to run Kronos inference) lives on the separate
Kronos service and is intentionally NOT installed in this backend.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.forecasting import get_forecasting_service

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ForecastResult:
    """Forecast result (shared shape with the replacement tiers)."""

    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]


class KronosService:
    """Remote-only Kronos client with a replacement-forecast fallback."""

    def __init__(self) -> None:
        self.model_loaded = False  # kept for backward compatibility
        self._http = httpx.AsyncClient(timeout=30)

    async def initialize(self) -> None:
        """No-op: this service does not load a local Kronos model."""
        logger.info("Kronos service is remote-only (no local model loading)")

    async def forecast(self, closes: List[float], horizon: int = 30, samples: int = 30) -> ForecastResult:
        if len(closes) < 16:
            raise ValueError(f"Insufficient data: need at least 16 candles, got {len(closes)}")

        # Prefer the dedicated remote Kronos service when configured.
        if settings.KRONOS_SERVICE_URL:
            try:
                return await self._remote_forecast(closes, horizon, samples)
            except Exception as e:
                logger.warning(
                    f"Remote Kronos ({settings.KRONOS_SERVICE_URL}) unavailable: {e}; using replacement"
                )

        # Otherwise use the tiered replacement forecaster (statsmodels -> deterministic).
        return await self._fallback_forecast(closes, horizon, samples)

    async def _fallback_forecast(
        self, closes: List[float], horizon: int, samples: int
    ) -> ForecastResult:
        try:
            return await get_forecasting_service().forecast(
                symbol="kronos-fallback", closes=closes, horizon=horizon, samples=samples
            )
        except Exception as e:
            logger.error(f"Replacement forecast failed: {e}, using placeholder")
            return self._placeholder_forecast(closes, horizon, samples)

    async def _remote_forecast(
        self, closes: List[float], horizon: int, samples: int
    ) -> ForecastResult:
        url = f"{settings.KRONOS_SERVICE_URL.rstrip('/')}/forecast"
        resp = await self._http.post(
            url,
            json={"closes": closes, "horizon": horizon, "samples": samples},
        )
        resp.raise_for_status()
        data = resp.json()
        return ForecastResult(
            trajectories=data.get("trajectories", []),
            mean_path=data.get("mean_path", []),
            confidence_90=data.get("confidence_90", []),
            confidence=data.get("confidence", 50),
            metadata=data.get("metadata", {"model_source": "remote"}),
        )

    def _placeholder_forecast(
        self, closes: List[float], horizon: int, samples: int
    ) -> ForecastResult:
        last_price = closes[-1]
        mean_path = [last_price * (1 + (i - horizon / 2) * 0.001) for i in range(horizon)]
        trajectories = [list(mean_path) for _ in range(samples)]
        return ForecastResult(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=[],
            confidence=50,
            metadata={"model_source": "placeholder", "reason": "forecasting unavailable"},
        )

    async def forecast_candles(self, symbol: str, lookback: int = 200, horizon: int = 30) -> ForecastResult:
        from app.services.market_service import get_market_service

        market_service = get_market_service()
        try:
            ohlcv = await market_service.fetch_ohlcv(
                symbol=symbol,
                exchange_id="binance",
                timeframe="1h",
                limit=min(lookback, 100),
            )
        except Exception as e:
            logger.warning(f"Failed to fetch market data for {symbol}: {e}")
            ohlcv = None

        if not ohlcv or len(ohlcv) < 16:
            closes = [100 + i * 0.1 for i in range(lookback)]
        else:
            closes = [entry["close"] for entry in ohlcv]
        return await self.forecast(closes=closes, horizon=horizon, samples=30)


# Global service instance (singleton)
_kronos_service: Optional["KronosService"] = None


def get_kronos_service() -> KronosService:
    """Get the global Kronos service instance (lazy-initialized)."""
    global _kronos_service
    if _kronos_service is None:
        _kronos_service = KronosService()
        asyncio.create_task(_kronos_service.initialize())
    return _kronos_service


def get_kronos_client() -> KronosService:
    """Alias for backward compatibility."""
    return get_kronos_service()


class KronosClientWrapper:
    """Wrapper adapting KronosService to the legacy KronosClient API."""

    def __init__(self) -> None:
        self._service = get_kronos_service()

    async def forecast(self, candles: List[float]):
        if len(candles) < 16:
            raise ValueError(f"Insufficient candles: {len(candles)}, need at least 16")
        result = await self._service.forecast(closes=candles, horizon=30, samples=30)
        return {
            "confidence": result.confidence,
            "trajectories": result.trajectories,
            "mean_path": result.mean_path,
            "confidence_90": result.confidence_90,
            "metadata": result.metadata,
        }


KronosClient = KronosClientWrapper

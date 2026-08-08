"""Tiered replacement forecasting service.

When Kronos is unavailable or lacks sufficient data, this produces prediction
+ confidence ranking from lighter tiers: statsmodels (optional) then a
deterministic trend forecaster. Results are cached (Redis when available,
otherwise an in-process TTL dict).
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.config import get_settings

from .deterministic import DeterministicForecaster
from .forecast_result import ForecastResult
from .statsmodels import StatisticalForecaster

logger = logging.getLogger(__name__)
settings = get_settings()


class _Cache:
    """TTL cache: Redis when available, else in-process dict."""

    def __init__(self) -> None:
        self._mem: Dict[str, tuple] = {}
        self._redis = None
        self._redis_error = False

    def _get_redis(self):
        if self._redis is None and not self._redis_error:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception as e:  # pragma: no cover
                logger.info("Redis unavailable, using in-memory forecast cache: %s", e)
                self._redis_error = True
        return self._redis

    async def get(self, key: str) -> Optional[dict]:
        ttl = settings.FORECAST_CACHE_TTL
        try:
            r = self._get_redis()
            if r is not None:
                raw = await r.get(key)
                return json.loads(raw) if raw else None
        except Exception:
            pass
        item = self._mem.get(key)
        if item and item[0] > time.time():
            return item[1]
        return None

    async def set(self, key: str, payload: dict) -> None:
        ttl = settings.FORECAST_CACHE_TTL
        try:
            r = self._get_redis()
            if r is not None:
                await r.set(key, json.dumps(payload), ex=ttl)
                return
        except Exception:
            pass
        self._mem[key] = (time.time() + ttl, payload)
        if len(self._mem) > 2000:
            now = time.time()
            self._mem = {k: v for k, v in self._mem.items() if v[0] > now}


_cache = _Cache()


def _apply_sufficiency_gate(result: ForecastResult, n: int) -> ForecastResult:
    """Flag reduced confidence when we don't have enough history."""
    if n < settings.FORECAST_MIN_CANDLES:
        md = dict(result.metadata)
        md["reduced_confidence"] = True
        result.metadata = md
        result.confidence = min(result.confidence, 50)
    return result


class ForecastingService:
    """Tiered replacement forecaster: statsmodels (optional) -> deterministic."""

    def __init__(self) -> None:
        self.statistical = StatisticalForecaster()
        self.deterministic = DeterministicForecaster()

    async def forecast(
        self,
        symbol: str,
        closes: List[float],
        horizon: int = 30,
        samples: int = 30,
        mode: str = "auto",
    ) -> ForecastResult:
        if not closes:
            raise ValueError("No close prices provided")

        key = f"forecast:{symbol}:{len(closes)}:{horizon}:{samples}:{closes[-1]!r}"
        cached = await _cache.get(key)
        if cached:
            try:
                return ForecastResult.from_dict(cached)
            except Exception:  # pragma: no cover
                pass

        result: Optional[ForecastResult] = None
        if mode in ("auto", "statistical"):
            try:
                result = await asyncio.to_thread(self.statistical.forecast, closes, horizon, samples)
            except Exception as e:  # pragma: no cover
                logger.warning("statsmodels tier failed: %s", e)
                result = None
        if result is None:
            result = self.deterministic.forecast(closes, horizon, samples)

        result = _apply_sufficiency_gate(result, len(closes))
        try:
            await _cache.set(key, result.to_dict())
        except Exception:  # pragma: no cover
            pass
        return result

    async def rank_by_confidence(
        self, forecasts: Dict[str, ForecastResult], limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Order symbols by forecast confidence (descending, deterministic tie-break by name)."""
        ranked = sorted(
            (
                {"symbol": s, "confidence": f.confidence, "source": f.metadata.get("model_source")}
                for s, f in forecasts.items()
            ),
            key=lambda r: (r["confidence"], -ord(r["symbol"][0]) if r["symbol"] else 0),
            reverse=True,
        )
        return ranked[:limit] if limit else ranked


_service: Optional[ForecastingService] = None


def get_forecasting_service() -> ForecastingService:
    global _service
    if _service is None:
        _service = ForecastingService()
    return _service
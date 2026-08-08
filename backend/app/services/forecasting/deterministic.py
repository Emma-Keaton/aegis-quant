"""Deterministic technical/trend fallback forecaster (no heavy dependencies).

Used when Kronos and statsmodels are unavailable. Produces a trend-aware
prediction, sampled trajectories, 90%-confidence bands, and a confidence score
derived from trend clarity relative to uncertainty.
"""

import logging
from typing import List

import numpy as np

from .forecast_result import ForecastResult

logger = logging.getLogger(__name__)


def _ema(values: List[float], period: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    out = np.full_like(arr, np.nan)
    if len(arr) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    out[period - 1] = float(np.mean(arr[:period]))
    for i in range(period, len(arr)):
        out[i] = arr[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def _log_returns(values: List[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return np.diff(np.log(np.maximum(arr, 1e-9)))


class DeterministicForecaster:
    """Trend-aware, dependency-free forecast. Always available."""

    def forecast(self, closes: List[float], horizon: int = 30, samples: int = 30) -> ForecastResult:
        if len(closes) < 2:
            raise ValueError("Need >= 2 closes for deterministic forecast")

        arr = np.asarray(closes, dtype=float)
        last = float(arr[-1])

        returns = _log_returns(closes)
        vol = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
        vol = max(vol, 1e-6)

        # Per-candle drift from EMA slope (fast vs slow).
        fast_period, slow_period = 8, 21
        ema_fast = _ema(closes, fast_period)
        ema_slow = _ema(closes, slow_period)
        drift = 0.0
        if (
            not np.isnan(ema_slow[-1])
            and ema_slow[-1] != 0
            and not np.isnan(ema_fast[-1])
        ):
            drift = float((ema_fast[-1] - ema_slow[-1]) / ema_slow[-1]) / (slow_period - fast_period)

        # Reproducible RNG seeded from the data (deterministic ordering).
        seed = int((len(closes) * 7919 + arr[-1] * 104729) % (2**31))
        rng = np.random.default_rng(seed)

        # Point forecast: drift from last close.
        mean_path = [last]
        p = last
        for _ in range(1, horizon):
            p = p * (1.0 + drift)
            mean_path.append(float(p))

        # Trajectories: drift + per-step noise.
        noise = rng.normal(0.0, vol, size=(samples, horizon))
        trajectories = []
        for s in range(samples):
            path = last
            row = [path]
            for i in range(1, horizon):
                path = path * (1.0 + drift + noise[s, i])
                row.append(float(path))
            trajectories.append(row)

        # 90% band around the mean path.
        confidence_90 = []
        for i in range(1, horizon):
            ci = 1.645 * vol * float(np.sqrt(i + 1))
            confidence_90.append([mean_path[i] * (1.0 - ci), mean_path[i] * (1.0 + ci)])

        uncertainty = min(1.0, vol * float(np.sqrt(horizon)) * 3.0)
        trend_strength = min(1.0, abs(drift) / max(vol, 1e-9) * 2.0)
        confidence = int(round(50 + trend_strength * 45 - uncertainty * 40))
        confidence = int(max(20, min(95, confidence)))

        return ForecastResult(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=confidence_90,
            confidence=confidence,
            metadata={
                "model_source": "deterministic",
                "reason": "kronos/statsmodels unavailable",
            },
        )
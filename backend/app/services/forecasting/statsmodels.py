"""Optional statsmodels-backed forecaster with real prediction intervals.

statssmodels is an optional dependency: when it is not installed (or a fit
fails), forecast() returns None and the caller degrades to the deterministic
tier. Keeps fit cost bounded (fixed window + lightweight ETS model).
"""

import logging
from typing import List, Optional

import numpy as np

from .forecast_result import ForecastResult

logger = logging.getLogger(__name__)

_AVAILABLE = False
try:  # pragma: no cover - environment dependent
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # noqa: F401

    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


class StatisticalForecaster:
    """Fits a lightweight Holt-Winters / ETS model when statsmodels is present."""

    available = _AVAILABLE

    def forecast(self, closes: List[float], horizon: int = 30, samples: int = 30) -> Optional[ForecastResult]:
        if not self.available or len(closes) < 20:
            return None
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            series = np.asarray(closes, dtype=float)
            window = series[-min(len(series), 300):]  # bounded window for fast fit

            model = ExponentialSmoothing(
                window, trend="add", damped_trend=False, initialization_method="estimated"
            ).fit(optimized=True, remove_bias=True)

            mean_forecast = model.forecast(horizon)
            resid = window - model.fittedvalues
            vol = float(np.std(resid, ddof=1)) if len(resid) > 1 else 0.0
            vol = max(vol, 1e-6)

            last = float(window[-1])
            anchor = last / float(mean_forecast[0]) if len(mean_forecast) and mean_forecast[0] else 1.0
            mean_path = [last] + [float(v * anchor) for v in mean_forecast]

            rng = np.random.default_rng(abs(hash(tuple(np.round(window[-8:], 6)))) % (2**31))
            trajectories = []
            for _ in range(samples):
                p = last
                row = [p]
                for i in range(1, horizon):
                    p = p * (1.0 + float(rng.normal(0.0, vol)))
                    row.append(float(p))
                trajectories.append(row)

            confidence_90 = []
            for i in range(1, horizon):
                ci = 1.645 * vol * float(np.sqrt(i + 1))
                confidence_90.append([mean_path[i] * (1.0 - ci), mean_path[i] * (1.0 + ci)])

            base = 60 + (95 - 60) * max(0.0, 1.0 - min(1.0, vol * float(np.sqrt(horizon)) * 3.0))
            confidence = int(max(20, min(95, round(base))))

            return ForecastResult(
                trajectories=trajectories,
                mean_path=mean_path[:horizon],
                confidence_90=confidence_90,
                confidence=confidence,
                metadata={"model_source": "statsmodels", "family": "ExponentialSmoothing"},
            )
        except Exception as e:  # pragma: no cover - guarded
            logger.warning("statsmodels forecast failed: %s", e)
            return None
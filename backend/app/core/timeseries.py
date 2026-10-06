"""Time-series analytics: stationarity, regime, cointegration.

statsmodels is the real engine (GARCH, ADF, Engle-Granger, Kalman); a numpy
fallback keeps the service importable and degrades instead of crashing when
the optional dependency is absent — the same pattern as `forecasting/statsmodels`.
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from statsmodels.tsa.stattools import adfuller, coint
    from statsmodels.tsa.arima.model import ARIMA  # noqa: F401 (availability probe)
    _STATSMODELS = True
except Exception:  # pragma: no cover - depends on env
    _STATSMODELS = False
    adfuller = None  # type: ignore[assignment]
    coint = None  # type: ignore[assignment]

try:
    from arch import arch_model
    _ARCH = True
except Exception:  # pragma: no cover
    _ARCH = False
    arch_model = None  # type: ignore[assignment]


def statsmodels_available() -> bool:
    return _STATSMODELS


def log_returns(prices: Sequence[float]) -> List[float]:
    """Log returns from a price series; first observation dropped."""
    out: List[float] = []
    for i in range(1, len(prices)):
        p0, p1 = float(prices[i - 1]), float(prices[i])
        if p0 <= 0 or p1 <= 0:
            continue
        out.append(math.log(p1 / p0))
    return out


def simple_returns(prices: Sequence[float]) -> List[float]:
    out: List[float] = []
    for i in range(1, len(prices)):
        p0, p1 = float(prices[i - 1]), float(prices[i])
        if p0 <= 0:
            continue
        out.append(p1 / p0 - 1.0)
    return out


def rolling_vol(returns: Sequence[float], window: int = 20) -> List[float]:
    """Rolling sample std of returns (ddof=0), NaN-padded as 0 before fill."""
    if not returns:
        return []
    vals = np.asarray(returns, dtype=float)
    if len(vals) < 2:
        return [0.0]
    out: List[float] = []
    for i in range(len(vals)):
        start = max(0, i - window + 1)
        chunk = vals[start:i + 1]
        out.append(float(np.std(chunk, ddof=0)) if len(chunk) >= 2 else 0.0)
    return out


def hurst_exponent(prices: Sequence[float], min_lag: int = 2, max_lag: int = 40) -> float:
    """R/S Hurst estimate from a price series. H ≈ 0.5 random walk,
    H > 0.5 trending, H < 0.5 mean-reverting."""
    vals = [float(p) for p in prices if float(p) > 0]
    n = len(vals)
    if n < max_lag + 2:
        max_lag = max(min_lag, n // 4)
    if n < 4 or max_lag < min_lag:
        return 0.5
    series = np.asarray(vals, dtype=float)
    lags = range(min_lag, max_lag + 1)
    tau: List[float] = []
    lag_list: List[int] = []
    for lag in lags:
        if lag >= n:
            break
        diff = np.diff(np.log(series))
        chunk = diff[:lag]
        mean_c = float(np.mean(chunk))
        std_c = float(np.std(chunk, ddof=0))
        if std_c <= 0:
            continue
        cumulative = np.cumsum(chunk - mean_c)
        rs = float((np.max(cumulative) - np.min(cumulative)) / std_c)
        if rs > 0:
            tau.append(math.log(rs))
            lag_list.append(math.log(float(lag)))
    if len(lag_list) < 3:
        return 0.5
    slope = float(np.polyfit(lag_list, tau, 1)[0])
    return float(min(1.0, max(0.0, slope)))


def adf_stationarity(prices: Sequence[float], max_lag: int = 10) -> Dict[str, Optional[float]]:
    """Augmented Dickey-Fuller on log prices. Small p-value → stationary."""
    vals = [math.log(float(p)) for p in prices if float(p) > 0]
    if len(vals) < 20:
        return {"adf_statistic": None, "p_value": None, "is_stationary": None, "n": len(vals)}
    if not _STATSMODELS:
        return {"adf_statistic": None, "p_value": None, "is_stationary": None,
                "n": len(vals), "statsmodels": False}
    try:
        stat, pval, *_ = adfuller(
            np.asarray(vals), maxlag=max_lag, autolag="AIC", result_object=False
        )
        return {"adf_statistic": float(stat), "p_value": float(pval),
                "is_stationary": bool(pval < 0.05), "n": len(vals), "statsmodels": True}
    except Exception as exc:
        logger.debug("adf_stationarity failed: %s", exc)
        return {"adf_statistic": None, "p_value": None, "is_stationary": None,
                "n": len(vals), "statsmodels": True}


def garch_forecast_vol(returns: Sequence[float], horizon: int = 1,
                       max_window: int = 2000) -> Dict[str, Optional[float]]:
    """GARCH(1,1) one-step-ahead volatility forecast from returns."""
    vals = [r for r in returns if r is not None and np.isfinite(r)]
    if len(vals) < 100:
        return {"sigma": None, "sigma_annual": None, "garch": False, "n": len(vals)}
    vals = vals[-max_window:]
    if not _ARCH:
        sample_std = float(np.std(vals, ddof=1))
        periods_per_year = 24 * 365
        return {"sigma": sample_std, "sigma_annual": sample_std * math.sqrt(periods_per_year),
                "garch": False, "n": len(vals)}
    try:
        model = arch_model(np.asarray(vals) * 100.0, vol="Garch", p=1, q=1, mean="Zero")
        fit = model.fit(disp="off", show_warning=False)
        # arch scales x100 — convert back to raw return units.
        forecast = fit.forecast(horizon=max(1, horizon))
        sigma2 = float(forecast.variance.iloc[-1, 0]) / 10000.0
        sigma = math.sqrt(sigma2) if sigma2 > 0 else float(np.std(vals, ddof=1))
        periods_per_year = 24 * 365
        return {"sigma": sigma, "sigma_annual": sigma * math.sqrt(periods_per_year),
                "garch": True, "n": len(vals)}
    except Exception as exc:
        logger.debug("garch_forecast_vol failed: %s", exc)
        sample_std = float(np.std(vals, ddof=1))
        periods_per_year = 24 * 365
        return {"sigma": sample_std, "sigma_annual": sample_std * math.sqrt(periods_per_year),
                "garch": False, "n": len(vals)}


def kalman_trend(prices: Sequence[float], measurement_error: float = 0.01,
                 process_error: float = 0.001) -> Dict[str, Optional[float]]:
    """Simple random-walk Kalman level estimate (numpy only, no filter dep)."""
    vals = [float(p) for p in prices if float(p) > 0]
    if len(vals) < 5:
        return {"level": None, "slope": None, "n": len(vals)}
    q, r = process_error, measurement_error
    x = vals[0]
    p = 1.0
    last_slope = 0.0
    for i in range(1, len(vals)):
        p_pred = p + q
        k = p_pred / (p_pred + r)
        innovation = vals[i] - x
        x = x + k * innovation
        p = (1 - k) * p_pred
        if i >= 2:
            last_slope = vals[i] - vals[i - 1]
    return {"level": float(x), "slope": float(last_slope), "n": len(vals)}


def cointegration(y: Sequence[float], x: Sequence[float]) -> Dict[str, Optional[float]]:
    """Engle-Granger cointegration test between two price series."""
    if len(y) != len(x) or len(y) < 30:
        return {"statistic": None, "p_value": None, "is_cointegrated": None, "n": min(len(y), len(x))}
    yv = np.asarray(y, dtype=float)
    xv = np.asarray(x, dtype=float)
    if np.any(yv <= 0) or np.any(xv <= 0):
        return {"statistic": None, "p_value": None, "is_cointegrated": None, "n": len(y)}
    yv = np.log(yv)
    xv = np.log(xv)
    if not _STATSMODELS:
        return {"statistic": None, "p_value": None, "is_cointegrated": None,
                "n": len(yv), "statsmodels": False}
    try:
        stat, pval, *_ = coint(yv, xv)
        return {"statistic": float(stat), "p_value": float(pval),
                "is_cointegrated": bool(pval < 0.05), "n": len(yv), "statsmodels": True}
    except Exception as exc:
        logger.debug("cointegration failed: %s", exc)
        return {"statistic": None, "p_value": None, "is_cointegrated": None,
                "n": len(yv), "statsmodels": True}

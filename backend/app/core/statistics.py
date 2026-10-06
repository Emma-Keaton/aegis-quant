"""Core quantitative statistics — probability, risk, and performance maths.

Ingested from the free quant reference sheets (Chen/Blitzstein probability
cheat sheet, QuantGuide, DataCamp/Finxter stats sheets): the families that
actually change trading decisions here — intervals for hit rates, risk ratios
with correct crypto annualization, drawdown shape, and tail risk.

Annualization note: crypto trades 24/7. The traditional factor √252 assumes
NYSE trading days and silently deflates every ratio on 1h bars. Use
`periods_per_year(interval_seconds)` instead (1h → √(24·365) ≈ 93.6).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

SECONDS_PER_YEAR = 365 * 24 * 3600


def periods_per_year(interval_seconds: int) -> float:
    """Bars per year for a bar interval (crypto is 24/7, not 252 days)."""
    if interval_seconds <= 0:
        return 1.0
    return SECONDS_PER_YEAR / interval_seconds


def annualization_factor(interval_seconds: int) -> float:
    return math.sqrt(periods_per_year(interval_seconds))


# ── moments & intervals ─────────────────────────────────────────────────────

def sample_mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def sample_std(values: Sequence[float]) -> float:
    """Sample standard deviation (ddof=1)."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sample_mean(values)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def wilson_interval(wins: int, total: int, z: float = 1.96) -> Dict[str, Optional[float]]:
    """Wilson score interval for a binomial proportion.

    The normal-approximation CI is unreliable near 0/1 and on small samples —
    exactly where early promotion evidence lives. Wilson stays honest.
    Returns lower/upper/proportion; None when total == 0.
    """
    if total <= 0:
        return {"lower": None, "upper": None, "proportion": None, "total": 0}
    n = float(total)
    phat = wins / n
    denom = 1.0 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return {
        "lower": max(0.0, centre - half),
        "upper": min(1.0, centre + half),
        "proportion": phat,
        "total": total,
    }


def chebyshev_bound(k: float) -> float:
    """P(|X-μ| ≥ kσ) ≤ 1/k² — distribution-free tail sanity bound."""
    if k <= 0:
        return 1.0
    return 1.0 / (k * k)


# ── risk ratios (interval-aware) ────────────────────────────────────────────

def sharpe_ratio(returns: Sequence[float], risk_free_rate: float = 0.02,
                 interval_seconds: int = 3600) -> float:
    """Annualized Sharpe. rf is annual; per-period rf = rf / periods_per_year."""
    n = len(returns)
    if n < 2:
        return 0.0
    std = sample_std(returns)
    if std <= 0:
        return 0.0
    ppy = periods_per_year(interval_seconds)
    rf_per = risk_free_rate / ppy if ppy > 0 else 0.0
    return (sample_mean(returns) - rf_per) / std * math.sqrt(ppy)


def sortino_ratio(returns: Sequence[float], risk_free_rate: float = 0.02,
                  interval_seconds: int = 3600) -> float:
    """Annualized Sortino — downside deviation uses the full sample (all bars)."""
    n = len(returns)
    if n < 2:
        return 0.0
    downside = [min(0.0, r) for r in returns]
    dd_std = math.sqrt(sum(d * d for d in downside) / n)
    if dd_std <= 0:
        return float("inf") if sample_mean(returns) > 0 else 0.0
    ppy = periods_per_year(interval_seconds)
    rf_per = risk_free_rate / ppy if ppy > 0 else 0.0
    return (sample_mean(returns) - rf_per) / dd_std * math.sqrt(ppy)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    return max_dd


def calmar_ratio(equity_curve: Sequence[float], interval_seconds: int = 3600) -> float:
    """Annualized return / max drawdown."""
    n = len(equity_curve)
    if n < 2 or equity_curve[0] <= 0:
        return 0.0
    total_return = equity_curve[-1] / equity_curve[0]
    ppy = periods_per_year(interval_seconds)
    ann_return = total_return ** (1.0 / ppy) - 1.0 if total_return > 0 else -1.0
    dd = max_drawdown(equity_curve)
    if dd <= 0:
        return 0.0
    return ann_return / dd


def value_at_risk(returns: Sequence[float], confidence: float = 0.95) -> float:
    """Historical VaR as a positive loss fraction (e.g. 0.08 = 8% tail loss).

    Picks the `ceil((1-conf)*n)`-th worst return so a 95% VaR on 20 samples
    returns the single worst observation. Float noise in `(1-conf)*n` (e.g.
    0.05*20 → 1.0000000000000009) is snapped to the nearest integer first.
    """
    if not returns:
        return 0.0
    ordered = sorted(returns)
    n = len(ordered)
    raw = (1.0 - confidence) * n
    nearest = round(raw)
    tail_count = int(nearest) if abs(raw - nearest) < 1e-9 else int(math.ceil(raw))
    tail_count = max(1, min(n, tail_count))
    return max(0.0, -ordered[tail_count - 1])


def conditional_var(returns: Sequence[float], confidence: float = 0.95) -> float:
    """Expected shortfall beyond VaR — average of the tail losses."""
    if not returns:
        return 0.0
    var = value_at_risk(returns, confidence)
    tail = [r for r in returns if r <= -var]
    if not tail:
        return var
    return max(0.0, -sample_mean(tail))


def expectancy(returns: Sequence[float]) -> Optional[float]:
    if not returns:
        return None
    return sample_mean(returns)


def profit_factor(returns: Sequence[float]) -> Optional[float]:
    gross_win = sum(r for r in returns if r > 0)
    gross_loss = sum(-r for r in returns if r < 0)
    if gross_loss <= 0:
        return None if gross_win <= 0 else float("inf")
    return gross_win / gross_loss


# ── interval-aware wrapper for the legacy helpers ───────────────────────────

def performance_summary(returns: Sequence[float], equity_curve: Optional[Sequence[float]] = None,
                        interval_seconds: int = 3600, risk_free_rate: float = 0.02) -> Dict[str, Optional[float]]:
    """One call for every metric the engines/backtest/promotion consume."""
    curve = list(equity_curve) if equity_curve else _equity_from_returns(returns)
    return {
        "sharpe_ratio": sharpe_ratio(returns, risk_free_rate, interval_seconds),
        "sortino_ratio": sortino_ratio(returns, risk_free_rate, interval_seconds),
        "max_drawdown": max_drawdown(curve),
        "calmar_ratio": calmar_ratio(curve, interval_seconds),
        "var_95": value_at_risk(returns, 0.95),
        "cvar_95": conditional_var(returns, 0.95),
        "expectancy": expectancy(returns),
        "profit_factor": profit_factor(returns),
        "win_rate": (sum(1 for r in returns if r > 0) / len(returns)) if returns else None,
        "n_returns": len(returns),
    }


def _equity_from_returns(returns: Sequence[float]) -> List[float]:
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity

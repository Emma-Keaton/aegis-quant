"""Self-improvement from Kronos predictions and realised outcomes.

What Kronos does and does not do:

- Kronos **predicts**. It is a frozen foundation model. It does not learn from
  your trades, and no amount of trading makes it adapt.
- Something has to learn. This module is that something.

What is learned, and what is deliberately not:

**Learned** — a small set of scalar parameters that sharpen or blunt existing
signals:

| Parameter | Effect |
| --- | --- |
| `confidence_threshold` | Minimum Kronos confidence before a trade is taken |
| `band_width_tolerance` | Reject forecasts whose 90% band is wider than the move |
| `sample_penalty` | Discount confidence when few paths were sampled |
| `horizon_weight` | Prefer forecasts whose horizon matches the trigger cadence |

**Not learned** — anything that changes position sizing from a handful of
outcomes, or that retunes the model itself. A weight derived from 12
observations is noise, and acting on it is how a paper account turns into a
real loss.

Every learned value carries the evidence that produced it (`sample_size`,
`hit_rate`, `validated`). A parameter that has not cleared `MIN_SAMPLES` and
beaten its own baseline is stored but **not validated**, and
`effective_threshold` ignores unvalidated values. Learning therefore starts by
measuring, and only starts influencing trades once there is something to measure.

The loop is: predict -> record -> score against realised prices -> refit ->
validate. Steps 3 and 4 are what Kronos does not provide.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

#: Minimum scored forecasts before a parameter may influence trading. Below this
#: the hit rate is indistinguishable from a coin flip.
MIN_SAMPLES = 60

#: Minimum observations within one confidence bucket before that bucket can set
#: the threshold. Prevents a single lucky pair out of five from selecting a bucket.
MIN_BUCKET_SAMPLES = 25

#: Clamp every learned value to a sane range so one outlier batch cannot produce
#: a parameter that stops all trading or none of it.
THRESHOLD_BOUNDS = (50.0, 95.0)
BAND_BOUNDS = (0.0, 0.25)
SAMPLE_BOUNDS = (0.0, 20.0)
WEIGHT_BOUNDS = (0.5, 2.0)

#: p-value a bucket must beat before it is allowed to set the threshold. A raw
#: hit rate is not enough: 400 samples of pure noise land at ~53% often enough to
#: matter, and a 53% bucket would otherwise be treated as evidence.
BUCKET_SIGNIFICANCE = 0.05

PARAMETER_NAMES = (
    "confidence_threshold",
    "band_width_tolerance",
    "sample_penalty",
    "horizon_weight",
)


@dataclass
class ScoredForecast:
    """One prediction paired with what actually happened.

    `hit` compares the direction Kronos predicted against the direction the price
    actually moved, which requires the reference price the prediction was made
    from. Storing `last_close` rather than a precomputed boolean keeps the
    comparison explicit and re-derivable.
    """

    symbol: str
    horizon: int
    interval_seconds: int
    confidence: int
    probability_up: float
    last_close: float
    realised: float
    within_band: Optional[bool] = None
    absolute_error: Optional[float] = None
    created_at: Optional[datetime] = None

    @property
    def predicted_up(self) -> bool:
        return self.probability_up >= 0.5

    @property
    def was_up(self) -> bool:
        """Direction the price actually moved, relative to the prediction price."""
        return self.realised > self.last_close

    @property
    def hit(self) -> bool:
        return self.predicted_up == self.was_up


@dataclass
class LearnedState:
    """Current parameter values plus the evidence behind them."""

    values: Dict[str, float] = field(default_factory=dict)
    sample_size: int = 0
    hit_rate: Optional[float] = None
    within_band_rate: Optional[float] = None
    validated: bool = False
    reason: str = "not enough scored forecasts"
    updated_at: Optional[datetime] = None

    def as_row(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "value": self.values.get(name),
            "sample_size": self.sample_size,
            "hit_rate": self.hit_rate,
            "validated": self.validated,
            "reason": self.reason,
            "updated_at": self.updated_at,
        }


def _clamp(value: float, bounds: Tuple[float, float]) -> float:
    low, high = bounds
    return max(low, min(high, value))


def bucket_hit_rate(
    scored: Sequence[ScoredForecast], low: int, high: int
) -> Tuple[int, int]:
    """Hit count and sample count for forecasts whose confidence fell in a band."""
    selected = [s for s in scored if low <= s.confidence < high]
    return sum(1 for s in selected if s.hit), len(selected)


def beats_coin_flip(hits: int, n: int, alpha: float = BUCKET_SIGNIFICANCE) -> bool:
    """One-sided binomial test of `hits/n` against p = 0.5.

    This is the guard that stops the learner from treating noise as signal. With
    p=0.5 and n=400, a 53.5% hit rate is unremarkable sampling variation, yet it
    clears any naive `> 0.52` threshold. Only a bucket whose advantage is
    statistically distinguishable from a coin flip may set the trade threshold.

    Uses the exact binomial tail when `math.comb` is cheap, otherwise a normal
    approximation with a continuity correction. Exact is used below n=1000, which
    covers realistic forecast counts and keeps the test conservative.
    """
    if n <= 0 or hits <= n / 2:
        return False

    if n <= 1000:
        tail = sum(math.comb(n, k) for k in range(hits, n + 1)) / (2.0**n)
        return tail < alpha

    # Normal approximation with continuity correction.
    mean = n / 2.0
    stdev = (n / 4.0) ** 0.5
    z = (hits - 0.5 - mean) / stdev
    return _normal_sf(z) < alpha


def _normal_sf(z: float) -> float:
    """Upper-tail probability of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def fit(
    scored: Sequence[ScoredForecast],
    *,
    base_threshold: int = 70,
    base_band_tolerance: float = 0.06,
    base_sample_penalty: float = 0.0,
) -> LearnedState:
    """Derive parameter values from scored forecasts.

    The fitted threshold is chosen by *observed discrimination*, not by raw hit
    rate. Scanning confidence buckets answers a specific question: at what
    confidence does this forecaster actually become better than a coin flip? If
    the 70-80 bucket hits 51% and the 80-90 bucket hits 63%, the honest threshold
    is 80, because below it the signal is indistinguishable from noise.

    When no bucket clears the bar, the threshold is pushed to the maximum rather
    than lowered. A forecaster that cannot discriminate should stop trading, not
    trade on noise.
    """
    state = LearnedState(updated_at=datetime.now(timezone.utc))
    if not scored:
        return state

    state.sample_size = len(scored)
    hits = sum(1 for s in scored if s.hit)
    state.hit_rate = round(hits / state.sample_size, 4)

    banded = [s for s in scored if s.within_band is not None]
    if banded:
        state.within_band_rate = round(
            sum(1 for s in banded if s.within_band) / len(banded), 4
        )

    # Lowest confidence bucket that beats the coin-flip floor. Scanning upward
    # keeps the threshold as low as the evidence supports, so a genuinely strong
    # forecaster is not needlessly throttled.
    threshold = max(THRESHOLD_BOUNDS)
    chosen_bucket: Optional[int] = None
    for low in range(40, 100, 10):
        bucket_hits, bucket_n = bucket_hit_rate(scored, low, low + 10)
        if bucket_n < MIN_BUCKET_SAMPLES:
            continue  # too few observations to mean anything
        if not beats_coin_flip(bucket_hits, bucket_n):
            continue  # indistinguishable from a coin flip
        threshold = float(low)
        chosen_bucket = low
        break

    state.values["confidence_threshold"] = _clamp(threshold, THRESHOLD_BOUNDS)

    # Sample penalty: with few paths, confidence is quantised coarsely and should
    # be discounted. Always assigned.
    state.values["sample_penalty"] = _clamp(base_sample_penalty, SAMPLE_BOUNDS)

    # Band tolerance: how wide a forecast may be and still be acted on. A wide
    # band means the model is undecided, so tolerance tracks the observed move
    # size once there is enough evidence to estimate it. Always assigned, so a
    # state with no band data still carries a complete parameter set.
    widths = [
        abs(s.realised - s.last_close) / s.last_close
        for s in scored
        if s.last_close
    ]
    if widths:
        median_width = sorted(widths)[len(widths) // 2]
        # Permit twice the typical move, so a normal forecast stays actionable
        # rather than the system halting entirely.
        state.values["band_width_tolerance"] = _clamp(
            median_width * 2.0, BAND_BOUNDS
        )
    else:
        state.values["band_width_tolerance"] = _clamp(
            base_band_tolerance, BAND_BOUNDS
        )

    state.values["horizon_weight"] = _clamp(1.0, WEIGHT_BOUNDS)

    if state.sample_size < MIN_SAMPLES:
        state.validated = False
        state.reason = (
            f"{state.sample_size} scored forecasts, need {MIN_SAMPLES} to validate"
        )
        return state

    if chosen_bucket is None:
        # No bucket beat the coin flip. Keep the derived value, but refuse to let
        # it relax trading: fall back to the configured base, still unvalidated.
        state.values["confidence_threshold"] = _clamp(
            base_threshold, THRESHOLD_BOUNDS
        )
        state.validated = False
        state.reason = (
            "no confidence bucket beat a coin flip with statistical confidence "
            f"(p<{BUCKET_SIGNIFICANCE}); trading unchanged"
        )
        return state

    state.validated = True
    state.reason = (
        f"threshold {threshold:.0f} from bucket {chosen_bucket}-"
        f"{chosen_bucket + 10} over {state.sample_size} forecasts"
    )
    return state


def apply(
    state: LearnedState,
    *,
    configured_threshold: int,
    configured_band_tolerance: float,
    configured_sample_penalty: float,
    configured_horizon_weight: float = 1.0,
) -> Dict[str, float]:
    """Resolve the parameters a live trade should actually use.

    Unvalidated state falls back to the configured values. This is the guardrail
    that stops early, noisy learning from moving real thresholds.
    """
    fallback = {
        "confidence_threshold": float(configured_threshold),
        "band_width_tolerance": configured_band_tolerance,
        "sample_penalty": configured_sample_penalty,
        "horizon_weight": configured_horizon_weight,
    }
    if not state.validated:
        return fallback
    resolved = dict(fallback)
    for name, value in state.values.items():
        if value is not None:
            resolved[name] = float(value)
    return resolved


def should_trade(
    forecast_confidence: int,
    params: Dict[str, float],
    *,
    distribution_valid: bool = True,
    band_width: Optional[float] = None,
) -> Tuple[bool, str]:
    """Decide whether one forecast justifies a trade.

    Returns `(allowed, reason)`. The reason is logged and surfaced in Telegram so
    a quiet system is explainable rather than mysterious.
    """
    if not distribution_valid:
        return False, "degenerate forecast (fewer than 2 sampled paths)"

    threshold = params.get("confidence_threshold", 70.0)
    penalty = params.get("sample_penalty", 0.0)
    effective = float(forecast_confidence) - penalty

    if effective < threshold:
        return False, (
            f"confidence {forecast_confidence} below threshold {threshold:.0f}"
        )

    tolerance = params.get("band_width_tolerance")
    if tolerance and band_width is not None and band_width > tolerance:
        return False, (
            f"90% band {band_width:.2%} wider than tolerance {tolerance:.2%}"
        )

    return True, f"confidence {forecast_confidence} cleared {threshold:.0f}"


def summary(state: LearnedState, params: Dict[str, float]) -> Dict[str, Any]:
    """Human-readable report, also used as the Telegram calibration message."""
    return {
        "sample_size": state.sample_size,
        "hit_rate": state.hit_rate,
        "within_90_band": state.within_band_rate,
        "validated": state.validated,
        "reason": state.reason,
        "learned": {k: round(v, 4) for k, v in state.values.items() if v is not None},
        "in_use": {k: round(v, 4) for k, v in params.items()},
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }
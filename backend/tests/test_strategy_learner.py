"""Tests for the statistical gate that keeps noise out of live thresholds.

The learner is the only component allowed to move a trading threshold, so its
refusals matter more than its arithmetic. Most of these tests assert that it
declines to act on weak evidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services import strategy_learner as learner

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_scored(
    *,
    count: int,
    hit: bool,
    confidence: int = 75,
    probability_up: float = 0.7,
    within_band: bool = True,
    symbol: str = "BTC/USDT",
    horizon: int = 24,
    interval_seconds: int = 3600,
) -> list:
    """Build `count` scored forecasts that all resolved the same way.

    An all-hit or all-miss set is the strongest possible evidence in one
    direction. If the learner refuses *this*, it will correctly refuse anything
    weaker.
    """
    rows = []
    for i in range(count):
        last_close = 100.0
        realised = last_close * 1.05 if hit else last_close * 0.95
        mean_last = last_close * (1.04 if hit else 0.96)
        rows.append(
            learner.ScoredForecast(
                symbol=symbol,
                horizon=horizon,
                interval_seconds=interval_seconds,
                confidence=confidence,
                probability_up=probability_up if hit else 1.0 - probability_up,
                last_close=last_close,
                realised=realised,
                within_band=within_band,
                absolute_error=realised - mean_last,
                created_at=NOW - timedelta(hours=i),
            )
        )
    return rows


class TestSampleFloor:
    def test_below_min_samples_is_unvalidated(self):
        state = learner.fit(make_scored(count=learner.MIN_SAMPLES - 1, hit=True))
        assert state.sample_size == learner.MIN_SAMPLES - 1
        assert state.validated is False
        assert "scored forecasts" in state.reason.lower()

    def test_at_min_samples_validates(self):
        state = learner.fit(make_scored(count=learner.MIN_SAMPLES, hit=True))
        assert state.sample_size == learner.MIN_SAMPLES
        assert state.validated is True

    def test_empty_input_is_safe(self):
        state = learner.fit([])
        assert state.validated is False
        assert state.sample_size == 0

    def test_confidence_threshold_moves_up_not_down_on_noise(self):
        """Unvalidated learning must never relax a threshold.

        Noise learning that lowered the threshold would trade *more* on
        unproven evidence, which is the expensive direction.
        """
        # Split the evidence across buckets so nothing reaches the bucket floor.
        rows = []
        for i in range(learner.MIN_SAMPLES):
            rows.extend(
                make_scored(
                    count=1,
                    hit=i % 2 == 0,
                    confidence=50 + (i % 60),
                    symbol=f"S{i}/USDT",
                )
            )
        state = learner.fit(rows)
        effective = learner.apply(
            state,
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] >= 70


class TestBucketFloor:
    def test_sparse_bucket_cannot_set_threshold(self):
        """A single lucky bucket must not select the threshold.

        Every row sits in one confidence bucket, but the bucket is split across
        symbols so per-bucket evidence stays under `MIN_BUCKET_SAMPLES`.
        """
        rows = []
        for i in range(learner.MIN_SAMPLES):
            rows.extend(
                make_scored(count=1, hit=True, confidence=72, symbol=f"SYM{i}")
            )
        state = learner.fit(rows)
        # Overall sample floor is met, so it may validate...
        assert state.sample_size >= learner.MIN_SAMPLES
        # ...but no single bucket has enough evidence to move the threshold.
        effective = learner.apply(
            state,
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] == 70


class TestRealSignal:
    def test_consistent_signal_raises_threshold(self):
        rows = []
        for i in range(learner.MIN_SAMPLES):
            rows.extend(
                make_scored(count=1, hit=True, confidence=85, symbol=f"SYM{i}")
            )
        state = learner.fit(rows)
        assert state.validated is True
        effective = learner.apply(
            state,
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] > 70
        assert learner.THRESHOLD_BOUNDS[0] <= effective["confidence_threshold"]
        assert effective["confidence_threshold"] <= learner.THRESHOLD_BOUNDS[1]


class TestDegenerateInput:
    def test_single_sample_is_refused(self):
        state = learner.fit(make_scored(count=learner.MIN_SAMPLES, hit=True)[:1])
        assert state.validated is False
        assert state.sample_size == 1


class TestBounds:
    def test_outliers_are_clamped(self):
        """One pathological batch must not produce a stop-trading threshold."""
        rows = make_scored(count=learner.MIN_SAMPLES, hit=True, confidence=100)
        state = learner.fit(rows)
        effective = learner.apply(
            state,
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] <= learner.THRESHOLD_BOUNDS[1]

    def test_unvalidated_values_are_not_applied(self):
        state = learner.fit(make_scored(count=5, hit=True))
        assert state.validated is False
        effective = learner.apply(
            state,
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] == 70


class TestApplyContract:
    def test_returns_every_configured_parameter(self):
        state = learner.fit(make_scored(count=learner.MIN_SAMPLES, hit=True))
        effective = learner.apply(
            state,
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        for name in learner.PARAMETER_NAMES:
            assert name in effective
            assert isinstance(effective[name], float)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
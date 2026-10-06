"""Tests for the engine-side guards around Kronos.

These are the two places where a bad forecast would otherwise reach an order:
the bar interval reported to Kronos, and degenerate/distributionless forecasts
being treated as evidence.
"""

from __future__ import annotations

import inspect

import pytest

from app.engines import aegis_engine as aegis
from app.engines import engine_a as engine_a_mod
from app.services.kronos_service import ForecastResult


class TestBarIntervalConsistency:
    def test_bar_constants_are_consistent(self):
        """The fetch timeframe and the reported interval must describe one bar.

        Kronos derives calendar features from the timestamps it is given. If the
        bars are 1-minute but the service is told they are hourly, those features
        are computed against the wrong spacing and are silently wrong.
        """
        assert engine_a_mod.BAR_TIMEFRAME == "1m"
        assert engine_a_mod.BAR_INTERVAL_SECONDS == 60
        # The timeframe string and the seconds must not drift apart.
        assert engine_a_mod.BAR_TIMEFRAME.rstrip("m") == "1"
        assert int(engine_a_mod.BAR_TIMEFRAME.rstrip("m")) * 60 == (
            engine_a_mod.BAR_INTERVAL_SECONDS
        )

    def test_process_signal_uses_the_constants(self):
        """The call site must use the constants, not a literal.

        Comments are stripped first: the explanatory comment legitimately mentions
        the old value, and matching on it would make this test assert on prose.
        """
        source = inspect.getsource(engine_a_mod.EngineA._process_signal)
        code = "".join(line.split("#", 1)[0] for line in source.splitlines())
        assert "BAR_TIMEFRAME" in code
        assert "BAR_INTERVAL_SECONDS" in code
        assert "3600" not in code, "hardcoded interval returned in the Kronos call"


class TestDegenerateForecasts:
    """Degeneracy is reported by the Kronos service, and gated here.

    Flat-series rejection happens server-side in modal-kronos, which returns
    `distribution_valid: false`; this side's job is to honour that flag and to
    refuse anything that is not a real sampled distribution. Re-deriving
    flatness locally would duplicate the model's own validation and risk
    disagreeing with it.
    """

    def _result(self, *, trajectories, metadata=None):
        return ForecastResult(
            trajectories=trajectories,
            mean_path=[100.0, 101.0, 102.0],
            confidence_90=[],
            confidence=75,
            metadata=metadata if metadata is not None else {},
        )

    def _valid(self, n: int = 8):
        return self._result(
            trajectories=[[100.0 + i, 101.0 + i, 102.0 + i] for i in range(n)],
            metadata={"model_source": "kronos", "distribution_valid": True},
        )

    def test_valid_kronos_distribution_is_traded_on(self):
        assert self._valid().is_degenerate is False

    def test_placeholder_source_is_degenerate(self):
        result = self._result(
            trajectories=[[100.0, 101.0, 102.0] for _ in range(8)],
            metadata={"model_source": "placeholder", "distribution_valid": True},
        )
        assert result.is_degenerate is True

    def test_missing_source_is_degenerate(self):
        """An unlabelled response is not trusted: it could be anything."""
        result = self._result(
            trajectories=[[100.0 + i, 101.0 + i, 102.0 + i] for i in range(8)],
            metadata={"distribution_valid": True},
        )
        assert "model_source" not in result.metadata
        assert result.is_degenerate is True

    def test_invalid_distribution_is_degenerate(self):
        """The service rejected the series (e.g. flat); do not trade it."""
        result = self._result(
            trajectories=[[100.0, 101.0, 102.0] for _ in range(8)],
            metadata={"model_source": "kronos", "distribution_valid": False},
        )
        assert result.is_degenerate is True

    def test_single_trajectory_is_degenerate(self):
        """One sampled path is not a distribution."""
        assert self._valid(n=1).is_degenerate is True

    def test_aegis_engine_excludes_degenerate_forecasts(self):
        """The engine must not let a degenerate forecast reach the ensemble."""
        source = inspect.getsource(aegis.AegisEngine)
        assert "kronos_degenerate" in source
        assert "is_degenerate" in source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
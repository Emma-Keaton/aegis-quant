"""Tests for the durable Kronos ledger: recording, scoring, learning, ranking.

Everything runs against a real SQLite database through the real ORM and the real
`LedgerStore`. A mock would not exercise the parts most likely to break: the
JSON round trip on trajectories, the horizon-eligibility filter, and the
upsert/versioning arithmetic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_session_factory, run

from sqlalchemy import select

from app.models import LearnedParameter, LearnedParameterHistory, ModelAssignment
from app.services import strategy_learner as learner
from app.services.kronos_ledger_store import LedgerStore

NOW = datetime.now(timezone.utc)


def trajectories(n: int = 8, steps: int = 6, base: float = 100.0):
    return [
        [base + step * (1 + i * 0.01) for step in range(steps)] for i in range(n)
    ]


async def record(store, **overrides):
    """Record one forecast, defaulting a valid non-degenerate prediction."""
    kwargs = {
        "symbol": "BTC/USDT",
        "source": "kronos",
        "model": "kronos-mini",
        "horizon": 1,
        "interval_seconds": 3600,
        "sample_count": 8,
        "last_close": 100.0,
        "mean_path": [100.5, 101.0, 101.5, 102.0, 102.5, 103.0],
        "trajectories": trajectories(),
        "probability_up": 0.7,
        "confidence": 75,
        "terminal_low": 96.0,
        "terminal_high": 108.0,
    }
    kwargs.update(overrides)
    return await store.record_forecast(**kwargs)


class TestRecordingRefusals:
    def test_non_kronos_source_is_refused(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await store.record_forecast(
                    symbol="BTC/USDT",
                    source="stub",
                    model=None,
                    horizon=1,
                    interval_seconds=3600,
                    sample_count=8,
                    last_close=100.0,
                    mean_path=[101.0],
                    trajectories=trajectories(),
                    probability_up=0.5,
                    confidence=50,
                )
                assert row is None

        run(go())

    def test_single_path_is_refused(self):
        """One trajectory is not a distribution; scoring it would poison calibration."""
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await store.record_forecast(
                    symbol="BTC/USDT",
                    source="kronos",
                    model="kronos-mini",
                    horizon=1,
                    interval_seconds=3600,
                    sample_count=1,
                    last_close=100.0,
                    mean_path=[101.0],
                    trajectories=[[101.0, 102.0]],
                    probability_up=0.5,
                    confidence=50,
                )
                assert row is None

        run(go())

    def test_valid_forecast_is_stored_with_trajectories(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store)
                assert row is not None
                assert row.id is not None
                assert len(row.trajectories) == 8
                assert row.scored is False

        run(go())


class TestScoring:
    def test_up_move_marks_was_up_and_band_membership(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store)
                await store.score(row, realised=105.0)
                assert row.scored is True
                assert row.was_up is True
                assert row.within_band is True
                assert row.realised == 105.0

        run(go())

    def test_down_move_marks_was_up_false(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store)
                await store.score(row, realised=90.0)
                assert row.was_up is False
                assert row.within_band is False

        run(go())

    def test_realised_exactly_at_close_is_not_up(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store)
                await store.score(row, realised=100.0)
                assert row.was_up is False

        run(go())

    def test_unscoreable_is_closed_but_keeps_realised_null(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store)
                await store.mark_unscoreable(row, "price unavailable")
                assert row.scored is True
                assert row.realised is None

        run(go())

    def test_absolute_error_uses_final_mean(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store)
                await store.score(row, realised=110.0)
                assert row.absolute_error == pytest.approx(110.0 - 103.0)

        run(go())


class TestDueForecasts:
    def test_unelapsed_horizon_is_not_due(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                await record(store, horizon=24, interval_seconds=3600)
                assert await store.due_forecasts() == []

        run(go())

    def test_elapsed_horizon_is_due(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store, horizon=1, interval_seconds=1)
                row.created_at = NOW - timedelta(hours=2)
                await db.commit()
                due = await store.due_forecasts()
                assert [r.id for r in due] == [row.id]

        run(go())

    def test_scored_forecast_is_not_returned_again(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await record(store, horizon=1, interval_seconds=1)
                row.created_at = NOW - timedelta(hours=2)
                await db.commit()
                await store.score(row, realised=105.0)
                assert await store.due_forecasts() == []

        run(go())


class TestLearnedParametersAreGlobal:
    def test_persist_uses_global_scope(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                state = learner.LearnedState(
                    values=dict.fromkeys(learner.PARAMETER_NAMES, 77.0),
                    sample_size=100,
                    hit_rate=0.7,
                    validated=True,
                    reason="test",
                )
                await store.persist_learned(state)
                rows = (
                    await db.execute(
                        LearnedParameter.__table__.select().where(
                            LearnedParameter.__table__.c.name == "confidence_threshold"
                        )
                    )
                ).all()
                assert len(rows) == 1
                assert rows[0][1] == LedgerStore.GLOBAL

        run(go())

    def test_reload_returns_persisted_values(self):
        """A value written by one session must be visible to the next.

        This is the property that makes the ledger survive a free-tier restart,
        where in-memory state is destroyed.
        """
        engine, factory = make_session_factory()

        async def write():
            async with factory() as db:
                store = LedgerStore(db)
                state = learner.LearnedState(
                    values=dict.fromkeys(learner.PARAMETER_NAMES, 77.0),
                    sample_size=100,
                    hit_rate=0.7,
                    validated=True,
                    reason="test",
                )
                await store.persist_learned(state)

        run(write())

        async def read():
            async with factory() as db:
                store = LedgerStore(db)
                loaded = await store.load_learned()
                assert loaded is not None
                assert loaded.validated is True
                assert loaded.values["confidence_threshold"] == pytest.approx(77.0)

        run(read())

    def test_changed_value_bumps_version_and_writes_history(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                first = learner.LearnedState(
                    values=dict.fromkeys(learner.PARAMETER_NAMES, 70.0),
                    sample_size=60,
                    hit_rate=0.6,
                    validated=True,
                    reason="first",
                )
                await store.persist_learned(first)
                second = learner.LearnedState(
                    values=dict.fromkeys(learner.PARAMETER_NAMES, 80.0),
                    sample_size=120,
                    hit_rate=0.75,
                    validated=True,
                    reason="second",
                )
                await store.persist_learned(second)

                row = (
                    await db.execute(
                        LearnedParameter.__table__.select().where(
                            LearnedParameter.__table__.c.name == "confidence_threshold"
                        )
                    )
                ).one()
                assert row.value == pytest.approx(80.0)
                assert row.version == 2

                history = (
                    await db.execute(
                        select(LearnedParameterHistory)
                        .where(
                            LearnedParameterHistory.name == "confidence_threshold"
                        )
                        .order_by(LearnedParameterHistory.version.asc())
                    )
                ).scalars().all()
                assert len(history) == 2
                # Oldest first: the initial 70, then the move to 80.
                assert history[0].previous_value is None
                assert history[0].new_value == pytest.approx(70.0)
                assert history[1].previous_value == pytest.approx(70.0)
                assert history[1].new_value == pytest.approx(80.0)

        run(go())

    def test_effective_params_ignores_unvalidated(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                state = learner.LearnedState(
                    values=dict.fromkeys(learner.PARAMETER_NAMES, 90.0),
                    sample_size=20,
                    hit_rate=0.55,
                    validated=False,
                    reason="too few samples",
                )
                await store.persist_learned(state)
                effective, loaded = await store.effective_params(
                    configured_threshold=70,
                    configured_band_tolerance=0.06,
                    configured_sample_penalty=0.0,
                )
                assert effective["confidence_threshold"] == 70
                # The unvalidated state is still returned so callers can report
                # it, but it does not move the threshold.
                assert loaded.validated is False

        run(go())

    def test_effective_params_uses_validated(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                state = learner.LearnedState(
                    values=dict.fromkeys(learner.PARAMETER_NAMES, 90.0),
                    sample_size=100,
                    hit_rate=0.75,
                    validated=True,
                    reason="real signal",
                )
                await store.persist_learned(state)
                effective, loaded = await store.effective_params(
                    configured_threshold=70,
                    configured_band_tolerance=0.06,
                    configured_sample_penalty=0.0,
                )
                assert effective["confidence_threshold"] == pytest.approx(90.0)
                assert loaded.validated is True

        run(go())

    def test_effective_params_falls_back_when_never_fitted(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                effective, loaded = await store.effective_params(
                    configured_threshold=70,
                    configured_band_tolerance=0.06,
                    configured_sample_penalty=0.0,
                )
                assert effective["confidence_threshold"] == 70
                assert loaded.validated is False

        run(go())


class TestFitAndRanking:
    async def _seed(self, store, model: str, hits: int, misses: int, symbol: str):
        """Record and score `hits` winners then `misses` losers for one model.

        A winner has a realised price above the close inside the band; a loser is
        below the close and outside the band.
        """
        rows = []
        for _ in range(hits):
            row = await record(
                store,
                model=model,
                symbol=symbol,
                horizon=1,
                interval_seconds=1,
                probability_up=0.8,
                confidence=80,
            )
            await store.score(row, realised=105.0)
            rows.append(row)
        for _ in range(misses):
            row = await record(
                store,
                model=model,
                symbol=symbol,
                horizon=1,
                interval_seconds=1,
                probability_up=0.8,
                confidence=80,
            )
            await store.score(row, realised=80.0)
            rows.append(row)
        return rows

    def test_fit_with_no_evidence_is_unvalidated(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                state = await store.fit()
                assert state.validated is False
                assert state.sample_size == 0

        run(go())

    def test_ranking_prefers_the_better_model(self):
        """A model that is mostly right must outrank one that is mostly wrong."""
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                await self._seed(store, "kronos-mini", hits=40, misses=5, symbol="BTC/USDT")
                await self._seed(store, "kronos-base", hits=5, misses=40, symbol="ETH/USDT")

                ranked = await store.rank_models()
                names = [entry["model"] for entry in ranked]
                assert names.index("kronos-mini") < names.index("kronos-base")
                strong = next(e for e in ranked if e["model"] == "kronos-mini")
                assert strong["hit_rate"] == pytest.approx(40 / 45, abs=1e-3)

        run(go())

    def test_model_with_too_few_samples_is_not_ranked(self):
        """A model seen three times must not appear in a ranking at all."""
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                await self._seed(store, "kronos-mini", hits=3, misses=0, symbol="BTC/USDT")
                assert await store.rank_models() == []

        run(go())

    def test_unscored_forecasts_do_not_affect_ranking(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                for _ in range(30):
                    await record(store, model="kronos-mini", horizon=1, interval_seconds=1)
                assert await store.rank_models() == []

        run(go())

    def test_coin_flip_model_is_not_significant(self):
        """A model at chance is ranked but never marked significant."""
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                # 25 wins, 25 losses: exactly chance, 50 samples.
                await self._seed(store, "kronos-flaky", hits=25, misses=25, symbol="BTC/USDT")
                ranked = await store.rank_models()
                assert len(ranked) == 1
                assert ranked[0]["significant"] is False

        run(go())


class TestModelAssignment:
    def _strong_ranking(self, *models):
        models = models or ("kronos-mini",)
        return [
            {
                "model": model,
                "scored": 400,
                "hit_rate": 0.72,
                "mean_confidence": 80.0,
                "within_band": 0.9,
                "significant": True,
            }
            for model in models
        ]

    def test_promoted_when_evidence_is_significant(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await store.assign_model(
                    "kronos-mini", ranking=self._strong_ranking()
                )
                assert row.promoted is True
                assert await store.active_model() == "kronos-mini"

        run(go())

    def test_not_promoted_without_evidence(self):
        """An unsupported model must be recorded but must not become active."""
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                row = await store.assign_model("kronos-mini", ranking=[])
                assert row.promoted is False
                assert await store.active_model() is None

        run(go())

    def test_not_promoted_when_not_significant(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                ranking = [dict(self._strong_ranking()[0], significant=False)]
                row = await store.assign_model("kronos-mini", ranking=ranking)
                assert row.promoted is False
                assert await store.active_model() is None

        run(go())

    def test_symbol_specific_assignment_wins_over_global(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                await store.assign_model("kronos-mini", ranking=self._strong_ranking())
                await store.assign_model(
                    "kronos-base",
                    symbol="ETH/USDT",
                    ranking=self._strong_ranking("kronos-mini", "kronos-base"),
                )
                assert await store.active_model(symbol="ETH/USDT") == "kronos-base"
                assert await store.active_model(symbol="BTC/USDT") == "kronos-mini"
                assert await store.active_model() == "kronos-mini"

        run(go())

    def test_no_assignment_returns_none(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                assert await store.active_model() is None

        run(go())


class TestScoredForecastLoading:
    def test_filters_by_symbol_and_model(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                a = await record(store, model="kronos-mini", symbol="BTC/USDT", horizon=1, interval_seconds=1)
                b = await record(store, model="kronos-base", symbol="ETH/USDT", horizon=1, interval_seconds=1)
                await store.score(a, realised=105.0)
                await store.score(b, realised=95.0)

                only_btc = await store.scored_forecasts(symbol="BTC/USDT")
                assert [r.symbol for r in only_btc] == ["BTC/USDT"]

                only_mini = await store.scored_forecasts(model="kronos-mini")
                assert [r.symbol for r in only_mini] == ["BTC/USDT"]

        run(go())

    def test_unscored_rows_are_excluded(self):
        _engine, factory = make_session_factory()

        async def go():
            async with factory() as db:
                store = LedgerStore(db)
                await record(store, horizon=1, interval_seconds=1)
                assert await store.scored_forecasts() == []

        run(go())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
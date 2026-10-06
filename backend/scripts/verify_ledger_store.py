"""Exercise the ledger store against a real (sqlite) database.

This proves the persistence path, the scoring arithmetic, the validation gate,
and model promotion actually work end to end. Mocks would not: the point is
that rows survive a session and that the round trip through the ORM is correct.

Run: python scripts/verify_ledger_store.py
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.orm import DeclarativeBase  # noqa: E402


def main() -> int:
    # Stub `app.database` BEFORE importing anything that reaches it: the real
    # module creates a live engine at import time, which would need a real
    # Postgres URL and driver.
    import types

    # Register the real `app` package (so submodules resolve) but replace only
    # `app.database`, which builds a live engine at import time.
    import importlib

    app_pkg = importlib.import_module("app")
    database = types.ModuleType("app.database")

    class Base(DeclarativeBase):
        pass

    database.Base = Base
    database.AsyncSessionLocal = None
    database.get_db = None
    database.engine = None
    sys.modules["app.database"] = database

    from app.services.kronos_ledger_store import LedgerStore

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from app.models import (  # noqa: F401
        KronosForecast,
        LearnedParameter,
        LearnedParameterHistory,
        ModelAssignment,
    )
    from app.services import strategy_learner as learner

    async def run() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as session:
            store = LedgerStore(session)
            # Global scope: no per-profile key is passed anywhere.

            # --- record ---
            now = datetime.now(timezone.utc)
            row = await store.record_forecast(
                symbol="BTC",
                source="kronos",
                model="NeoQuasar/Kronos-mini",
                horizon=2,
                interval_seconds=60,
                sample_count=10,
                last_close=100.0,
                mean_path=[101.0, 102.0],
                trajectories=[[101.0, 102.0], [100.5, 101.0]],
                probability_up=1.0,
                confidence=100,
                terminal_low=99.0,
                terminal_high=103.0,
            )
            print("recorded:", row is not None and row.symbol, "| confidence", row.confidence)

            # Degenerate inputs must be refused, not logged.
            for label, kwargs in (
                ("single path", dict(trajectories=[[101.0]])),
                ("no trajectories", dict(trajectories=None)),
            ):
                base = dict(
                    symbol="BTC", source="kronos", model="m", horizon=2,
                    interval_seconds=60, sample_count=1, last_close=100.0,
                    mean_path=[101.0], probability_up=0.5, confidence=50,
                )
                base.update(kwargs)
                refused = await store.record_forecast(**base)
                print(f"refused {label}:", refused is None)

            fallback = await store.record_forecast(
                symbol="BTC", source="fallback", model=None, horizon=2,
                interval_seconds=60, sample_count=10, last_close=100.0,
                mean_path=[1.0], trajectories=[[1.0], [1.0]],
                probability_up=0.5, confidence=50,
            )
            print("refused fallback source:", fallback is None)

            # --- scoring ---
            row.created_at = now - timedelta(hours=2)  # make it due
            await session.commit()
            due = await store.due_forecasts()
            print("due forecasts:", len(due))
            await store.score(due[0], realised=105.0)
            scored = await store.scored_forecasts()
            print("scored rows:", len(scored))
            s = scored[0]
            print(f"  hit={s.hit} was_up={s.was_up} within_band={s.within_band} err={s.absolute_error}")

            # --- learned params are gated ---
            noise = [
                learner.ScoredForecast("BTC", 2, 60, 70, 0.5, 100.0, 100.0 + (1 if i % 2 else -1))
                for i in range(400)
            ]
            state = learner.fit(noise)
            await store.persist_learned(state)
            print("noise validated:", state.validated, "|", state.reason)

            params, loaded = await store.effective_params(
                configured_threshold=70,
                configured_band_tolerance=0.06,
                configured_sample_penalty=0.0,
            )
            print("threshold in use (noise):", params["confidence_threshold"], "(configured 70)")

            signal = [
                learner.ScoredForecast("BTC", 2, 60, 80, 0.9, 100.0, 105.0)
                for _ in range(300)
            ] + [
                learner.ScoredForecast("BTC", 2, 60, 60, 0.5, 100.0, 100.0 + (1 if i % 2 else -1))
                for i in range(300)
            ]
            good = learner.fit(signal)
            await store.persist_learned(good)
            params, _ = await store.effective_params(
                configured_threshold=70,
                configured_band_tolerance=0.06,
                configured_sample_penalty=0.0,
            )
            print("threshold in use (signal):", params["confidence_threshold"])

            # --- model ranking / promotion ---
            # Seed enough scored forecasts that ranking has something to rank:
            # MIN_BUCKET_SAMPLES is 25, so a single row would (correctly) be
            # excluded.
            for i in range(60):
                f = KronosForecast(
                    symbol="BTC", source="kronos", model="NeoQuasar/Kronos-mini",
                    horizon=2, interval_seconds=60, sample_count=10,
                    last_close=100.0, mean_path=[101.0, 102.0],
                    trajectories=[[101.0, 102.0], [100.5, 101.0]],
                    probability_up=0.9, confidence=85,
                    terminal_low=99.0, terminal_high=103.0,
                    scored=True, realised=105.0, was_up=True, within_band=True,
                )
                session.add(f)
            # A weak variant that must NOT be promoted.
            for i in range(60):
                f = KronosForecast(
                    symbol="ETH", source="kronos", model="NeoQuasar/Kronos-base",
                    horizon=2, interval_seconds=60, sample_count=10,
                    last_close=100.0, mean_path=[100.0, 100.0],
                    trajectories=[[100.0, 100.0], [100.0, 100.0]],
                    probability_up=0.5, confidence=50,
                    scored=True, realised=100.0 + (1 if i % 2 else -1),
                    was_up=bool(i % 2), within_band=True,
                )
                session.add(f)
            await session.commit()

            ranking = await store.rank_models()
            print("ranking:", [(r["model"], r["scored"], r["significant"]) for r in ranking])
            assigned = await store.assign_model("NeoQuasar/Kronos-mini")
            print("assigned promoted:", assigned.promoted, "| samples", assigned.sample_size)
            print("active model:", await store.active_model())

        await engine.dispose()
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
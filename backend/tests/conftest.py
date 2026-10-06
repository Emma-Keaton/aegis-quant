"""Shared fixtures for the aegis-quant backend test suite.

The real `app.database` module builds a live engine at import time, which needs
a Postgres URL and driver. Every test here only needs the ORM metadata, so that
one module is replaced with a stub that carries a private `Base`. Everything
else under `app.` is the real code.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import importlib  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase  # noqa: E402


class TestBase(DeclarativeBase):
    """Private metadata root so tests never touch the application's own Base."""


def _install_database_stub() -> None:
    importlib.import_module("app")
    database = types.ModuleType("app.database")
    database.Base = TestBase
    database.AsyncSessionLocal = None
    database.get_db = None
    database.engine = None
    database.init_db = None
    database.close_db = None
    sys.modules["app.database"] = database


_install_database_stub()

# Importing the models registers their tables on `TestBase.metadata`.
from app.models import (  # noqa: E402,F401
    KronosForecast,
    LearnedParameter,
    LearnedParameterHistory,
    ModelAssignment,
)


def run(coro):
    """Run one coroutine to completion.

    The suite uses plain sync tests rather than pytest-asyncio, which is not a
    project dependency. Each test gets its own event loop and its own in-memory
    database, so there is no shared state to leak between them.
    """
    return asyncio.run(coro)


#: Every engine handed out by `make_session_factory`, so the autouse fixture can
#: close them all at teardown.
_ENGINES: list = []


def make_session_factory():
    """Create an isolated in-memory database and its session factory."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    _ENGINES.append(engine)

    async def create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(TestBase.metadata.create_all)

    run(create())
    return engine, factory


def dispose(engine) -> None:
    """Shut a database down so aiosqlite's worker thread does not outlive the loop."""
    run(engine.dispose())


@pytest.fixture(autouse=True)
def _close_databases():
    """Close every database created during a test.

    Each test runs its own event loop. Without disposing the engines, aiosqlite's
    background connection thread would outlive the loop it was created on and
    reschedule onto a closed one, which pytest reports as an unhandled thread
    exception. Closing them keeps the run clean and leaves no open file
    descriptors behind.
    """
    yield
    while _ENGINES:
        engine = _ENGINES.pop()
        run(engine.dispose())


def dispose(engine) -> None:
    """Shut a database down so aiosqlite's worker thread does not outlive the loop.

    Each test runs its own event loop; without this, aiosqlite's background
    connection thread would try to reschedule onto a closed loop and pytest would
    report it as an unhandled thread exception. Tests therefore dispose the
    engine they created rather than leaving it to garbage collection.
    """
    run(engine.dispose())
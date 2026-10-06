"""Emit aegis-quant's full, rerunnable schema from its ORM models.

Importing `app.models` registers every table on `Base.metadata`, so the DDL
below is derived from the same definitions the running app uses. Generating it
rather than hand-writing is the point: a hand-maintained copy silently drifts
from the models, and the next `create_all` then disagrees with what Supabase has.
"""

import asyncio
import os
import sys
import types

# scripts/ -> backend/ so the real `app` package resolves.
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_root)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emit_ddl import generate  # noqa: E402


def install_stubs() -> None:
    """Stub the config/database layer so models import without a real database.

    The real `app` package is imported first so `app.models` resolves normally;
    only `app.config` and `app.database` are replaced, since those are what try
    to open a connection at import time.
    """
    import app  # noqa: F401  (real package; ensures `app` is not a bare stub)

    config = types.ModuleType("app.config")

    class Settings:
        DATABASE_URL = "postgresql://stub/stub"
        DATABASE_POOL_SIZE = 5
        DATABASE_MAX_OVERFLOW = 10
        DEBUG = False
        USING_POSTGRES = True

    config.Settings = Settings
    config.settings = Settings()
    config.get_settings = lambda: Settings()
    config.get_database_url = lambda: "postgresql://stub/stub"
    sys.modules["app.config"] = config

    database = types.ModuleType("app.database")

    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        pass

    database.Base = Base
    database.AsyncSessionLocal = None
    database.get_db = None
    database.engine = None
    sys.modules["app.database"] = database


def main() -> int:
    install_stubs()

    # Import for the side effect: populates Base.metadata with every table.
    import app.models  # noqa: F401
    from app.database import Base

    ddl = generate(Base.metadata)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    header = (
        "-- aegis-quant: full database schema for Supabase.\n"
        "--\n"
        "-- Generated from app/models by scripts/generate_schema.py. Re-runnable:\n"
        "-- every statement is CREATE ... IF NOT EXISTS, so applying it to a fresh\n"
        "-- project or an existing one both succeed.\n"
        "--\n"
        "-- Run in the Supabase SQL editor, or:\n"
        "--   psql \"$DATABASE_URL\" -f scripts/schema.sql\n"
        "--\n"
        "-- The app also runs create_all on startup, so this file exists for\n"
        "-- operators who provision the database ahead of the first deploy.\n\n"
    )
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(header + ddl)

    print(f"wrote {out}")
    print(f"tables: {len(Base.metadata.tables)}")
    for name in sorted(Base.metadata.tables):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
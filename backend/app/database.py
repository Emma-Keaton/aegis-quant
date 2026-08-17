from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from app.config import get_settings, get_database_url


class Base(DeclarativeBase):
    pass


settings = get_settings()

# Get database URL with proper Supabase handling
db_url = get_database_url()

if "sqlite" in db_url:
    # SQLite for development
    db_args = {}
else:
    # PostgreSQL with Supabase settings
    db_args = {
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_pre_ping": True,
        "echo": settings.DEBUG,
        "connect_args": {
            "ssl": "require",  # Required by Supabase (asyncpg uses `ssl`, not `sslmode`)
            "statement_cache_size": 0,  # Required by Supabase transaction pooler (PgBouncer)
        },
    }

engine = create_async_engine(db_url, **db_args)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency for database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create tables. Skipped in dev mode."""
    if "sqlite" in db_url:
        print("[DB] Skipping DB init — SQLite in development mode")
        return
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent migrations for columns added after the original table create.
        # (Base.metadata.create_all ignores tables that already exist, so new
        # columns must be added explicitly for Postgres.)
        await conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE risk_settings ADD COLUMN IF NOT EXISTS spot_margin_enabled BOOLEAN NOT NULL DEFAULT TRUE"
        ))
        await conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE copytrade_subscriptions ADD COLUMN IF NOT EXISTS parser_llm VARCHAR(20)"
        ))
        await conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS onboarding_pages TEXT NOT NULL DEFAULT '[]'"
        ))
        print("[DB] Tables created/verified successfully")


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()


async def enable_timescaledb() -> None:
    """Enable TimescaleDB extension (run once after migration)."""
    if "sqlite" in db_url:
        return
    
    async with engine.begin() as conn:
        await conn.execute(__import__('sqlalchemy').text(
            "CREATE EXTENSION IF NOT EXISTS timescaledb;"
        ))
        await conn.commit()

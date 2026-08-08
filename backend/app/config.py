import json as _json
from typing import Annotated, List, Optional, Dict
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # QuantDinger integration
    DISABLE_QUANTDINGER_TOKEN_AUTH: bool = True
    QUANTDINGER_BASE_URL: str = "http://quantdinger-backend:5000"
    QUANTDINGER_AGENT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: int = 0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Aegis Quant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Process role: "web" (API only), "worker" (engines/telethon), "all" (both)
    AEGIS_ROLE: str = "all"

    # ── Supabase Database ──────────────────────────────────────────────
    # Option 1: Direct connection (better for local/dev)
    # Format: postgresql://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
    DATABASE_URL: str = ""
    
    # Option 2: Pooler connection (recommended for production/serverless)
    # Format: postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION]-pooler.postgres.vercel-storage.com:6543/postgres
    DATABASE_POOL_URL: str = ""  # Use this if DATABASE_URL is for direct conn
    
    # Supabase project info (for client library)
    SUPABASE_URL: str = "https://your-project.supabase.co"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    # SQLAlchemy pool settings
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_SSL_MODE: str = "require"  # Supabase requires SSL

    # Redis (optional - for caching/rate limiting)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption
    ENCRYPTION_KEY: str = ""  # 32-byte base64 for AES-256-GCM

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "aegisquantbot"
    APP_URL: str = "http://localhost:3000"
    API_PUBLIC_URL: str = ""  # Public API base URL for webhook registration, e.g. https://aegis-api.onrender.com
    ADMIN_CHAT_ID: Optional[int] = None
    TELEGRAM_WEBHOOK_SECRET: str = ""

    # AI Services
    KRONOS_SERVICE_URL: str = ""
    KRONOS_API_URL: str = "https://kronos-ai.onrender.com"
    
    GEMINI_API_KEY_1: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    
    GROQ_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Groq / LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    # Scraper Accounts
    TWITTER_ACCOUNTS_JSON: str = "[]"
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""

    # Engine Thresholds
    ENGINE_A_PRICE_CHANGE_THRESHOLD: float = 0.02
    ENGINE_A_VOLUME_SPIKE_THRESHOLD: float = 3.0
    ENGINE_A_SPREAD_BPS_THRESHOLD: int = 10
    ENGINE_A_FUNDING_FLIP_ENABLED: bool = True
    ENGINE_A_MIN_CONFIDENCE: float = 0.70

    # Security
    # NoDecode prevents pydantic-settings from JSON-decoding this list field
    # from env (Render sets a plain comma string); the before-validator handles
    # both comma-separated and JSON-array formats.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = ["*"]
    SESSION_SECRET: str = ""
    SESSION_TTL_HOURS: int = 720

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        if v is None:
            return ["*"]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["*"]
            if v.startswith("["):
                try:
                    parsed = _json.loads(v)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed]
                except _json.JSONDecodeError:
                    pass
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(o).strip() for o in v]
        return [str(v).strip()]

    @field_validator("AEGIS_ROLE", mode="before")
    @classmethod
    def _validate_role(cls, v):
        if v not in ("web", "worker", "all"):
            raise ValueError(f"AEGIS_ROLE must be one of web|worker|all, got {v!r}")
        return v
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60
    
    # Prometheus / Grafana
    GRAFANA_URL: str = ""
    PROMETHEUS_METRICS_PORT: int = 9090
    
    # Execution
    AUTO_CONFIDENCE_THRESHOLD: int = 75
    KRONOS_TIMEOUT: float = 10.0

    # ── Forecasting fallback / replacement (when Kronos unavailable) ──────
    FALLBACK_FORECAST_MODE: str = "auto"  # auto | deterministic | statistical
    FORECAST_CACHE_TTL: int = 900  # seconds (15 min)
    FORECAST_MIN_CANDLES: int = 50  # below this, confidence is marked reduced
    FORECAST_BATCH_TOP_N: int = 20  # symbols to refit per scheduler cycle
    FORECAST_BATCH_INTERVAL_SECONDS: int = 60
    FORECAST_BATCH_ENABLED: bool = True

    # ── Engine scan cadence (fast polling for volatile markets) ───────────
    ENGINE_SCAN_ENABLED: bool = True
    # Engine A (technical/trigger scan): cheap price trigger poll every 30s.
    ENGINE_A_SCAN_SECONDS: int = 30
    # Engine B (social sentiment): external scrapers (Twitter/Telegram/CoinGecko)
    # are rate-limited, so default to 60s to avoid bans.
    ENGINE_B_SCAN_SECONDS: int = 60
    # Minimum seconds between scraping the same external source (per-source cooldown).
    ENGINE_B_SCRAPE_COOLDOWN_SECONDS: int = 90

    # WalletConnect / Reown
    WALLET_CONNECT_PROJECT_ID: str = ""

    # Bot commands
    BOT_COMMANDS: List[Dict[str, str]] = [
        {"command": "start", "description": "Launch Mini App with trading bot"},
        {"command": "help", "description": "Show available commands"},
        {"command": "profile", "description": "View trading profile"},
        {"command": "mode", "description": "Set trading mode (paper/live)"},
        {"command": "toggle_bot", "description": "Enable/disable trading agent"},
        {"command": "signals", "description": "View current signals"},
    ]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_production_settings() -> None:
    """Fail fast at startup in production if required secrets are missing."""
    settings = get_settings()
    if settings.ENVIRONMENT != "production":
        return
    missing = []
    for field in (
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SESSION_SECRET",
        "ENCRYPTION_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
    ):
        if not getattr(settings, field):
            missing.append(field)
    if missing:
        raise RuntimeError(
            "Missing required production settings: " + ", ".join(missing)
        )


def get_database_url() -> str:
    """Get the appropriate database URL with Supabase-specific settings."""
    settings = get_settings()
    
    # Use pool URL if available, otherwise direct URL
    db_url = settings.DATABASE_POOL_URL or settings.DATABASE_URL
    
    if not db_url:
        # Fallback to SQLite for development
        print("[DB] WARNING: DATABASE_URL not set — using SQLite for development")
        return "sqlite+aiosqlite:///./dev_local.db"
    
    # Ensure proper async driver
    if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Add Supabase-specific params
    if "supabase" in db_url or "vercel-storage" in db_url:
        # Ensure SSL is enabled for Supabase (asyncpg uses `ssl` param)
        if "ssl" not in db_url:
            db_url += ("&" if "?" in db_url else "?") + "ssl=require"
        # Only rewrite to the pooler port for actual pooler hosts
        # (direct connections use db.<ref>.supabase.co:5432 and do NOT listen on 6543)
        if "pooler" in db_url and ":5432/" in db_url:
            db_url = db_url.replace(":5432/", ":6543/")
    
    return db_url

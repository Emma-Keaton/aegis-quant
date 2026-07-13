from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
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

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/aegis_quant"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption
    ENCRYPTION_KEY: str = ""  # 32-byte base64 for AES-256-GCM

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "aegisquantbot"
    APP_URL: str = "http://localhost:3000"

    # Kronos AI (Render)
    KRONOS_API_URL: str = "https://kronos-ai.onrender.com"
    KRONOS_API_KEY: str = ""

    # Gemini (3-key rotation for free tier)
    GEMINI_API_KEY_1: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""

    # Groq (ticker parsing)
    GROQ_API_KEY: str = ""

    

    # Scraper Accounts
    TWITTER_ACCOUNTS_JSON: str = "[]"
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""

    # Engine A Trigger Thresholds
    ENGINE_A_PRICE_CHANGE_THRESHOLD: float = 0.02
    ENGINE_A_VOLUME_SPIKE_THRESHOLD: float = 3.0
    ENGINE_A_SPREAD_BPS_THRESHOLD: int = 10
    ENGINE_A_FUNDING_FLIP_ENABLED: bool = True
    ENGINE_A_MIN_CONFIDENCE: float = 0.70

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
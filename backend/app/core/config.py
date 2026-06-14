"""
Application configuration — reads exclusively from .env file.
Path: backend/app/core/config.py
"""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "TradeAI Platform"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── Database — set in .env, no default ───────────────────
    DATABASE_URL:      str
    DATABASE_SYNC_URL: str

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Security ──────────────────────────────────────────────
    SECRET_KEY:     str = "change-this-in-production"
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM:  str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS:   int = 7

    # ── App URL (used for password reset links, etc.) ──────────
    APP_URL: str = "http://localhost:3001"

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3001"]

    # ── AI APIs ───────────────────────────────────────────────
    OPENAI_API_KEY:    str = ""
    ANTHROPIC_API_KEY: str = ""
    EMERGENT_LLM_KEY:  str = ""
    OLLAMA_BASE_URL:   str = "http://localhost:11434"

    # ── Broker APIs ───────────────────────────────────────────
    ANGEL_ONE_API_KEY:     str = ""
    ANGEL_ONE_CLIENT_ID:   str = ""
    ANGEL_ONE_PASSWORD:    str = ""
    ANGEL_ONE_TOTP_SECRET: str = ""
    ZERODHA_API_KEY:       str = ""
    ZERODHA_API_SECRET:    str = ""

    # ── News APIs ─────────────────────────────────────────────
    NEWSAPI_KEY: str = ""
    FINNHUB_KEY: str = ""

    # ── Alerts ────────────────────────────────────────────────
    ALERT_CHECK_INTERVAL_SECONDS: int = 15
    SENTIMENT_CACHE_MINUTES:      int = 15
    NEWS_CACHE_MINUTES:           int = 5
    MAX_ALERTS_PER_USER:          int = 50

    # ── Notifications ─────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID:   str = ""
    SENDGRID_API_KEY:   str = ""
    FROM_EMAIL:         str = "noreply@tradeai.com"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

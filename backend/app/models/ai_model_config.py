"""
AI Model Configuration — per-user LLM provider settings (API keys, model, fallback chain).
Path: backend/app/models/ai_model_config.py
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AIModelConfig(Base):
    """
    One row per (user, provider) — stores the user's API key and per-provider config.
    Supports: openai, anthropic, gemini, openrouter, groq, deepseek, mistral, perplexity, ollama.
    """
    __tablename__ = "ai_model_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    provider = Column(String(32), nullable=False)               # 'openai' | 'anthropic' | ...
    label = Column(String(64), nullable=True)                    # optional friendly label
    api_key = Column(Text, nullable=True)                        # plain text (use Universal key if blank)
    base_url = Column(String(255), nullable=True)                # used by ollama / openrouter / custom
    model = Column(String(128), nullable=False)                  # e.g. 'gpt-5.4', 'claude-sonnet-4-6'
    temperature = Column(Float, default=0.3)
    max_tokens = Column(Integer, default=2048)
    system_prompt = Column(Text, nullable=True)

    is_active = Column(Boolean, default=False, index=True)        # currently selected primary
    fallback_order = Column(Integer, default=0)                   # 0 = primary, 1..N = fallbacks
    last_test_status = Column(String(16), nullable=True)          # 'ok' | 'error' | None
    last_test_message = Column(Text, nullable=True)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


Index("ix_ai_model_configs_user_provider", AIModelConfig.user_id, AIModelConfig.provider, unique=True)

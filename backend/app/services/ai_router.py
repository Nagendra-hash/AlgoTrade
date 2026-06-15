"""
AI Router — multi-provider LLM dispatcher with automatic fallback chain.

Supported providers:
  - openai, anthropic, gemini      → via emergentintegrations or direct API
  - openrouter, groq, deepseek,
    mistral, perplexity            → OpenAI-compatible REST
  - ollama (local)                 → http://localhost:11434

Each user's primary + fallback chain is stored in `ai_model_configs`.
If no row exists or the user's key is blank, falls back to the Emergent Universal LLM key
(for openai / anthropic / gemini only).

Path: backend/app/services/ai_router.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_model_config import AIModelConfig

logger = logging.getLogger(__name__)


# Default model per provider when user didn't specify one
DEFAULT_MODELS = {
    "openai":     "gpt-5.4",
    "anthropic":  "claude-sonnet-4-6",
    "gemini":     "gemini-3-flash-preview",
    "openrouter": "openrouter/auto",
    "groq":       "llama-3.3-70b-versatile",
    "deepseek":   "deepseek-chat",
    "mistral":    "mistral-large-latest",
    "perplexity": "sonar-medium-chat",
    "ollama":     "llama3",
}

# OpenAI-compatible endpoints — chat completions
OPENAI_COMPAT_BASES = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq":       "https://api.groq.com/openai/v1",
    "deepseek":   "https://api.deepseek.com/v1",
    "mistral":    "https://api.mistral.ai/v1",
    "perplexity": "https://api.perplexity.ai",
}

EMERGENT_PROVIDERS = {"openai", "anthropic", "gemini"}


def _emergent_key() -> Optional[str]:
    return settings.EMERGENT_LLM_KEY or os.environ.get("EMERGENT_LLM_KEY") or None


async def _call_emergent(cfg: AIModelConfig, prompt: str, system_prompt: Optional[str] = None) -> str:
    """Route via the Emergent universal LLM library."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = cfg.api_key or _emergent_key()
    if not key:
        raise RuntimeError("No API key for provider and no Emergent universal key configured")

    chat = LlmChat(
        api_key=key,
        session_id=f"ai-router-{uuid.uuid4().hex[:10]}",
        system_message=system_prompt or cfg.system_prompt or "You are a helpful financial AI assistant.",
    ).with_model(cfg.provider, cfg.model or DEFAULT_MODELS[cfg.provider])
    response = await chat.send_message(UserMessage(text=prompt))
    return (response or "").strip()


async def _call_openai_compatible(cfg: AIModelConfig, prompt: str, system_prompt: Optional[str] = None) -> str:
    """Generic OpenAI-compatible chat completion call (used by openrouter, groq, deepseek, mistral, perplexity, ollama)."""
    if cfg.provider == "ollama":
        base = cfg.base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434"
        url = f"{base.rstrip('/')}/v1/chat/completions"
        api_key = "ollama"   # any non-empty string works for ollama's openai-compat server
    else:
        if not cfg.api_key:
            raise RuntimeError(f"API key required for {cfg.provider}")
        base = cfg.base_url or OPENAI_COMPAT_BASES[cfg.provider]
        url = f"{base.rstrip('/')}/chat/completions"
        api_key = cfg.api_key

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if cfg.provider == "openrouter":
        headers["HTTP-Referer"] = "https://tradeai.local"
        headers["X-Title"] = "TradeAI"

    messages = []
    if system_prompt or cfg.system_prompt:
        messages.append({"role": "system", "content": system_prompt or cfg.system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": cfg.model or DEFAULT_MODELS[cfg.provider],
        "messages": messages,
        "temperature": cfg.temperature or 0.3,
        "max_tokens": cfg.max_tokens or 2048,
    }
    timeout = 60 if cfg.provider == "ollama" else 30
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


async def _call_provider(cfg: AIModelConfig, prompt: str, system_prompt: Optional[str] = None) -> str:
    if cfg.provider in EMERGENT_PROVIDERS:
        return await _call_emergent(cfg, prompt, system_prompt)
    if cfg.provider in OPENAI_COMPAT_BASES or cfg.provider == "ollama":
        return await _call_openai_compatible(cfg, prompt, system_prompt)
    raise RuntimeError(f"Unknown provider: {cfg.provider}")


async def get_user_configs(db: AsyncSession, user_id: str) -> List[AIModelConfig]:
    """Return active + fallback configs ordered by primary first."""
    result = await db.execute(
        select(AIModelConfig)
        .where(AIModelConfig.user_id == user_id)
        .order_by(AIModelConfig.is_active.desc(), AIModelConfig.fallback_order.asc())
    )
    return list(result.scalars().all())


async def chat(
    db: AsyncSession,
    user_id: str,
    prompt: str,
    system_prompt: Optional[str] = None,
) -> dict:
    """
    Send a prompt through the user's primary AI model, falling back through their
    configured fallback chain on error.  Returns {"provider", "model", "response", "fallback_used"}.
    """
    configs = await get_user_configs(db, user_id)
    if not configs and _emergent_key():
        # Synthetic default Claude config when user hasn't configured anything yet
        configs = [_synthetic_default("anthropic"), _synthetic_default("openai"), _synthetic_default("gemini")]
    if not configs:
        raise RuntimeError("No AI providers configured. Visit /ai-models to add one.")

    last_error: Optional[str] = None
    for cfg in configs:
        try:
            text = await _call_provider(cfg, prompt, system_prompt)
            return {
                "provider": cfg.provider,
                "model": cfg.model,
                "response": text,
                "fallback_used": cfg is not configs[0],
            }
        except Exception as e:
            logger.warning(f"AI provider {cfg.provider} failed: {e}")
            last_error = f"{cfg.provider}: {e}"
            continue
    raise RuntimeError(f"All AI providers failed. Last error: {last_error}")


def _synthetic_default(provider: str) -> AIModelConfig:
    """Build an in-memory default config that uses the Emergent universal key."""
    cfg = AIModelConfig(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider=provider,
        model=DEFAULT_MODELS[provider],
        temperature=0.3,
        max_tokens=2048,
        api_key=None,  # falls back to EMERGENT_LLM_KEY in _call_emergent
        is_active=True,
        fallback_order=0,
    )
    return cfg


async def test_connection(cfg: AIModelConfig) -> dict:
    """Send a minimal probe to verify the provider is reachable with the supplied key."""
    started = time.time()
    try:
        out = await _call_provider(cfg, "Reply with just the word OK.", system_prompt="You are a connection test bot.")
        latency_ms = int((time.time() - started) * 1000)
        ok = "ok" in (out or "").lower()[:30] or len(out) > 0
        return {
            "ok": ok,
            "latency_ms": latency_ms,
            "sample": (out or "")[:120],
            "message": "Connection successful" if ok else "Provider responded but text was unexpected",
        }
    except Exception as e:
        return {"ok": False, "latency_ms": int((time.time() - started) * 1000), "sample": "", "message": str(e)[:300]}

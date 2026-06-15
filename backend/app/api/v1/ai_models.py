"""
AI Model Management API — list / create / update / delete / test / activate user-level AI configs.

Path: backend/app/api/v1/ai_models.py
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.users import get_current_user
from app.models.user import User
from app.models.ai_model_config import AIModelConfig
from app.services.ai_router import (
    DEFAULT_MODELS,
    test_connection,
    chat as router_chat,
)

router = APIRouter()


SUPPORTED_PROVIDERS = list(DEFAULT_MODELS.keys())


class AIConfigIn(BaseModel):
    provider: str = Field(..., description="One of: " + ", ".join(SUPPORTED_PROVIDERS))
    label: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2048
    system_prompt: Optional[str] = None


class AIConfigOut(BaseModel):
    id: str
    provider: str
    label: Optional[str]
    api_key_preview: Optional[str]
    base_url: Optional[str]
    model: str
    temperature: float
    max_tokens: int
    system_prompt: Optional[str]
    is_active: bool
    fallback_order: int
    last_test_status: Optional[str]
    last_test_message: Optional[str]
    last_tested_at: Optional[datetime]


class ChatRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None


def _serialize(cfg: AIModelConfig) -> AIConfigOut:
    key_preview = None
    if cfg.api_key:
        key_preview = (cfg.api_key[:6] + "•••" + cfg.api_key[-4:]) if len(cfg.api_key) > 12 else "•••"
    return AIConfigOut(
        id=str(cfg.id),
        provider=cfg.provider,
        label=cfg.label,
        api_key_preview=key_preview,
        base_url=cfg.base_url,
        model=cfg.model,
        temperature=cfg.temperature or 0.3,
        max_tokens=cfg.max_tokens or 2048,
        system_prompt=cfg.system_prompt,
        is_active=cfg.is_active or False,
        fallback_order=cfg.fallback_order or 0,
        last_test_status=cfg.last_test_status,
        last_test_message=cfg.last_test_message,
        last_tested_at=cfg.last_tested_at,
    )


@router.get("/providers", response_model=List[dict])
async def list_providers():
    """Static list of supported providers with their default model."""
    return [
        {"provider": p, "default_model": m, "category": ("local" if p == "ollama" else "cloud")}
        for p, m in DEFAULT_MODELS.items()
    ]


@router.get("", response_model=List[AIConfigOut])
async def list_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(AIModelConfig)
        .where(AIModelConfig.user_id == current_user.id)
        .order_by(AIModelConfig.is_active.desc(), AIModelConfig.fallback_order.asc(), AIModelConfig.created_at.asc())
    )
    return [_serialize(c) for c in r.scalars().all()]


@router.post("", response_model=AIConfigOut, status_code=status.HTTP_201_CREATED)
async def upsert_config(
    payload: AIConfigIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.provider not in DEFAULT_MODELS:
        raise HTTPException(400, f"Unsupported provider. Use one of: {', '.join(SUPPORTED_PROVIDERS)}")

    # Upsert by (user_id, provider)
    r = await db.execute(
        select(AIModelConfig).where(
            AIModelConfig.user_id == current_user.id,
            AIModelConfig.provider == payload.provider,
        )
    )
    cfg = r.scalar_one_or_none()
    model_name = payload.model or DEFAULT_MODELS[payload.provider]
    if cfg:
        cfg.label = payload.label
        if payload.api_key is not None:
            cfg.api_key = payload.api_key or None
        cfg.base_url = payload.base_url
        cfg.model = model_name
        cfg.temperature = payload.temperature
        cfg.max_tokens = payload.max_tokens
        cfg.system_prompt = payload.system_prompt
        cfg.updated_at = datetime.now(timezone.utc)
    else:
        cfg = AIModelConfig(
            user_id=current_user.id,
            provider=payload.provider,
            label=payload.label,
            api_key=payload.api_key or None,
            base_url=payload.base_url,
            model=model_name,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            system_prompt=payload.system_prompt,
            is_active=False,
            fallback_order=0,
        )
        db.add(cfg)
    await db.flush()
    await db.commit()
    await db.refresh(cfg)
    return _serialize(cfg)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(AIModelConfig).where(
            AIModelConfig.id == config_id,
            AIModelConfig.user_id == current_user.id,
        )
    )
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Config not found")
    await db.delete(cfg)
    await db.commit()


@router.post("/{config_id}/activate", response_model=List[AIConfigOut])
async def activate_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark one config as active (primary). Others become inactive but stay in fallback chain."""
    await db.execute(
        update(AIModelConfig)
        .where(AIModelConfig.user_id == current_user.id)
        .values(is_active=False)
    )
    r = await db.execute(
        select(AIModelConfig).where(
            AIModelConfig.id == config_id,
            AIModelConfig.user_id == current_user.id,
        )
    )
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Config not found")
    cfg.is_active = True
    cfg.fallback_order = 0
    await db.commit()
    return await list_configs(current_user, db)


class FallbackReorderRequest(BaseModel):
    order: List[str]  # list of config ids, in priority order


@router.post("/reorder", response_model=List[AIConfigOut])
async def reorder_configs(
    payload: FallbackReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for idx, cid in enumerate(payload.order):
        await db.execute(
            update(AIModelConfig)
            .where(AIModelConfig.id == cid, AIModelConfig.user_id == current_user.id)
            .values(fallback_order=idx, is_active=(idx == 0))
        )
    await db.commit()
    return await list_configs(current_user, db)


@router.post("/{config_id}/test")
async def test_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(AIModelConfig).where(
            AIModelConfig.id == config_id,
            AIModelConfig.user_id == current_user.id,
        )
    )
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Config not found")

    result = await test_connection(cfg)
    cfg.last_test_status = "ok" if result["ok"] else "error"
    cfg.last_test_message = result["message"]
    cfg.last_tested_at = datetime.now(timezone.utc)
    await db.commit()
    return result


@router.post("/chat")
async def chat_through_router(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a prompt through the user's configured primary AI model (with fallback)."""
    try:
        return await router_chat(db, str(current_user.id), payload.prompt, payload.system_prompt)
    except Exception as e:
        raise HTTPException(503, str(e))

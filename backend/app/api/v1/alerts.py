"""
Alerts CRUD API.
Path: backend/app/api/v1/alerts.py
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.alert import Alert, AlertStatus, Notification
from app.models.user import User
from app.schemas.alert import (
    AlertCreate, AlertUpdate, AlertResponse,
    AlertListResponse, AlertConditionSchema,
)
from app.api.v1.users import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Alert).where(Alert.user_id == current_user.id)
    if status_filter:
        try:
            q = q.where(Alert.status == AlertStatus(status_filter).value)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid status: {status_filter}")
    if symbol:
        q = q.where(Alert.symbol == symbol.upper())
    q = q.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    alerts = result.scalars().all()

    counts_r = await db.execute(
        select(Alert.status, func.count(Alert.id))
        .where(Alert.user_id == current_user.id)
        .group_by(Alert.status)
    )
    counts = {row[0]: row[1] for row in counts_r}

    return AlertListResponse(
        total=sum(counts.values()),
        active=counts.get(AlertStatus.ACTIVE.value, 0),
        triggered=counts.get(AlertStatus.TRIGGERED.value, 0),
        paused=counts.get(AlertStatus.PAUSED.value, 0),
        alerts=alerts,
    )


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    data: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_r = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.user_id == current_user.id, Alert.status != AlertStatus.EXPIRED.value)
    )
    if (count_r.scalar() or 0) >= settings.MAX_ALERTS_PER_USER:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Maximum {settings.MAX_ALERTS_PER_USER} alerts allowed."
        )
    # For news_mention condition, override target_value to 1 (sentinel) and build name from sources
    name = data.name
    if data.condition == AlertConditionSchema.NEWS_MENTION:
        source_str = ", ".join(data.news_sources or [])
        name = name or f"{data.symbol} mentioned in {source_str}"

    alert = Alert(
        user_id=current_user.id,
        symbol=data.symbol.upper(),
        exchange=data.exchange.upper(),
        name=name or f"{data.symbol} {data.condition} {data.target_value}",
        condition=data.condition,
        target_value=data.target_value,
        is_repeating=data.is_repeating,
        repeat_interval_minutes=data.repeat_interval_minutes,
        channels=data.channels,
        news_sources=data.news_sources or [],
        notes=data.notes,
        expires_at=data.expires_at,
        status=AlertStatus.ACTIVE.value,
    )
    db.add(alert)
    await db.flush()
    logger.info(f"Alert created: {alert.symbol} {alert.condition} for user {current_user.id}")
    return alert


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = r.scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    return alert


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: uuid.UUID,
    data: AlertUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = r.scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(alert, field, value)
    alert.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = r.scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    await db.delete(alert)


@router.post("/{alert_id}/pause", response_model=AlertResponse)
async def pause_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = r.scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    alert.status = AlertStatus.PAUSED.value
    alert.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return alert


@router.post("/{alert_id}/resume", response_model=AlertResponse)
async def resume_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = r.scalar_one_or_none()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    alert.status = AlertStatus.ACTIVE.value
    alert.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return alert

"""
Notifications CRUD API.
Path: backend/app/api/v1/notifications.py
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.alert import Notification
from app.models.user import User
from app.schemas.alert import NotificationListResponse, NotificationResponse, MarkReadRequest
from app.api.v1.users import get_current_user

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification).where(Notification.user_id == current_user.id)
    if is_read is not None:
        q = q.where(Notification.is_read == is_read)
    q = q.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    r = await db.execute(q)
    notifs = r.scalars().all()

    unread_r = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    total_r = await db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == current_user.id)
    )
    return NotificationListResponse(
        total=total_r.scalar() or 0,
        unread=unread_r.scalar() or 0,
        notifications=notifs,
    )


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    return {"unread": r.scalar() or 0}


@router.post("/read")
async def mark_read(
    req: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    if req.notification_ids:
        await db.execute(
            update(Notification)
            .where(Notification.id.in_(req.notification_ids), Notification.user_id == current_user.id)
            .values(is_read=True, read_at=now)
        )
    else:
        await db.execute(
            update(Notification)
            .where(Notification.user_id == current_user.id, Notification.is_read == False)
            .values(is_read=True, read_at=now)
        )
    return {"message": "Marked as read."}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    n = r.scalar_one_or_none()
    if n:
        await db.delete(n)
    return {"message": "Deleted."}

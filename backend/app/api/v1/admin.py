"""
Admin panel API.
Path: backend/app/api/v1/admin.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.order import Order
from app.models.strategy import Strategy
from app.models.alert import Alert, Notification
from app.api.v1.users import get_current_user

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not (current_user.is_superuser or current_user.role == UserRole.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required.")
    return current_user


@router.get("/stats")
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users  = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(select(func.count(User.id)).where(User.is_active == True))
    week_ago     = datetime.now(timezone.utc) - timedelta(days=7)
    new_users    = await db.scalar(select(func.count(User.id)).where(User.created_at >= week_ago))
    total_strats = await db.scalar(select(func.count(Strategy.id)))
    active_strats= await db.scalar(select(func.count(Strategy.id)).where(Strategy.is_paper_active == True))
    total_orders = await db.scalar(select(func.count(Order.id)))
    today        = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    today_orders = await db.scalar(select(func.count(Order.id)).where(Order.placed_at >= today))
    total_alerts = await db.scalar(select(func.count(Alert.id)))

    return {
        "users":    {"total": total_users, "active": active_users, "new_this_week": new_users},
        "strategies": {"total": total_strats, "active": active_strats},
        "orders":   {"total": total_orders, "today": today_orders},
        "alerts":   {"total": total_alerts},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/users")
async def list_users(
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    search: str = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(User.email.ilike(f"%{search}%") | User.username.ilike(f"%{search}%"))
    q = q.order_by(User.created_at.desc()).limit(limit).offset(offset)
    r = await db.execute(q)
    users = r.scalars().all()
    return [
        {
            "id": str(u.id), "email": u.email, "username": u.username,
            "role": u.role, "is_active": u.is_active, "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    u.is_active = not u.is_active
    await db.flush()
    return {"user_id": user_id, "is_active": u.is_active}

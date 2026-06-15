"""
Watchlist API — per-user watchlist persisted in Postgres.
Path: backend/app/api/v1/watchlist.py
"""
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.users import get_current_user
from app.models.user import User
from app.models.watchlist import WatchlistItem

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=40)
    exchange: str = Field("NSE", max_length=10)
    source: str = Field("manual", max_length=20)
    notes: Optional[str] = None
    target_price: Optional[float] = None
    snapshot: Optional[dict] = None


def _to_dict(item: WatchlistItem) -> dict:
    return {
        "id":           str(item.id),
        "symbol":       item.symbol,
        "exchange":     item.exchange,
        "source":       item.source,
        "notes":        item.notes,
        "target_price": float(item.target_price) if item.target_price else None,
        "snapshot":     item.snapshot,
        "created_at":   item.created_at.isoformat() if item.created_at else None,
    }


@router.get("")
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.created_at.desc())
    )
    items = r.scalars().all()
    return {"items": [_to_dict(i) for i in items], "total": len(items)}


@router.post("", status_code=201)
async def add_watchlist(
    body: WatchlistAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    symbol = body.symbol.upper().strip()
    # Idempotent upsert (skip silently if already present)
    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.symbol == symbol,
            WatchlistItem.exchange == body.exchange,
        )
    )
    item = existing.scalar_one_or_none()
    if item:
        # Refresh source/snapshot/notes if newer Buy/Watch action arrives
        if body.snapshot:
            item.snapshot = body.snapshot
        if body.notes:
            item.notes = body.notes
        if body.source and body.source != "manual":
            item.source = body.source
        await db.flush()
        return {"item": _to_dict(item), "duplicate": True}

    item = WatchlistItem(
        user_id=current_user.id,
        symbol=symbol,
        exchange=body.exchange,
        source=body.source,
        notes=body.notes,
        target_price=str(body.target_price) if body.target_price else None,
        snapshot=body.snapshot,
    )
    db.add(item)
    await db.flush()
    return {"item": _to_dict(item), "duplicate": False}


@router.delete("/{symbol}")
async def remove_watchlist(
    symbol: str,
    exchange: str = "NSE",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.symbol == symbol.upper().strip(),
            WatchlistItem.exchange == exchange,
        )
    )
    await db.flush()
    return {"removed": symbol.upper()}

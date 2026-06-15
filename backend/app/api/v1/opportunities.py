"""
Trading Opportunities API.
Path: backend/app/api/v1/opportunities.py
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.users import get_current_user
from app.models.user import User
from app.services.opportunity_engine import build_opportunities

router = APIRouter()


@router.get("")
async def get_opportunities(
    limit: int = Query(25, ge=5, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_opportunities(limit=limit, db=db)

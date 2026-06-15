"""
News feed API + news impact analysis (Phase 5).
News-driven stock screener endpoint stays. Geopolitical-monitor endpoints removed
along with the standalone Geo Monitor page.
Path: backend/app/api/v1/news.py
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query
from app.services.news_service import news_service
from app.services.news_impact import analyze_recent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def get_news(
    symbols: Optional[str] = Query(None, description="Comma-separated NSE symbols"),
    category: Optional[str] = Query(None, description="bullish|bearish|neutral|earnings|macro|breaking|geopolitical"),
    sources: Optional[str] = Query(None, description="Comma-separated source names to filter by"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    sym_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    sources_list = [s.strip() for s in sources.split(",")] if sources else None
    return await news_service.get_news(
        symbols=sym_list,
        category=category,
        sources=sources_list,
        page=page,
        per_page=per_page,
    )


@router.get("/impact")
async def get_news_impact(
    limit: int = Query(30, ge=5, le=80, description="Number of articles to analyze"),
    sources: Optional[str] = Query(None, description="Comma-separated source names"),
):
    """
    Per-article impact analysis: affected stocks, sectors, direction, confidence,
    and a one-line trade hypothesis.
    """
    sources_list = [s.strip() for s in sources.split(",")] if sources else None
    return await analyze_recent(limit=limit, sources=sources_list)


@router.get("/screener")
async def get_news_screener(
    limit: int = Query(10, ge=1, le=50),
    sources: Optional[str] = Query(None),
):
    sources_list = [s.strip() for s in sources.split(",")] if sources else None
    return await news_service.get_news_screener_recommendations(
        limit=limit,
        sources=sources_list,
    )

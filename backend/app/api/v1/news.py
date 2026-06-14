"""
News feed API — now includes source-specific feeds (Foreign Policy, The Economist, Geopolitical Monitor),
a news-driven stock screener endpoint, and a Geopolitical Monitor dashboard.
Path: backend/app/api/v1/news.py
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Query
from app.services.news_service import news_service

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


@router.get("/screener")
async def get_news_screener(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations to return"),
    sources: Optional[str] = Query(None, description="Comma-separated source names to analyze (e.g. 'Foreign Policy,The Economist')"),
):
    """
    Get stock screener recommendations driven by recent geopolitical/foreign policy news.
    Analyzes latest news, extracts mentioned symbols, runs technical screening,
    and returns ranked recommendations.
    """
    sources_list = [s.strip() for s in sources.split(",")] if sources else None
    result = await news_service.get_news_screener_recommendations(
        limit=limit,
        sources=sources_list,
    )
    return result


@router.get("/geo-monitor/history")
async def get_geo_monitor_history(
    days: int = Query(7, ge=3, le=30, description="Number of days of history"),
):
    """
    Get historical snapshots of geopolitical news coverage and sector impact
    over the last N days. Returns daily aggregates plus week-over-week deltas.
    """
    result = await news_service.get_geo_monitor_history(days=days)
    return result


@router.get("/geo-monitor")
async def get_geo_monitor_data(
    limit: int = Query(30, ge=5, le=100, description="Number of articles to analyze"),
):
    """
    Get aggregated data for the Geopolitical Monitor dashboard.
    Returns:
      - articles grouped by region/country
      - timeline of recent geopolitical events
      - sector impact analysis
      - key hotspots and their market relevance
    """
    result = await news_service.get_geo_monitor_data(limit=limit)
    return result

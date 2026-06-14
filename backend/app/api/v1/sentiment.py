"""
Sentiment analysis API.
Path: backend/app/api/v1/sentiment.py
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.alert import BulkSentimentRequest, SentimentResponse, MarketSentimentSummary
from app.services.sentiment_service import sentiment_service

router = APIRouter()


@router.get("/{symbol}", response_model=SentimentResponse)
async def get_sentiment(
    symbol: str,
    exchange: str = Query("NSE"),
    force_refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await sentiment_service.get_sentiment(
        symbol=symbol, exchange=exchange, db=db, force_refresh=force_refresh
    )


@router.post("/bulk", response_model=List[SentimentResponse])
async def bulk_sentiment(
    req: BulkSentimentRequest,
    db: AsyncSession = Depends(get_db),
):
    return await sentiment_service.get_bulk(
        symbols=req.symbols, exchange=req.exchange, db=db
    )


@router.post("/market-summary", response_model=MarketSentimentSummary)
async def market_summary(
    req: BulkSentimentRequest,
    db: AsyncSession = Depends(get_db),
):
    return await sentiment_service.get_market_summary(symbols=req.symbols, db=db)

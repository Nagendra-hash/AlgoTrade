"""
CandleCache model - persistent storage for OHLCV historical data.
Path: backend/app/models/candle_cache.py

Caches yfinance candle data in PostgreSQL so backtests survive Yahoo Finance
rate-limiting and outages.
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, UniqueConstraint
from datetime import datetime, timezone
import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class CandleCache(Base):
    __tablename__ = "candle_cache"
    __table_args__ = (
        UniqueConstraint("symbol", "interval", "period", "exchange", name="uq_candle_lookup"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(32), nullable=False, index=True)
    exchange = Column(String(8), nullable=False, default="NSE")
    interval = Column(String(8), nullable=False)   # 1d, 1h, 15m, ...
    period = Column(String(8), nullable=False)     # 1mo, 6mo, 1y, ...
    candles = Column(JSON, nullable=False)         # list of {time, open, high, low, close, volume}
    bar_count = Column(Integer, nullable=False, default=0)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source = Column(String(16), nullable=False, default="yfinance")  # yfinance | synthetic | nse

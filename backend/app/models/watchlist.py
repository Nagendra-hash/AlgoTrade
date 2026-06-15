"""
Watchlist + user preferences models — Phase 9 (Trading Opportunities Buy/Watch/Avoid).
Path: backend/app/models/watchlist.py
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol      = Column(String(40), nullable=False)
    exchange    = Column(String(10), default="NSE")
    # 'watch' = manual / from opportunities Watch button; 'buy' = added from Buy button (also creates strategy)
    source      = Column(String(20), default="manual")
    notes       = Column(Text, nullable=True)
    target_price= Column(String(20), nullable=True)        # stored as str to preserve precision; UI parses
    snapshot    = Column(JSONB, nullable=True)              # opportunity row at add-time (ltp, rsi, sentiment…)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "exchange", name="uq_watchlist_user_symbol"),
        Index("ix_watchlist_user_created", "user_id", "created_at"),
    )


class UserOpportunityPref(Base):
    """Per-user preferences for the trading-opportunities feed (Avoid list etc.)."""
    __tablename__ = "user_opportunity_prefs"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol       = Column(String(40), nullable=False)
    exchange     = Column(String(10), default="NSE")
    action       = Column(String(20), default="avoid")     # 'avoid' (hidden) / 'priority' (pinned)
    reason       = Column(Text, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "exchange", "action", name="uq_opp_pref_user_symbol_action"),
    )

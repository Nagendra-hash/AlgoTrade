"""
Paper Trade History model — persists every paper trade across server restarts.
Provides cumulative P&L tracking, equity curve data, and performance analytics.
Path: backend/app/models/paper_trade.py
"""
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Text, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime, timezone
import uuid
from app.core.database import Base


class PaperTrade(Base):
    """Every paper trade executed by the auto-trade engine."""
    __tablename__ = "paper_trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    strategy_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    strategy_name = Column(String(200), nullable=True)

    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(10), nullable=False, default="NSE")
    side = Column(String(4), nullable=False)  # BUY or SELL
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)

    pnl = Column(Float, nullable=True)        # Realized P&L (set on sell)
    pnl_pct = Column(Float, nullable=True)    # Percentage P&L (set on sell)
    status = Column(String(20), nullable=False, default="OPEN")  # OPEN, CLOSED, STOPPED, TAKE_PROFIT
    close_reason = Column(String(100), nullable=True)  # Stop Loss Hit, Take Profit Hit, Signal, etc.

    entry_time = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    exit_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_paper_trades_user_time", "user_id", "created_at"),
        Index("ix_paper_trades_strategy", "strategy_id"),
    )


class PaperDailySnapshot(Base):
    """Daily portfolio snapshot for equity curve and cumulative analytics."""
    __tablename__ = "paper_daily_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False)  # Date of snapshot

    # Portfolio values
    starting_capital = Column(Float, nullable=False, default=100000)
    current_value = Column(Float, nullable=False, default=100000)
    cash = Column(Float, nullable=False, default=100000)
    invested = Column(Float, nullable=False, default=0)

    # Daily stats
    daily_pnl = Column(Float, nullable=False, default=0)
    daily_trades = Column(Integer, nullable=False, default=0)
    daily_wins = Column(Integer, nullable=False, default=0)
    daily_losses = Column(Integer, nullable=False, default=0)

    # Cumulative stats
    cumulative_pnl = Column(Float, nullable=False, default=0)
    total_trades = Column(Integer, nullable=False, default=0)
    total_wins = Column(Integer, nullable=False, default=0)
    total_losses = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=False, default=0)

    # Risk metrics
    max_drawdown = Column(Float, nullable=False, default=0)
    sharpe_ratio = Column(Float, nullable=True)

    # Open positions snapshot
    open_positions = Column(JSON, nullable=True)  # [{symbol, qty, entry_price, current_price, pnl}]

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_paper_snapshot_user_date", "user_id", "date", unique=True),
    )

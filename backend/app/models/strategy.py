"""
Strategy database model.
Path: backend/app/models/strategy.py
"""
from sqlalchemy import Column, String, Text, Boolean, Float, Integer, DateTime, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
import enum
from app.core.database import Base


class StrategyStatus(str, enum.Enum):
    DRAFT = "draft"
    TESTED = "tested"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), default="custom")
    status = Column(String(20), default=StrategyStatus.DRAFT.value)
    version = Column(Integer, default=1)
    user_prompt = Column(Text, nullable=True)
    python_code = Column(Text, nullable=True)
    entry_logic = Column(Text, nullable=True)
    exit_logic = Column(Text, nullable=True)
    risk_rules = Column(Text, nullable=True)
    indicators = Column(JSON, nullable=True)
    parameters = Column(JSON, nullable=True)
    symbols = Column(JSON, nullable=True)
    timeframe = Column(String(10), default="1d")
    exchange = Column(String(10), default="NSE")
    max_position_size = Column(Float, default=10.0)
    stop_loss_pct = Column(Float, default=2.0)
    take_profit_pct = Column(Float, default=4.0)
    max_drawdown_pct = Column(Float, default=15.0)
    trailing_stop_enabled = Column(Boolean, default=True)
    trailing_stop_pct = Column(Float, default=1.5)
    backtest_results = Column(JSON, nullable=True)
    is_public = Column(Boolean, default=False)
    cloned_from = Column(UUID(as_uuid=True), nullable=True)
    clone_count = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    tags = Column(JSON, nullable=True)
    is_paper_active = Column(Boolean, default=False)
    is_live_active = Column(Boolean, default=False)
    broker_account_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

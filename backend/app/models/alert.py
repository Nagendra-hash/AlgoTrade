"""
Alert, Notification, and SentimentCache models.
Path: backend/app/models/alert.py
"""
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Enum as SAEnum, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.core.database import Base


class AlertCondition(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"
    PERCENT_CHANGE = "percent_change"
    VOLUME_SPIKE = "volume_spike"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    NEWS_MENTION = "news_mention"
    SENTIMENT_ABOVE = "sentiment_above"
    SENTIMENT_BELOW = "sentiment_below"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    PAUSED = "paused"
    EXPIRED = "expired"


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    TELEGRAM = "telegram"
    EMAIL = "email"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(10), nullable=False, default="NSE")
    name = Column(String(200), nullable=True)
    condition = Column(String(30), nullable=False)
    target_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default=AlertStatus.ACTIVE.value)
    is_repeating = Column(Boolean, default=False)
    repeat_interval_minutes = Column(Integer, default=60)
    channels = Column(JSON, default=list)
    news_sources = Column(JSON, nullable=True, default=list)
    notes = Column(Text, nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    notifications = relationship("Notification", back_populates="alert", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=False)
    symbol = Column(String(50), nullable=True)
    notification_type = Column(String(50), default="alert")
    data = Column(JSON, nullable=True)
    channel = Column(String(20), default=NotificationChannel.IN_APP.value)
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    alert = relationship("Alert", back_populates="notifications")


class SentimentCache(Base):
    __tablename__ = "sentiment_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(50), nullable=False, index=True, unique=True)
    exchange = Column(String(10), default="NSE")
    score = Column(Float, nullable=False, default=0.0)
    label = Column(String(20), default="neutral")
    confidence = Column(Float, nullable=False, default=0.0)
    explanation = Column(Text, nullable=True)
    headlines = Column(JSON, nullable=True)
    news_count = Column(Integer, default=0)
    cached_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_stale = Column(Boolean, default=False)

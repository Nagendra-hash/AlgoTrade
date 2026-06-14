"""
Alert, Notification, Sentiment Pydantic schemas.
Path: backend/app/schemas/alert.py
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
import uuid


class AlertConditionSchema(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    PERCENT_CHANGE = "percent_change"
    VOLUME_SPIKE = "volume_spike"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    NEWS_MENTION = "news_mention"
    SENTIMENT_ABOVE = "sentiment_above"
    SENTIMENT_BELOW = "sentiment_below"


class AlertStatusSchema(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    PAUSED = "paused"
    EXPIRED = "expired"


class AlertCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=50)
    exchange: str = Field(default="NSE", max_length=10)
    name: Optional[str] = Field(None, max_length=200)
    condition: AlertConditionSchema
    target_value: float = Field(...)
    is_repeating: bool = False
    repeat_interval_minutes: int = Field(default=60, ge=5, le=10080)
    channels: List[str] = Field(default=["in_app"])
    news_sources: Optional[List[str]] = Field(None, description="News sources to watch (e.g. Foreign Policy, The Economist). Required for news_mention condition.")
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("symbol")
    @classmethod
    def symbol_upper(cls, v):
        return v.upper().strip()

    @field_validator("channels")
    @classmethod
    def valid_channels(cls, v):
        allowed = {"in_app", "telegram", "email"}
        for ch in v:
            if ch not in allowed:
                raise ValueError(f"Invalid channel: {ch}")
        return v

    @field_validator("news_sources")
    @classmethod
    def validate_news_sources(cls, v, info):
        if info.data.get("condition") == AlertConditionSchema.NEWS_MENTION and not v:
            raise ValueError("news_sources is required for news_mention condition")
        return v

    @field_validator("target_value")
    @classmethod
    def validate_target_value(cls, v, info):
        condition = info.data.get("condition")
        # Sentiment_below allows negative thresholds (e.g. -30 for bearish)
        if condition == AlertConditionSchema.SENTIMENT_BELOW:
            if v > 0:
                raise ValueError("target_value should be negative or zero for sentiment_below condition (e.g. -30)")
            return v
        # Price/sentiment_above conditions must have positive target
        if condition not in (AlertConditionSchema.NEWS_MENTION,):
            if v <= 0:
                raise ValueError("target_value must be positive for this condition")
        return v


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    target_value: Optional[float] = Field(None, gt=0)
    condition: Optional[AlertConditionSchema] = None
    status: Optional[AlertStatusSchema] = None
    is_repeating: Optional[bool] = None
    repeat_interval_minutes: Optional[int] = Field(None, ge=5, le=10080)
    channels: Optional[List[str]] = None
    news_sources: Optional[List[str]] = None
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class AlertResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    symbol: str
    exchange: str
    name: Optional[str]
    condition: str
    target_value: float
    current_value: Optional[float]
    status: str
    is_repeating: bool
    repeat_interval_minutes: int
    channels: List[str]
    news_sources: Optional[List[str]]
    notes: Optional[str]
    trigger_count: int
    triggered_at: Optional[datetime]
    last_checked_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    total: int
    active: int
    triggered: int
    paused: int
    alerts: List[AlertResponse]


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    alert_id: Optional[uuid.UUID]
    title: str
    message: str
    symbol: Optional[str]
    notification_type: str
    data: Optional[Any]
    channel: str
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    total: int
    unread: int
    notifications: List[NotificationResponse]


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[uuid.UUID]] = None


class SentimentResponse(BaseModel):
    symbol: str
    exchange: str
    score: float
    label: str
    confidence: float
    explanation: Optional[str]
    headlines: Optional[List[str]]
    news_count: int
    cached_at: Optional[datetime]
    is_stale: bool

    model_config = {"from_attributes": True}


class BulkSentimentRequest(BaseModel):
    symbols: List[str] = Field(..., min_length=1, max_length=50)
    exchange: str = "NSE"


class MarketSentimentSummary(BaseModel):
    bullish_count: int
    bearish_count: int
    neutral_count: int
    total: int
    avg_score: float
    top_bullish: Optional[SentimentResponse]
    top_bearish: Optional[SentimentResponse]
    updated_at: datetime

"""
Order database model.
Path: backend/app/models/order.py
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
import enum
from app.core.database import Base


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_MARKET = "STOP_LOSS_MARKET"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ProductType(str, enum.Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    NORMAL = "NORMAL"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_account_id = Column(UUID(as_uuid=True), nullable=True)
    broker_order_id = Column(String(100), nullable=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(10), nullable=False, default="NSE")
    side = Column(SAEnum(OrderSide), nullable=False)
    order_type = Column(SAEnum(OrderType), nullable=False)
    product_type = Column(SAEnum(ProductType), nullable=False, default=ProductType.INTRADAY)
    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)
    trigger_price = Column(Float, nullable=True)
    average_price = Column(Float, nullable=True)
    filled_quantity = Column(Integer, nullable=True, default=0)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    strategy_id = Column(UUID(as_uuid=True), nullable=True)
    is_paper_trade = Column(String(5), nullable=False, default="true")
    notes = Column(Text, nullable=True)
    broker_message = Column(Text, nullable=True)
    placed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    executed_at = Column(DateTime(timezone=True), nullable=True)

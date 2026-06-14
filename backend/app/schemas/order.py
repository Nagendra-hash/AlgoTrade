"""
Order Pydantic schemas.
Path: backend/app/schemas/order.py
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class PlaceOrderRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    side: str = Field(..., pattern="^(BUY|SELL)$")
    order_type: str = Field(..., pattern="^(MARKET|LIMIT|STOP_LOSS|STOP_LOSS_MARKET)$")
    product_type: str = Field("INTRADAY", pattern="^(INTRADAY|DELIVERY|NORMAL)$")
    quantity: int = Field(..., gt=0)
    price: float = Field(0.0, ge=0)
    trigger_price: float = Field(0.0, ge=0)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    is_paper_trade: bool = True


class OrderResponse(BaseModel):
    id: uuid.UUID
    broker_order_id: Optional[str]
    symbol: str
    exchange: str
    side: str
    order_type: str
    product_type: str
    status: str
    quantity: int
    price: Optional[float]
    average_price: Optional[float]
    filled_quantity: Optional[int]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    is_paper_trade: str
    placed_at: datetime
    executed_at: Optional[datetime]

    model_config = {"from_attributes": True}

"""
Order management — place, cancel, list orders.
Routes real orders through connected brokers (Angel One / Zerodha).
Path: backend/app/api/v1/orders.py
"""
import uuid
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.order import Order, OrderSide, OrderType, OrderStatus, ProductType
from app.models.user import User
from app.schemas.order import PlaceOrderRequest, OrderResponse
from app.api.v1.users import get_current_user
from app.services.alert_engine import fetch_market_data
from app.services.angel_one import (
    get_session as get_angel_session, get_symbol_token,
    _headers as angel_headers, _get_angel_symbol,
)
from app.services.zerodha import (
    get_session as get_zerodha_session, _kite_headers, _get_kite_symbol,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _place_broker_order(
    user_id: str, symbol: str, exchange: str, side: str,
    quantity: int, price: float, order_type: str, product_type: str,
) -> tuple[str, str]:
    """
    Route order to connected broker. Returns (broker_order_id, broker_name).
    Tries Angel One first, then Zerodha.
    """
    # Try Angel One
    angel_session = await get_angel_session(user_id)
    if angel_session and angel_session.get("jwt_token"):
        token = await get_symbol_token(symbol, exchange)
        if token:
            angel_sym = _get_angel_symbol(symbol, exchange)
            angel_order_type = {
                "MARKET": "MARKET", "LIMIT": "LIMIT",
                "STOP_LOSS": "STOP_LOSS_LIMIT", "STOP_LOSS_MARKET": "STOP_LOSS_MARKET",
            }.get(order_type, "MARKET")
            angel_product = {"INTRADAY": "INTRADAY", "DELIVERY": "CNC", "NORMAL": "NORMAL"}.get(product_type, "INTRADAY")
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    resp = await c.post(
                        "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/placeOrder",
                        headers=angel_headers(angel_session["api_key"], angel_session["jwt_token"]),
                        json={
                            "exchange": exchange, "tradingsymbol": angel_sym,
                            "transactiontype": side, "ordertype": angel_order_type,
                            "product": angel_product, "duration": "DAY",
                            "quantity": str(quantity),
                            "price": str(price) if order_type != "MARKET" else "0",
                        },
                    )
                    data = resp.json()
                    if data.get("status") is True:
                        oid = data.get("data", {}).get("orderid", "")
                        logger.info(f"Angel One order placed: {oid}")
                        return str(oid), "angel_one"
                    else:
                        logger.warning(f"Angel One order rejected: {data.get('message')}")
            except Exception as e:
                logger.error(f"Angel One order error: {e}")

    # Try Zerodha
    zerodha_session = await get_zerodha_session(user_id)
    if zerodha_session and zerodha_session.get("access_token"):
        kite_sym = _get_kite_symbol(symbol, exchange).replace(f"{exchange}:", "")
        kite_order_type = {
            "MARKET": "MARKET", "LIMIT": "LIMIT",
            "STOP_LOSS": "SL", "STOP_LOSS_MARKET": "SL-M",
        }.get(order_type, "MARKET")
        kite_product = {"INTRADAY": "MIS", "DELIVERY": "CNC", "NORMAL": "NRML"}.get(product_type, "MIS")
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.post(
                    "https://api.kite.trade/orders",
                    headers=_kite_headers(zerodha_session["access_token"], zerodha_session["api_key"]),
                    data={
                        "exchange": exchange, "tradingsymbol": kite_sym,
                        "transaction_type": side, "order_type": kite_order_type,
                        "product": kite_product, "validity": "DAY",
                        "quantity": str(quantity),
                        "price": str(price) if order_type != "MARKET" else "",
                    },
                )
                data = resp.json()
                if "data" in data and data["data"].get("order_id"):
                    oid = data["data"]["order_id"]
                    logger.info(f"Zerodha order placed: {oid}")
                    return str(oid), "zerodha"
                else:
                    logger.warning(f"Zerodha order rejected: {data}")
        except Exception as e:
            logger.error(f"Zerodha order error: {e}")

    return "", "none"


@router.post("/place", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(
    req: PlaceOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = Order(
        user_id=current_user.id,
        symbol=req.symbol.upper(),
        exchange=req.exchange.upper(),
        side=OrderSide(req.side),
        order_type=OrderType(req.order_type),
        product_type=ProductType(req.product_type),
        quantity=req.quantity,
        price=req.price if req.order_type != "MARKET" else None,
        trigger_price=req.trigger_price or None,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        is_paper_trade=str(req.is_paper_trade).lower(),
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()

    if req.is_paper_trade:
        market = await fetch_market_data(req.symbol.upper())
        ltp = market.get("ltp", 0) if market else (req.price or 0)
        order.average_price = ltp if req.order_type == "MARKET" else req.price
        order.filled_quantity = req.quantity
        order.status = OrderStatus.COMPLETE
        order.executed_at = datetime.now(timezone.utc)
        order.broker_order_id = f"PAPER-{order.id}"
    else:
        # Route to real broker
        broker_id, broker_name = await _place_broker_order(
            user_id=str(current_user.id),
            symbol=req.symbol.upper(), exchange=req.exchange.upper(),
            side=req.side, quantity=req.quantity,
            price=req.price or 0, order_type=req.order_type,
            product_type=req.product_type,
        )
        if broker_id:
            order.broker_order_id = broker_id
            order.status = OrderStatus.OPEN
        else:
            order.status = OrderStatus.REJECTED
            order.broker_message = "No broker connected or order rejected"

    await db.flush()
    logger.info(f"Order placed: {order.side} {order.quantity} {order.symbol} [{order.status}]")
    return order


@router.get("", response_model=list[OrderResponse])
@router.get("/", response_model=list[OrderResponse], include_in_schema=False)
async def list_orders(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    symbol: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Order).where(Order.user_id == current_user.id)
    if symbol:
        q = q.where(Order.symbol == symbol.upper())
    q = q.order_by(Order.placed_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = r.scalar_one_or_none()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found.")
    return order


@router.delete("/{order_id}")
async def cancel_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = r.scalar_one_or_none()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found.")
    if order.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot cancel {order.status} order.")
    order.status = OrderStatus.CANCELLED
    await db.flush()
    return {"message": "Order cancelled successfully."}

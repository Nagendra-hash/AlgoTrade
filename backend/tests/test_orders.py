"""
Tests for orders API.
Path: backend/tests/test_orders.py

Orders endpoints require get_current_user + get_db.
Auth tests run without mocking; list/get tests use mock DB.
"""
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.users import get_current_user
from app.core.database import get_db


# ── Helpers ─────────────────────────────────────────────────────────

def _mock_auth():
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: mock_user


def _clear_auth():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _mock_db(**kwargs):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_execute = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=kwargs.get("scalars_return", []))
    mock_execute.scalars = MagicMock(return_value=mock_scalars)

    scalar_return = kwargs.get("scalar_return")
    mock_execute.scalar_one_or_none = MagicMock(return_value=scalar_return)
    mock_execute.scalar = MagicMock(return_value=scalar_return)

    mock_session.execute = AsyncMock(return_value=mock_execute)
    app.dependency_overrides[get_db] = lambda: mock_session
    return mock_session, mock_execute, mock_scalars


# ── Auth tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_place_order_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/orders/place", json={
            "symbol": "RELIANCE", "side": "BUY", "quantity": 10,
            "order_type": "MARKET", "product_type": "INTRADAY", "exchange": "NSE",
        })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_orders_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/orders/")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_order_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/v1/orders/{uuid.uuid4()}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cancel_order_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(f"/api/v1/orders/{uuid.uuid4()}")
    assert r.status_code == 403


# ── Place order validation tests (Pydantic enforces before handler) ─

@pytest.mark.asyncio
async def test_place_order_invalid_side():
    """Invalid side should fail Pydantic validation (pattern enum check)."""
    _mock_auth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/orders/place",
                json={
                    "symbol": "RELIANCE", "side": "INVALID", "quantity": 10,
                    "order_type": "MARKET", "product_type": "INTRADAY", "exchange": "NSE",
                },
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 422
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_place_order_negative_quantity():
    """Negative quantity should fail Pydantic validation (gt=0)."""
    _mock_auth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/orders/place",
                json={
                    "symbol": "RELIANCE", "side": "BUY", "quantity": -5,
                    "order_type": "MARKET", "product_type": "INTRADAY", "exchange": "NSE",
                },
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 422
    finally:
        _clear_auth()


# ── List orders tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_orders_empty():
    _mock_auth()
    try:
        _mock_db(scalars_return=[])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/orders/",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
        assert r.json() == []
    finally:
        _clear_auth()


# ── Get order tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_order_not_found():
    _mock_auth()
    try:
        _mock_db()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/v1/orders/{uuid.uuid4()}",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 404
    finally:
        _clear_auth()

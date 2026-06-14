"""
Tests for portfolio API.
Path: backend/tests/test_portfolio.py

Portfolio endpoints require get_current_user + get_db.
Auth tests don't need DB; data flow tests mock broker sessions.
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


def _mock_db():
    """Replace get_db with a mock async session."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_execute = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=[])
    mock_execute.scalars = MagicMock(return_value=mock_scalars)
    mock_execute.scalar = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_execute)
    app.dependency_overrides[get_db] = lambda: mock_session
    return mock_session


# ── Auth tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_holdings_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/portfolio/holdings")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_summary_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/portfolio/summary")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_positions_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/portfolio/positions")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_funds_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/portfolio/funds")
    assert r.status_code == 403


# ── Sample data fallback tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_holdings_returns_sample_data_when_no_broker():
    """
    With no broker session, holdings should return sample data enriched with LTP.
    """
    _mock_auth()
    _mock_db()
    try:
        async def mock_get_quote(symbol, exchange="NSE", user_id=None):
            prices = {"RELIANCE": 2510.0, "TCS": 3300.0, "INFY": 1480.0,
                      "HDFCBANK": 1620.0, "SBIN": 600.0, "WIPRO": 440.0}
            ltp = prices.get(symbol, 100.0)
            return {"ltp": ltp, "change_pct": 0.5, "source": "test"}

        with patch("app.api.v1.portfolio.get_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.portfolio.get_zerodha_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.portfolio._get_quote", side_effect=mock_get_quote):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/portfolio/holdings",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "sample"
        assert data["is_real"] is False
        assert len(data["holdings"]) == 6
        for h in data["holdings"]:
            assert "ltp" in h
            assert "pnl" in h
            assert "current_value" in h
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_summary_returns_sample_data_when_no_broker():
    _mock_auth()
    _mock_db()
    try:
        async def mock_get_quote(symbol, exchange="NSE", user_id=None):
            prices = {"RELIANCE": 2510.0, "TCS": 3300.0, "INFY": 1480.0,
                      "HDFCBANK": 1620.0, "SBIN": 600.0, "WIPRO": 440.0}
            ltp = prices.get(symbol, 100.0)
            return {"ltp": ltp, "change_pct": 0.5}

        with patch("app.api.v1.portfolio.get_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.portfolio.get_zerodha_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.portfolio._get_quote", side_effect=mock_get_quote):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/portfolio/summary",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "sample"
        assert data["is_real"] is False
        assert data["holdings_count"] == 6
        assert data["total_invested"] > 0
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_positions_returns_empty_when_no_broker():
    _mock_auth()
    _mock_db()
    try:
        with patch("app.api.v1.portfolio.get_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.portfolio.get_zerodha_session", AsyncMock(return_value=None)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/portfolio/positions",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "sample"
        assert data["is_real"] is False
        assert data["positions"] == []
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_funds_returns_empty_when_no_broker():
    _mock_auth()
    _mock_db()
    try:
        with patch("app.api.v1.portfolio.get_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.portfolio.get_zerodha_session", AsyncMock(return_value=None)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/portfolio/funds",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "sample"
        assert data["is_real"] is False
    finally:
        _clear_auth()

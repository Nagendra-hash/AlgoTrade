"""
Tests for market data API endpoints.
Path: backend/tests/test_market.py

Regression tests for the get_indices exchange parameter bug and similar Query() default issues.
Uses app.dependency_overrides to mock auth, avoiding database event loop complications.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.users import get_current_user


# ── Helper ──────────────────────────────────────────────────────────

def _mock_auth():
    """Override auth dependency so tests don't need real DB users."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: mock_user


def _clear_auth():
    """Remove the auth override."""
    app.dependency_overrides.pop(get_current_user, None)


# ── Auth / auth-agnostic tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_indices_requires_auth():
    """get_indices should return 403 without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/market/indices")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_indices_invalid_token():
    """get_indices should return 401 with an invalid token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/market/indices",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_market_status_unauthenticated():
    """market/status should work without authentication (no Depends)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/market/status")
    assert r.status_code == 200
    data = r.json()
    assert "is_open" in data
    assert data["exchange"] == "NSE"


# ── get_indices regression tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_indices_calls_get_quotes_with_exchange_nse():
    """
    Regression test: get_indices must call get_quotes with exchange="NSE".

    Previously, get_indices called:
        return await get_quotes("NIFTY50,BANKNIFTY,SENSEX", current_user=current_user)

    This caused the Query("NSE") default in get_quotes to evaluate to a
    FieldInfo object instead of the string "NSE", breaking JSON serialization.

    The fix explicitly passes exchange="NSE".
    """
    _mock_auth()
    try:
        async def mock_quotes_bulk(symbols, exchange=None, user_id=None):
            assert isinstance(exchange, str), (
                f"exchange should be str, got {type(exchange)}: {exchange!r}"
            )
            assert exchange == "NSE", f"exchange should be 'NSE', got {exchange!r}"
            assert symbols == "NIFTY50,BANKNIFTY,SENSEX"
            assert isinstance(user_id, str)
            return [
                {"symbol": "NIFTY50", "ltp": 23622.9, "exchange": "NSE", "source": "test"},
                {"symbol": "BANKNIFTY", "ltp": 56814.8, "exchange": "NSE", "source": "test"},
                {"symbol": "SENSEX", "ltp": 75527.95, "exchange": "NSE", "source": "test"},
            ]

        mock_bulk_fn = AsyncMock(side_effect=mock_quotes_bulk)

        with patch("app.api.v1.market._get_quotes_bulk", mock_bulk_fn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/market/indices",
                    headers={"Authorization": "Bearer test-token"},
                )

        assert r.status_code == 200
        mock_bulk_fn.assert_awaited_once()

        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 3
        for item in data:
            assert "symbol" in item
            assert item["exchange"] == "NSE"
    finally:
        _clear_auth()


# ── get_quotes regression test ──────────────────────────────────────

@pytest.mark.asyncio
async def test_quotes_calls_get_quote_with_exchange_str():
    """
    Regression test: get_quotes passes exchange as string (not FieldInfo) to _get_quote.
    Tests both default exchange and explicit override via the HTTP layer.
    """
    _mock_auth()
    try:
        call_count = 0

        async def mock_get_quote(symbol, exchange="NSE", user_id=None):
            nonlocal call_count
            call_count += 1
            assert isinstance(exchange, str), (
                f"exchange should be str, got {type(exchange)}: {exchange!r}"
            )
            return {"symbol": symbol, "ltp": 100.0, "exchange": exchange, "source": "test"}

        with patch("app.api.v1.market._get_quote", side_effect=mock_get_quote):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Test with default exchange (should be "NSE")
                r = await client.get(
                    "/api/v1/market/quotes?symbols=RELIANCE,TCS",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert r.status_code == 200
                data = r.json()
                assert isinstance(data, list)
                assert len(data) == 2
                for item in data:
                    assert item["exchange"] == "NSE"

                # Test with explicit exchange override
                r = await client.get(
                    "/api/v1/market/quotes?symbols=RELIANCE&exchange=BSE",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert r.status_code == 200
                data = r.json()
                assert len(data) == 1
                assert data[0]["exchange"] == "BSE"
    finally:
        _clear_auth()


# ── get_quote_route regression test ────────────────────────────────

@pytest.mark.asyncio
async def test_quote_route_passes_exchange_str():
    """
    Regression test: get_quote_route passes exchange as string (not FieldInfo) to _get_quote.
    """
    _mock_auth()
    try:
        captured_exchange = None

        async def mock_get_quote(symbol, exchange="NSE", user_id=None):
            nonlocal captured_exchange
            captured_exchange = exchange
            assert isinstance(exchange, str), (
                f"exchange should be str, got {type(exchange)}: {exchange!r}"
            )
            return {"symbol": symbol, "ltp": 100.0, "exchange": exchange, "source": "test"}

        with patch("app.api.v1.market._get_quote", side_effect=mock_get_quote):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Default exchange
                r = await client.get(
                    "/api/v1/market/quote/RELIANCE",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert r.status_code == 200
                assert captured_exchange == "NSE", f"Expected 'NSE', got {captured_exchange!r}"
                assert r.json()["exchange"] == "NSE"

                # Explicit exchange
                r = await client.get(
                    "/api/v1/market/quote/RELIANCE?exchange=BSE",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert r.status_code == 200
                assert captured_exchange == "BSE", f"Expected 'BSE', got {captured_exchange!r}"
                assert r.json()["exchange"] == "BSE"
    finally:
        _clear_auth()


# ── get_candles regression test ────────────────────────────────────

@pytest.mark.asyncio
async def test_candles_passes_query_defaults_as_str():
    """
    Regression test: get_candles passes interval, period, and exchange as strings,
    not FieldInfo objects, when called through the HTTP layer.
    """
    _mock_auth()
    try:
        with patch("app.api.v1.market.redis_get", new_callable=AsyncMock, return_value=None), \
             patch("app.api.v1.market.redis_set", new_callable=AsyncMock, return_value=None), \
             patch("app.api.v1.market._fetch_candles_sync", return_value=[
                 {"time": 1000000, "open": 100.0, "high": 101.0,
                  "low": 99.0, "close": 100.5, "volume": 10000},
             ]):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Default parameters
                r = await client.get(
                    "/api/v1/market/candles/RELIANCE",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert r.status_code == 200
                data = r.json()
                assert isinstance(data, list)
                assert len(data) >= 1

                # Custom parameters
                r = await client.get(
                    "/api/v1/market/candles/RELIANCE?interval=1h&period=1mo&exchange=BSE",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert r.status_code == 200
                data = r.json()
                assert isinstance(data, list)
    finally:
        _clear_auth()


# ── search_symbols regression test (no auth needed) ─────────────────

@pytest.mark.asyncio
async def test_search_symbols_query_defaults():
    """
    Regression test: search_symbols handles Query() defaults correctly.
    No auth required, tests that query params work via HTTP.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Search with default exchange
        r = await client.get("/api/v1/market/search", params={"q": "RELIANCE"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["symbol"] == "RELIANCE"
        assert data[0]["exchange"] == "NSE"

        # Partial match search
        r = await client.get("/api/v1/market/search", params={"q": "BANK"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert any("BANK" in item["symbol"] for item in data)

        # Empty query should fail validation (min_length=1)
        r = await client.get("/api/v1/market/search", params={"q": ""})
        assert r.status_code == 422




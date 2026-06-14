"""
Tests for auto-trading engine API.
Path: backend/tests/test_auto_trade.py

auto_trade.py endpoints use auto_trade_engine singleton (no Depends(get_db)),
making them easy to test by mocking the engine.
"""
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.users import get_current_user


# ── Helper ──────────────────────────────────────────────────────────

def _mock_auth():
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: mock_user


def _clear_auth():
    app.dependency_overrides.pop(get_current_user, None)


def _make_engine_mock():
    """Create a mock auto_trade_engine with default return values."""
    engine = MagicMock()
    engine.state.risk_config = {
        "max_daily_loss_pct": 5.0,
        "max_position_size_pct": 10.0,
        "max_open_positions": 5,
        "max_trades_per_day": 10,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 1.5,
        "trading_capital": 100000.0,
    }
    engine.get_status.return_value = {
        "is_running": True, "mode": "paper",
        "active_strategies": 0, "open_positions": 0,
        "today_pnl": 0.0, "total_trades": 0,
    }
    engine.get_positions.return_value = []
    engine.get_today_activity.return_value = []
    return engine


# ── Auth tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_engine_start_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/auto-trade/start")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_engine_stop_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/auto-trade/stop")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_engine_status_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/auto-trade/status")
    assert r.status_code == 403


# ── Engine control tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_engine_default_mode():
    """Starting with no body should default to paper mode."""
    _mock_auth()
    try:
        engine = _make_engine_mock()
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/auto-trade/start",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["is_running"] is True
        assert data["mode"] == "paper"
        engine.set_mode.assert_called_once_with("paper")
        engine.start.assert_called_once()
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_start_engine_live_mode():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/auto-trade/start",
                    json={"mode": "live"},
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        assert r.json()["mode"] == "live"
        engine.set_mode.assert_called_once_with("live")
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_stop_engine():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/auto-trade/stop",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        assert r.json()["is_running"] is False
        engine.stop.assert_called_once()
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_get_engine_status():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/auto-trade/status",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["is_running"] is True
        assert data["mode"] == "paper"
        engine.get_status.assert_called_once()
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_get_positions():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        engine.get_positions.return_value = [
            {"symbol": "RELIANCE", "quantity": 10, "entry_price": 2500.0},
        ]
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/auto-trade/positions",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert "positions" in data
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "RELIANCE"
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_get_activity():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        engine.get_today_activity.return_value = [
            {"time": "09:30", "action": "BUY", "symbol": "TCS", "qty": 5},
            {"time": "10:15", "action": "SELL", "symbol": "INFY", "qty": 10},
        ]
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/auto-trade/activity",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["activity"]) == 2
    finally:
        _clear_auth()


# ── Risk config tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_risk_config():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/auto-trade/risk",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert "risk_config" in data
        assert data["risk_config"]["max_daily_loss_pct"] == 5.0
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_update_risk_config():
    _mock_auth()
    try:
        engine = _make_engine_mock()
        with patch("app.api.v1.auto_trade.auto_trade_engine", engine):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.put(
                    "/api/v1/auto-trade/risk",
                    json={"max_daily_loss_pct": 3.0, "max_open_positions": 8},
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        engine.update_risk_config.assert_called_once_with({
            "max_daily_loss_pct": 3.0, "max_open_positions": 8,
        })
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_update_risk_config_validation():
    """min/max bounds should be enforced by Pydantic."""
    _mock_auth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.put(
                "/api/v1/auto-trade/risk",
                json={"max_daily_loss_pct": 999},
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 422
    finally:
        _clear_auth()


# ── Stock screener test ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_screen_stocks():
    _mock_auth()
    try:
        mock_screener = MagicMock()
        mock_screener.screen_stocks = AsyncMock(return_value=[
            {"symbol": "RELIANCE", "score": 85, "signal": "BUY"},
            {"symbol": "TCS", "score": 72, "signal": "BUY"},
        ])

        with patch("app.services.stock_screener.stock_screener", mock_screener):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/auto-trade/screen",
                    json={"strategy_type": "momentum", "min_volume": 50000, "limit": 5},
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["candidates"]) == 2
        mock_screener.screen_stocks.assert_called_once()
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_screen_stocks_defaults():
    """Screen with no body should use defaults."""
    _mock_auth()
    try:
        mock_screener = MagicMock()
        mock_screener.screen_stocks = AsyncMock(return_value=[])

        with patch("app.services.stock_screener.stock_screener", mock_screener):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/auto-trade/screen",
                    json={},
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        _, kwargs = mock_screener.screen_stocks.call_args
        assert kwargs["criteria"]["strategy_type"] == "momentum"
        assert kwargs["criteria"]["min_volume"] == 100000
        assert kwargs["limit"] == 10
    finally:
        _clear_auth()

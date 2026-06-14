"""
Tests for broker connection API.
Path: backend/tests/test_brokers.py

brokers.py endpoints use get_current_user but not get_db,
making them testable by mocking broker service functions.
"""
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.users import get_current_user


# ── Helpers ─────────────────────────────────────────────────────────

def _mock_auth():
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: mock_user


def _clear_auth():
    app.dependency_overrides.pop(get_current_user, None)


# ── Auth tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_angel_one_connect_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/brokers/angel-one/connect", json={
            "api_key": "test", "client_id": "test",
            "password": "test", "totp_secret": "test",
        })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_zerodha_connect_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/brokers/zerodha/connect", json={
            "api_key": "test", "api_secret": "test",
        })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_broker_status_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/brokers/status")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_broker_debug_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/brokers/debug")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_disconnect_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/brokers/disconnect/angel_one")
    assert r.status_code == 403


# ── Validation tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_angel_one_connect_empty_fields():
    _mock_auth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/brokers/angel-one/connect",
                json={"api_key": "", "client_id": "  ", "password": "test", "totp_secret": "test"},
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 400
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_zerodha_connect_empty_fields():
    _mock_auth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/brokers/zerodha/connect",
                json={"api_key": "", "api_secret": ""},
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 400
    finally:
        _clear_auth()


# ── Angel One connection tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_angel_one_connect_success():
    _mock_auth()
    try:
        mock_login = AsyncMock(return_value={
            "success": True,
            "jwt_token": "test-jwt",
            "refresh_token": "test-refresh",
            "feed_token": "test-feed",
        })
        mock_store = AsyncMock()

        with patch("app.api.v1.brokers.login", mock_login), \
             patch("app.api.v1.brokers.store_session", mock_store):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/brokers/angel-one/connect",
                    json={
                        "api_key": "test-key",
                        "client_id": "test-client",
                        "password": "test-pass",
                        "totp_secret": "test-totp",
                    },
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["broker"] == "angel_one"
        assert data["is_connected"] is True
        mock_login.assert_called_once_with("test-key", "test-client", "test-pass", "test-totp")
        mock_store.assert_called_once()
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_angel_one_connect_failure():
    _mock_auth()
    try:
        mock_login = AsyncMock(return_value={
            "success": False,
            "error": "Invalid credentials",
        })

        with patch("app.api.v1.brokers.login", mock_login):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/brokers/angel-one/connect",
                    json={
                        "api_key": "bad-key",
                        "client_id": "bad-client",
                        "password": "bad-pass",
                        "totp_secret": "bad-totp",
                    },
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 400
    finally:
        _clear_auth()


# ── Zerodha connection tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_zerodha_connect_success():
    _mock_auth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/brokers/zerodha/connect",
                json={"api_key": "valid-key", "api_secret": "valid-secret"},
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["broker"] == "zerodha"
        assert "login_url" in data
        assert "kite.zerodha.com" in data["login_url"]
    finally:
        _clear_auth()


# ── Broker status tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broker_status_empty():
    """Status should return empty list when no brokers connected."""
    _mock_auth()
    try:
        with patch("app.api.v1.brokers.get_session", AsyncMock(return_value=None)), \
             patch("app.api.v1.brokers.zerodha_get_session", AsyncMock(return_value=None)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/brokers/status",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        assert r.json() == []
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_broker_status_with_angel_one():
    _mock_auth()
    try:
        with patch("app.api.v1.brokers.get_session", AsyncMock(return_value={
            "client_id": "test-client",
        })), \
             patch("app.api.v1.brokers.zerodha_get_session", AsyncMock(return_value=None)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    "/api/v1/brokers/status",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["broker"] == "angel_one"
        assert data[0]["is_connected"] is True
    finally:
        _clear_auth()


# ── Zerodha callback tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_zerodha_callback_success():
    _mock_auth()
    try:
        mock_login = AsyncMock(return_value={
            "success": True,
            "access_token": "test-access",
            "login_id": "test-login",
        })
        mock_store = AsyncMock()

        with patch("app.api.v1.brokers.zerodha_login", mock_login), \
             patch("app.api.v1.brokers.zerodha_store_session", mock_store):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/brokers/zerodha/callback",
                    json={"request_token": "test-token", "api_key": "test-key", "api_secret": "test-secret"},
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["broker"] == "zerodha"
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_zerodha_callback_failure():
    _mock_auth()
    try:
        mock_login = AsyncMock(return_value={
            "success": False,
            "error": "Token exchange failed",
        })

        with patch("app.api.v1.brokers.zerodha_login", mock_login):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/brokers/zerodha/callback",
                    json={"request_token": "bad-token", "api_key": "bad-key", "api_secret": "bad-secret"},
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 400
    finally:
        _clear_auth()


# ── Disconnect tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disconnect_angel_one():
    _mock_auth()
    try:
        mock_clear = AsyncMock()
        with patch("app.api.v1.brokers.clear_session", mock_clear):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/brokers/disconnect/angel_one",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        assert r.json()["success"] is True
        mock_clear.assert_called_once()
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_disconnect_zerodha():
    _mock_auth()
    try:
        mock_clear = AsyncMock()
        mock_stop_ticker = MagicMock()
        with patch("app.api.v1.brokers.zerodha_clear_session", mock_clear), \
             patch("app.services.zerodha.stop_ticker", mock_stop_ticker):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/api/v1/brokers/disconnect/zerodha",
                    headers={"Authorization": "Bearer test-token"},
                )
        assert r.status_code == 200
        assert r.json()["success"] is True
        mock_clear.assert_called_once()
        mock_stop_ticker.assert_called_once()
    finally:
        _clear_auth()

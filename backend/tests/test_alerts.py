"""
Tests for alerts API.
Path: backend/tests/test_alerts.py

Alerts endpoints require get_current_user + get_db.
Auth tests run without mocking; flow tests use a mock DB session
for endpoints that don't require real data persistence (list only).
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

    scalar_side_effect = kwargs.get("scalar_side_effect")
    if scalar_side_effect is not None:
        mock_execute.scalar = MagicMock(side_effect=scalar_side_effect)
    else:
        mock_execute.scalar = MagicMock(return_value=kwargs.get("scalar_return", 0))

    mock_session.execute = AsyncMock(return_value=mock_execute)
    app.dependency_overrides[get_db] = lambda: mock_session
    return mock_session, mock_execute, mock_scalars


# ── Auth tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_alerts_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/alerts")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_alert_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/alerts", json={
            "symbol": "RELIANCE", "condition": "above", "target_value": 2800.0,
        })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_alert_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/v1/alerts/{uuid.uuid4()}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_update_alert_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.put(f"/api/v1/alerts/{uuid.uuid4()}", json={"name": "Updated"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_alert_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(f"/api/v1/alerts/{uuid.uuid4()}")
    assert r.status_code == 403


# ── List alerts tests (only use mock DB for reading, not writing) ───

@pytest.mark.asyncio
async def test_list_alerts_empty():
    _mock_auth()
    try:
        _mock_db(scalars_return=[], scalar_side_effect=[0, 0, 0, 0, 0])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/alerts",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
        data = r.json()
        assert "alerts" in data
        assert "total" in data
        assert data["alerts"] == []
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_list_alerts_with_status_filter():
    _mock_auth()
    try:
        _mock_db(scalars_return=[], scalar_side_effect=[0, 0, 0, 0, 0])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/alerts?status=active",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_list_alerts_invalid_status():
    _mock_auth()
    try:
        _mock_db(scalar_side_effect=[0, 0, 0, 0, 0])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/alerts?status=invalid_status_xyz",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 400
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_list_alerts_with_symbol_filter():
    _mock_auth()
    try:
        _mock_db(scalars_return=[], scalar_side_effect=[0, 0, 0, 0, 0])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/alerts?symbol=RELIANCE",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
    finally:
        _clear_auth()

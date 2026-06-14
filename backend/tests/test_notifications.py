"""
Tests for notifications API.
Path: backend/tests/test_notifications.py

Notifications endpoints require get_current_user + get_db.
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
async def test_list_notifications_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/notifications")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_unread_count_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/notifications/unread-count")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_mark_read_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/notifications/read", json={})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_notification_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(f"/api/v1/notifications/{uuid.uuid4()}")
    assert r.status_code == 403


# ── List notifications tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_notifications_empty():
    _mock_auth()
    try:
        _mock_db(scalars_return=[], scalar_side_effect=[0, 0])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/notifications",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
        data = r.json()
        assert "notifications" in data
        assert "total" in data
        assert data["notifications"] == []
        assert data["unread"] == 0
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_list_notifications_unread_filter():
    _mock_auth()
    try:
        _mock_db(scalars_return=[], scalar_side_effect=[0, 0])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/notifications?is_read=false",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
    finally:
        _clear_auth()


# ── Unread count test ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unread_count():
    _mock_auth()
    try:
        _mock_db(scalar_return=3)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/notifications/unread-count",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
        assert r.json()["unread"] == 3
    finally:
        _clear_auth()


# ── Mark read tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_read_all():
    _mock_auth()
    try:
        mock_session, _, _ = _mock_db()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/notifications/read",
                json={},
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
        assert r.json()["message"] == "Marked as read."
    finally:
        _clear_auth()


@pytest.mark.asyncio
async def test_mark_read_specific():
    _mock_auth()
    try:
        mock_session, _, _ = _mock_db()
        nid1 = uuid.uuid4()
        nid2 = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/v1/notifications/read",
                json={"notification_ids": [str(nid1), str(nid2)]},
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200
    finally:
        _clear_auth()


# ── Delete notification test ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_notification():
    _mock_auth()
    try:
        mock_session, _, _ = _mock_db(scalars_return=[])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(
                f"/api/v1/notifications/{uuid.uuid4()}",
                headers={"Authorization": "Bearer test-token"},
            )
        # Delete is idempotent — returns 200 even if not found
        assert r.status_code == 200
        assert r.json()["message"] == "Deleted."
    finally:
        _clear_auth()

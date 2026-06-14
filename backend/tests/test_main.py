"""
Integration tests.
Path: backend/tests/test_main.py
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_market_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/market/status")
    assert r.status_code == 200
    data = r.json()
    assert "is_open" in data
    assert "status" in data
    assert data["exchange"] == "NSE"


@pytest.mark.asyncio
async def test_signup_and_login():
    # Use unique credentials per run so this test is idempotent
    uid = uuid.uuid4().hex[:8]
    email = f"testuser-{uid}@tradeai.com"
    username = f"testtrader-{uid}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        signup = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "username": username,
            "full_name": "Test Trader",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        })
        assert signup.status_code == 201
        assert signup.json()["email"] == email

        login = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "SecurePass123!",
        })
        assert login.status_code == 200
        assert "access_token" in login.json()
        return login.json()["access_token"]


@pytest.mark.asyncio
async def test_news_feed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/news?page=1&per_page=5")
    assert r.status_code == 200
    data = r.json()
    assert "articles" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_alert_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/alerts", json={
            "symbol": "RELIANCE",
            "condition": "above",
            "target_value": 2800.0,
        })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_docs_available():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/docs")
    assert r.status_code == 200

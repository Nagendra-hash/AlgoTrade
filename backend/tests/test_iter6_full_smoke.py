"""Iter6 — Full functional smoke after env recreate (Postgres + Redis + migrations + seed)."""
import os, uuid, time, requests, pytest

EXT = "https://5e0d847d-b059-4b8e-9818-9c3a87b9ce69.preview.emergentagent.com"
LOCAL = "http://localhost:8001"
API = f"{EXT}/api/v1"
DEMO = {"email": "demo@tradeai.com", "password": "Demo1234!"}


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json=DEMO, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    j = r.json()
    assert "access_token" in j and "refresh_token" in j and "user" in j
    assert j["user"]["email"] == DEMO["email"]
    return j["access_token"]


@pytest.fixture
def h(token):
    return {"Authorization": f"Bearer {token}"}


# --- Health ---
def test_health_local():
    r = requests.get(f"{LOCAL}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# --- Auth ---
def test_signup_unique():
    email = f"smoke_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "username": email.split("@")[0], "password": "Pass1234!", "confirm_password": "Pass1234!", "full_name": "Smoke User"}, timeout=20)
    assert r.status_code in (200, 201), r.text[:300]
    body = r.json()
    assert "email" in body and body["email"] == email


def test_users_me(h):
    r = requests.get(f"{API}/users/me", headers=h, timeout=15)
    assert r.status_code == 200
    assert r.json()["email"] == DEMO["email"]


# --- Market ---
def test_market_indices(h):
    r = requests.get(f"{API}/market/indices", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    txt = str(body).upper()
    assert "NIFTY" in txt


def test_market_quote(h):
    r = requests.get(f"{API}/market/quote/RELIANCE", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]


def test_market_candles(h):
    r = requests.get(f"{API}/market/candles/RELIANCE", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]


def test_market_search(h):
    r = requests.get(f"{API}/market/search?q=infy", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]


# --- Portfolio (no broker => no_live_data invariant) ---
def test_portfolio_summary_no_live(h):
    r = requests.get(f"{API}/portfolio/summary", headers=h, timeout=20)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("source") == "none" and j.get("no_live_data") is True, j


def test_portfolio_positions_no_live(h):
    r = requests.get(f"{API}/portfolio/positions", headers=h, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("source") == "none" and j.get("no_live_data") is True


def test_portfolio_funds_no_live(h):
    r = requests.get(f"{API}/portfolio/funds", headers=h, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("source") == "none" and j.get("no_live_data") is True


# --- Orders ---
def test_orders_list(h):
    r = requests.get(f"{API}/orders/", headers=h, timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


# --- Alerts CRUD ---
def test_alerts_crud(h):
    create = requests.post(f"{API}/alerts", headers=h, json={
        "symbol": "RELIANCE", "condition": "above", "target_value": 9999999,
        "notify_channels": ["in_app"]
    }, timeout=20)
    assert create.status_code in (200, 201), create.text[:300]
    aid = create.json().get("id")
    assert aid

    lst = requests.get(f"{API}/alerts", headers=h, timeout=20)
    assert lst.status_code == 200
    items = lst.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("alerts") or []
    assert any(a.get("id") == aid for a in items)

    p = requests.post(f"{API}/alerts/{aid}/pause", headers=h, timeout=15)
    assert p.status_code in (200, 204)
    r = requests.post(f"{API}/alerts/{aid}/resume", headers=h, timeout=15)
    assert r.status_code in (200, 204)
    d = requests.delete(f"{API}/alerts/{aid}", headers=h, timeout=15)
    assert d.status_code in (200, 204)


# --- Notifications ---
def test_notifications(h):
    r = requests.get(f"{API}/notifications", headers=h, timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


# --- News ---
def test_news_feed(h):
    r = requests.get(f"{API}/news?limit=5", headers=h, timeout=40)
    assert r.status_code == 200, r.text[:300]


def test_news_impact(h):
    r = requests.get(f"{API}/news/impact?limit=5&ai=false", headers=h, timeout=60)
    assert r.status_code == 200, r.text[:300]


# --- Sentiment ---
def test_sentiment(h):
    r = requests.get(f"{API}/sentiment/RELIANCE", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]


# --- Strategy ---
def test_strategy_generate(h):
    r = requests.post(f"{API}/strategy/generate", headers=h, json={"prompt": "Generate a moderate-risk swing strategy for RELIANCE", "symbol": "RELIANCE"}, timeout=60)
    assert r.status_code == 200, r.text[:300]


def test_strategy_list(h):
    r = requests.get(f"{API}/strategy", headers=h, timeout=20)
    assert r.status_code == 200


# --- Opportunities ---
def test_opportunities(h):
    r = requests.get(f"{API}/opportunities?limit=5", headers=h, timeout=60)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    arr = body.get("items") if isinstance(body, dict) else body
    assert isinstance(arr, list) and len(arr) > 0, f"empty items: {body}"


# --- AI Models ---
def test_ai_models_crud(h):
    lst = requests.get(f"{API}/ai-models", headers=h, timeout=20)
    assert lst.status_code == 200
    c = requests.post(f"{API}/ai-models", headers=h, json={
        "provider": "anthropic", "model_name": "claude-sonnet-4-6", "api_key": "", "is_active": True
    }, timeout=20)
    assert c.status_code in (200, 201), c.text[:300]
    mid = c.json().get("id")
    if mid:
        d = requests.delete(f"{API}/ai-models/{mid}", headers=h, timeout=15)
        assert d.status_code in (200, 204)

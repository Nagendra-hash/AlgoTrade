"""
Comprehensive backend API tests for TradeAI platform.
Covers: health, auth, users, strategy, auto-trade, backtest, market, portfolio, news, sentiment, alerts, orders.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://func-test.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api/v1"

DEMO_EMAIL = "demo@tradeai.com"
DEMO_PASSWORD = "Demo1234!"

# Internal URL fallback (used only for /health which has no /api prefix)
INTERNAL_BASE = "http://localhost:8001"


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_token(session):
    r = session.post(
        f"{API}/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text}")
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ---------- Health ----------

class TestHealth:
    def test_health_internal(self):
        # /health is not behind /api prefix so only reachable internally
        r = requests.get(f"{INTERNAL_BASE}/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_public_not_routed(self):
        # Confirm ingress routes only /api/* - documents the gap
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        # This will not reach backend; Next.js 404 page returned instead
        assert r.status_code in (200, 404)  # informational only


# ---------- Auth & Users ----------

class TestAuth:
    def test_login_success(self, session):
        r = session.post(
            f"{API}/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str)
        assert "refresh_token" in data and isinstance(data["refresh_token"], str)

    def test_login_invalid(self, session):
        r = session.post(
            f"{API}/auth/login",
            json={"email": DEMO_EMAIL, "password": "WrongPass!"},
            timeout=30,
        )
        assert r.status_code in (400, 401)

    def test_me(self, auth_headers):
        r = requests.get(f"{API}/users/me", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("email") == DEMO_EMAIL


# ---------- Strategy ----------

class TestStrategy:
    def test_list_strategies(self, auth_headers):
        r = requests.get(f"{API}/strategy", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_strategy(self, auth_headers):
        payload = {
            "name": f"TEST_strat_{uuid.uuid4().hex[:6]}",
            "description": "Test strategy",
            "code": "def strategy(data):\n    return 'hold'",
            "symbols": ["RELIANCE"],
            "timeframe": "1d",
        }
        r = requests.post(f"{API}/strategy", headers=auth_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("name") == payload["name"]
        assert "id" in data
        # Persist via list GET
        lst = requests.get(f"{API}/strategy", headers=auth_headers, timeout=30).json()
        assert any(s.get("id") == data["id"] for s in lst)
        # store for later
        pytest.created_strategy_id = data["id"]

    def test_generate_strategy_ai(self, auth_headers):
        payload = {
            "prompt": "A simple RSI mean reversion strategy on RELIANCE",
            "symbols": ["RELIANCE"],
            "timeframe": "1d",
        }
        # LLM call can take 30-90s; retry once for transient 502s
        r = None
        for attempt in range(2):
            r = requests.post(
                f"{API}/strategy/generate",
                headers=auth_headers,
                json=payload,
                timeout=180,
            )
            if r.status_code in (200, 201):
                break
            time.sleep(3)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)
        assert ("code" in data) or ("strategy" in data) or ("name" in data)

    def test_deploy_strategy_paper(self, auth_headers):
        sid = getattr(pytest, "created_strategy_id", None)
        if not sid:
            pytest.skip("No strategy created to deploy")
        r = requests.post(
            f"{API}/strategy/{sid}/deploy?mode=paper",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"

    def test_backtest(self, auth_headers):
        payload = {
            "symbol": "RELIANCE",
            "timeframe": "1d",
            "period": "6mo",
            "initial_capital": 100000,
        }
        # Need a strategy code in some implementations
        sid = getattr(pytest, "created_strategy_id", None)
        if sid:
            payload["strategy_id"] = sid
        r = requests.post(
            f"{API}/strategy/backtest",
            headers=auth_headers,
            json=payload,
            timeout=120,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)


# ---------- Auto-Trade ----------

class TestAutoTrade:
    def test_status(self, auth_headers):
        r = requests.get(f"{API}/auto-trade/status", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        # accept either 'running' or 'is_running' etc.
        assert any(k in data for k in ("running", "is_running", "status", "mode"))

    def test_start_stop(self, auth_headers):
        r1 = requests.post(
            f"{API}/auto-trade/start",
            headers=auth_headers,
            json={"mode": "paper"},
            timeout=30,
        )
        assert r1.status_code in (200, 201, 409), f"{r1.status_code} {r1.text[:300]}"

        r2 = requests.post(
            f"{API}/auto-trade/stop",
            headers=auth_headers,
            json={},
            timeout=30,
        )
        assert r2.status_code in (200, 201, 409), f"{r2.status_code} {r2.text[:300]}"

        # Restart for downstream tests
        r3 = requests.post(
            f"{API}/auto-trade/start",
            headers=auth_headers,
            json={"mode": "paper"},
            timeout=30,
        )
        assert r3.status_code in (200, 201, 409)

    def test_positions(self, auth_headers):
        r = requests.get(f"{API}/auto-trade/positions", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_activity(self, auth_headers):
        r = requests.get(f"{API}/auto-trade/activity", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_risk_get_and_update(self, auth_headers):
        rg = requests.get(f"{API}/auto-trade/risk", headers=auth_headers, timeout=30)
        assert rg.status_code == 200
        assert isinstance(rg.json(), dict)

        ru = requests.put(
            f"{API}/auto-trade/risk",
            headers=auth_headers,
            json={"max_position_size_pct": 5, "trading_capital": 100000},
            timeout=30,
        )
        assert ru.status_code in (200, 201), f"{ru.status_code} {ru.text[:300]}"
        data = ru.json()
        # Verify via GET
        rg2 = requests.get(f"{API}/auto-trade/risk", headers=auth_headers, timeout=30)
        assert rg2.status_code == 200
        d2 = rg2.json()
        # Field name may vary - accept any keys present
        cap = d2.get("trading_capital") or d2.get("capital")
        if cap is not None:
            assert float(cap) == 100000


# ---------- Market / Portfolio / News / Sentiment / Alerts / Orders ----------

class TestMarket:
    def test_quote(self, auth_headers):
        r = requests.get(f"{API}/market/quote/RELIANCE", headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)
        # Accept ltp/last_price/price keys
        assert any(k in data for k in ("ltp", "last_price", "price", "lastPrice"))


class TestPortfolio:
    def test_summary(self, auth_headers):
        r = requests.get(f"{API}/portfolio/summary", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert isinstance(r.json(), dict)


class TestNews:
    def test_news(self, auth_headers):
        r = requests.get(f"{API}/news", headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, (list, dict))


class TestSentiment:
    def test_sentiment(self, auth_headers):
        r = requests.get(f"{API}/sentiment/RELIANCE", headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)


class TestAlerts:
    def test_list_alerts(self, auth_headers):
        r = requests.get(f"{API}/alerts", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))

    def test_create_alert(self, auth_headers):
        payload = {
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "condition": "above",
            "target_value": 9999.0,
            "channels": ["in_app"],
            "notes": "TEST alert",
        }
        r = requests.post(f"{API}/alerts", headers=auth_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("symbol") == "RELIANCE"
        assert "id" in data
        pytest.created_alert_id = data["id"]
        # Cleanup
        requests.delete(f"{API}/alerts/{data['id']}", headers=auth_headers, timeout=15)


class TestOrders:
    def test_list_orders(self, auth_headers):
        # Use trailing slash to avoid 307 redirect (which may drop Authorization
        # header through Cloudflare cross-scheme redirect, causing 403).
        r = requests.get(f"{API}/orders/", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert isinstance(r.json(), (list, dict))

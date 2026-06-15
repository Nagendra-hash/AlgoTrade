"""
Iter9 backend smoke — Trading Opportunities Buy/Watch/Avoid + Auto-Trade dashboard endpoints.
Path: backend/tests/test_iter9_opps_autotrade.py
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://5e0d847d-b059-4b8e-9818-9c3a87b9ce69.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/v1"

DEMO_EMAIL = "demo@tradeai.com"
DEMO_PASS = "Demo1234!"
TEST_SYMBOL = "TESTSYM"
TEST_AVOID_SYMBOL = "TESTAVOID"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"] if "access_token" in r.json() else r.json().get("token")


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Watchlist CRUD ──────────────────────────────────────────────

def test_watchlist_list(H):
    r = requests.get(f"{API}/watchlist", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "items" in j and "total" in j
    assert isinstance(j["items"], list)


def test_watchlist_cleanup_pre(H):
    # cleanup leftovers from prior runs
    for s in [TEST_SYMBOL, TEST_AVOID_SYMBOL, "TESTBUY"]:
        requests.delete(f"{API}/watchlist/{s}", headers=H, timeout=10)
        requests.delete(f"{API}/opportunities/{s}/avoid", headers=H, timeout=10)


# ── Opportunities feed ──────────────────────────────────────────

def test_opportunities_feed(H):
    r = requests.get(f"{API}/opportunities?limit=10", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "items" in j
    assert "avoided_count" in j
    assert isinstance(j["avoided_count"], int)


# ── Watch action ────────────────────────────────────────────────

def test_opp_watch_adds(H):
    body = {"symbol": TEST_SYMBOL, "exchange": "NSE", "snapshot": {"ltp": 100, "rsi": 55, "confidence": 70}}
    r = requests.post(f"{API}/opportunities/{TEST_SYMBOL}/watch", headers=H, json=body, timeout=15)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["action"] == "watch"
    assert j["symbol"] == TEST_SYMBOL
    assert j["added"] is True
    assert "watchlist_id" in j


def test_opp_watch_idempotent(H):
    body = {"symbol": TEST_SYMBOL, "exchange": "NSE", "snapshot": {"ltp": 101}}
    r = requests.post(f"{API}/opportunities/{TEST_SYMBOL}/watch", headers=H, json=body, timeout=15)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["added"] is False  # already present


def test_watchlist_contains_test_symbol(H):
    r = requests.get(f"{API}/watchlist", headers=H, timeout=15)
    assert r.status_code == 200
    items = r.json()["items"]
    syms = [it["symbol"] for it in items]
    assert TEST_SYMBOL in syms
    # snapshot persisted
    matching = next(it for it in items if it["symbol"] == TEST_SYMBOL)
    assert matching["snapshot"] is not None
    assert matching["source"] in ("watch", "buy")


# ── Avoid action ────────────────────────────────────────────────

def test_opp_avoid_adds(H):
    body = {"symbol": TEST_AVOID_SYMBOL, "exchange": "NSE", "notes": "test"}
    r = requests.post(f"{API}/opportunities/{TEST_AVOID_SYMBOL}/avoid", headers=H, json=body, timeout=15)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["action"] == "avoid"
    assert j["added"] is True


def test_opp_avoid_idempotent(H):
    body = {"symbol": TEST_AVOID_SYMBOL, "exchange": "NSE"}
    r = requests.post(f"{API}/opportunities/{TEST_AVOID_SYMBOL}/avoid", headers=H, json=body, timeout=15)
    assert r.status_code == 201, r.text
    assert r.json()["added"] is False


def test_opp_feed_reflects_avoided_count(H):
    r = requests.get(f"{API}/opportunities?limit=10", headers=H, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["avoided_count"] >= 1


def test_opp_unavoid(H):
    r = requests.delete(f"{API}/opportunities/{TEST_AVOID_SYMBOL}/avoid", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "unavoid"


# ── Buy action (creates strategy + refreshes engine) ────────────

def test_opp_buy_creates_strategy(H):
    snap = {"ltp": 200, "rsi": 62, "confidence": 75, "risk_level": "moderate", "recommended_action": "Buy", "ai_summary": "Test buy"}
    body = {"symbol": "TESTBUY", "exchange": "NSE", "snapshot": snap}
    r = requests.post(f"{API}/opportunities/TESTBUY/buy", headers=H, json=body, timeout=20)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["action"] == "buy"
    assert j["symbol"] == "TESTBUY"
    assert "watchlist_id" in j
    strat = j["strategy"]
    assert strat["type"] == "hybrid_trend_momentum"
    assert strat["stop_loss_pct"] == 2.0
    assert strat["take_profit_pct"] == 4.0
    assert "id" in strat


# ── Watchlist delete ────────────────────────────────────────────

def test_watchlist_delete_symbol(H):
    r = requests.delete(f"{API}/watchlist/{TEST_SYMBOL}", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["removed"] == TEST_SYMBOL


# ── Auto-Trade endpoints ────────────────────────────────────────

def test_autotrade_status(H):
    r = requests.get(f"{API}/auto-trade/status", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ["is_running", "mode", "active_strategies", "open_positions", "today_pnl", "win_rate", "risk_config"]:
        assert k in j, f"missing key {k} in status: {j}"


def test_autotrade_start_paper(H):
    r = requests.post(f"{API}/auto-trade/start", headers=H, json={"mode": "paper"}, timeout=20)
    assert r.status_code in (200, 201), r.text

    # Verify status flipped to running/paper
    s = requests.get(f"{API}/auto-trade/status", headers=H, timeout=15).json()
    assert s["is_running"] is True
    assert s["mode"] == "paper"


def test_autotrade_positions(H):
    r = requests.get(f"{API}/auto-trade/positions", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    # Should return either list or dict with positions key
    assert isinstance(j, (list, dict))


def test_autotrade_activity(H):
    r = requests.get(f"{API}/auto-trade/activity", headers=H, timeout=15)
    assert r.status_code == 200, r.text


def test_autotrade_risk_update(H):
    r = requests.put(
        f"{API}/auto-trade/risk",
        headers=H,
        json={"trading_capital": 150000, "max_daily_loss_pct": 5.0, "trailing_stop_enabled": True},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    # Verify via status
    s = requests.get(f"{API}/auto-trade/status", headers=H, timeout=15).json()
    rc = s["risk_config"]
    assert rc.get("trading_capital") == 150000
    assert rc.get("max_daily_loss_pct") == 5.0


def test_autotrade_stop(H):
    r = requests.post(f"{API}/auto-trade/stop", headers=H, timeout=15)
    assert r.status_code in (200, 201), r.text
    s = requests.get(f"{API}/auto-trade/status", headers=H, timeout=15).json()
    assert s["is_running"] is False


# ── Cleanup ─────────────────────────────────────────────────────

def test_zz_cleanup(H):
    for s in [TEST_SYMBOL, TEST_AVOID_SYMBOL, "TESTBUY"]:
        requests.delete(f"{API}/watchlist/{s}", headers=H, timeout=10)
        requests.delete(f"{API}/opportunities/{s}/avoid", headers=H, timeout=10)

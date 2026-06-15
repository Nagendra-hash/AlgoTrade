"""
Iteration 11 Backend Tests
Covers: Auth, Backtest, Risk-Hardening (circuit breaker / kill switch / broker
recovery), News-Driven Candidates pipeline.

Run:
  pytest /app/backend/tests/iteration_11_test.py -v \
    --junitxml=/app/test_reports/pytest/iteration_11.xml
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
DEMO_EMAIL = "demo@tradeai.com"
DEMO_PASSWORD = "Demo1234!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data and isinstance(data["access_token"], str)
    return data["access_token"]


@pytest.fixture(scope="module")
def auth(session, token):
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class TestAuth:
    def test_login_demo(self, token):
        assert token and len(token) > 20


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
class TestBacktest:
    def test_strategies(self, auth):
        r = auth.get(f"{BASE_URL}/api/v1/backtest/strategies", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # accept either list or dict with key
        items = body if isinstance(body, list) else (
            body.get("strategies") or body.get("data") or []
        )
        names = {
            (s.get("type") or s.get("id") or s.get("name") or s)
            if isinstance(s, dict) else s
            for s in items
        }
        expected = {
            "trend_following",
            "mean_reversion",
            "momentum",
            "hybrid_trend_momentum",
        }
        missing = expected - {str(n) for n in names}
        assert not missing, f"Missing strategies: {missing}. Got {names}"

    def test_run_backtest(self, auth):
        payload = {
            "symbol": "RELIANCE",
            "interval": "1d",
            "period": "1y",
            "strategy_type": "trend_following",
            "initial_capital": 1000000,
        }
        r = auth.post(
            f"{BASE_URL}/api/v1/backtest/run", json=payload, timeout=60
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data
        summary = data["summary"]
        for k in ("win_rate", "sharpe_ratio", "max_drawdown", "profit_factor"):
            assert k in summary, f"Missing summary.{k}; got {list(summary)}"
        assert "trades" in data and isinstance(data["trades"], list)
        assert "equity_curve" in data and isinstance(data["equity_curve"], list)

    def test_run_backtest_invalid_interval(self, auth):
        payload = {
            "symbol": "RELIANCE",
            "interval": "1x",
            "period": "1y",
            "strategy_type": "trend_following",
            "initial_capital": 1000000,
        }
        r = auth.post(
            f"{BASE_URL}/api/v1/backtest/run", json=payload, timeout=30
        )
        # Should be 400 (or 422 from Pydantic)
        assert r.status_code in (400, 422), (
            f"expected 400/422 got {r.status_code} body={r.text[:200]}"
        )


# ---------------------------------------------------------------------------
# Risk Hardening (Auto-Trade)
# ---------------------------------------------------------------------------
class TestRiskHardening:
    def _status(self, auth):
        r = auth.get(f"{BASE_URL}/api/v1/auto-trade/status", timeout=20)
        assert r.status_code == 200, r.text
        return r.json()

    def test_status_risk_state(self, auth):
        data = self._status(auth)
        assert "risk_state" in data, f"keys={list(data)}"
        rs = data["risk_state"]
        for k in (
            "circuit_breaker_active",
            "kill_switch_armed",
            "broker_failure_count",
            "daily_loss_used_pct",
            "trades_used_pct",
            "open_pos_used_pct",
        ):
            assert k in rs, f"Missing risk_state.{k}; got {list(rs)}"
        assert isinstance(rs["circuit_breaker_active"], bool)
        assert isinstance(rs["kill_switch_armed"], bool)
        assert isinstance(rs["broker_failure_count"], (int, float))

    def test_circuit_breaker_trip_and_reset(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/circuit-breaker/trip",
            json={}, timeout=15
        )
        assert r.status_code == 200, r.text
        rs = self._status(auth)["risk_state"]
        assert rs["circuit_breaker_active"] is True

        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/circuit-breaker/reset",
            json={}, timeout=15
        )
        assert r.status_code == 200, r.text
        rs = self._status(auth)["risk_state"]
        assert rs["circuit_breaker_active"] is False

    def test_kill_switch_arm_and_disarm(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/kill-switch/arm",
            json={}, timeout=15
        )
        assert r.status_code == 200, r.text
        rs = self._status(auth)["risk_state"]
        assert rs["kill_switch_armed"] is True

        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/kill-switch/disarm",
            json={}, timeout=15
        )
        assert r.status_code == 200, r.text
        rs = self._status(auth)["risk_state"]
        assert rs["kill_switch_armed"] is False

    def test_broker_recovery_reset(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/broker-recovery/reset",
            json={}, timeout=15
        )
        assert r.status_code == 200, r.text
        rs = self._status(auth)["risk_state"]
        assert rs["broker_failure_count"] == 0
        # broker_last_recovery_at should be present somewhere
        assert (
            "broker_last_recovery_at" in rs
            or "broker_last_recovery" in rs
        ), f"missing broker_last_recovery_at; got {list(rs)}"


# ---------------------------------------------------------------------------
# News-driven candidates pipeline
# ---------------------------------------------------------------------------
class TestNewsCandidates:
    def test_get_candidates(self, auth):
        r = auth.get(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates", timeout=20
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data and "candidates" in data
        s = data["summary"]
        for k in (
            "enabled",
            "candidates_total",
            "pending",
            "executed",
            "rejected",
            "last_run_iso",
            "next_run_in_sec",
        ):
            assert k in s, f"Missing summary.{k}; got {list(s)}"
        assert isinstance(data["candidates"], list)

    def test_scan_bypass_cooldown(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates/scan",
            json={}, timeout=45
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "message" in data
        assert data["message"].lower().startswith("scan")
        assert "result" in data
        assert "summary" in data

    def test_toggle_disable_enable(self, auth):
        # disable
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates/toggle",
            json={"enabled": False}, timeout=15
        )
        assert r.status_code == 200, r.text
        time.sleep(0.5)
        r = auth.get(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates", timeout=15
        )
        assert r.json()["summary"]["enabled"] is False
        # re-enable
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates/toggle",
            json={"enabled": True}, timeout=15
        )
        assert r.status_code == 200, r.text
        assert (
            auth.get(
                f"{BASE_URL}/api/v1/auto-trade/news-candidates", timeout=15
            ).json()["summary"]["enabled"]
            is True
        )

    def test_reset(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates/reset",
            json={}, timeout=15
        )
        assert r.status_code == 200, r.text
        s = auth.get(
            f"{BASE_URL}/api/v1/auto-trade/news-candidates", timeout=15
        ).json()["summary"]
        assert s["candidates_total"] == 0
        assert s["pending"] == 0

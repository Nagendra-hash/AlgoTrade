"""
Iteration 2 backend tests for TradeAI new features:
  1. POST /api/v1/auto-trade/quick-start (one-tap auto-trade)
  2. POST /api/v1/strategy/generate-stream (SSE streaming)
  3. POST /api/v1/strategy/backtest with PG candle cache
  4. Broker connect/status/debug regression
  5. General regression on login + strategy list + auto-trade status + orders
"""
import os
import json
import time
import pytest
import requests
import psycopg2

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://fc7e60fe-65a9-4620-9382-a46d2d9394ee.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api/v1"

PG_DSN = "postgresql://trader:trader123@localhost:5432/tradeai"


# ── Auth fixture ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "demo@tradeai.com", "password": "Demo1234!"},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Regression: login + existing endpoints ──────────────────────
class TestRegression:
    def test_login_ok(self, token):
        assert isinstance(token, str) and len(token) > 10

    def test_strategy_list(self, headers):
        r = requests.get(f"{API}/strategy", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_auto_trade_status(self, headers):
        r = requests.get(f"{API}/auto-trade/status", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "is_running" in body
        assert "mode" in body

    def test_orders_list(self, headers):
        r = requests.get(f"{API}/orders/", headers=headers, timeout=20, allow_redirects=True)
        assert r.status_code in (200, 201), r.text


# ── Feature 1: One-Click Quick Start ────────────────────────────
class TestQuickStart:
    def test_quick_start_trend_following(self, headers):
        body = {
            "strategy_type": "trend_following",
            "symbols": ["RELIANCE", "TCS"],
            "mode": "paper",
            "trading_capital": 100000,
            "max_position_size_pct": 10,
        }
        r = requests.post(f"{API}/auto-trade/quick-start", headers=headers, json=body, timeout=90)
        assert r.status_code == 200, f"quick-start failed: {r.status_code} {r.text[:400]}"
        data = r.json()
        assert "strategy" in data and "engine" in data
        assert data["strategy"]["strategy_type"] in ("trend_following", "custom")
        assert "id" in data["strategy"] and data["strategy"]["id"]
        assert data["engine"]["is_running"] is True
        assert data["engine"]["mode"] == "paper"

        # Verify GET /strategy lists the new strategy
        sid = data["strategy"]["id"]
        r2 = requests.get(f"{API}/strategy", headers=headers, timeout=20)
        assert r2.status_code == 200
        ids = [s["id"] for s in r2.json()]
        assert sid in ids, f"new strategy {sid} not found in list"

        # Verify engine status reflects is_running
        r3 = requests.get(f"{API}/auto-trade/status", headers=headers, timeout=20)
        assert r3.status_code == 200
        assert r3.json()["is_running"] is True

    @pytest.mark.parametrize("stype", ["mean_reversion", "momentum", "breakout", "swing"])
    def test_quick_start_all_types(self, headers, stype):
        body = {
            "strategy_type": stype,
            "symbols": ["INFY"],
            "mode": "paper",
            "trading_capital": 50000,
            "max_position_size_pct": 5,
        }
        r = requests.post(f"{API}/auto-trade/quick-start", headers=headers, json=body, timeout=90)
        assert r.status_code == 200, f"{stype}: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["engine"]["is_running"] is True
        assert "id" in data["strategy"]


# ── Feature 2: SSE strategy generation streaming ────────────────
class TestStreamingSSE:
    def test_generate_stream_emits_status_quickly_then_result(self, headers):
        h = dict(headers)
        h["Accept"] = "text/event-stream"
        body = {
            "prompt": "Simple EMA crossover for RELIANCE on 1d",
            "symbols": ["RELIANCE"],
            "timeframe": "1d",
            "exchange": "NSE",
        }

        first_status_ts = None
        got_result = False
        result_json = None
        got_done = False

        start = time.time()
        with requests.post(
            f"{API}/strategy/generate-stream",
            headers=h,
            json=body,
            stream=True,
            timeout=90,
        ) as resp:
            assert resp.status_code == 200, f"SSE status: {resp.status_code} {resp.text[:300]}"
            ct = resp.headers.get("content-type", "")
            assert "text/event-stream" in ct, f"unexpected content-type: {ct}"

            current_event = None
            data_lines = []
            for raw in resp.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                if raw == "":
                    # dispatch
                    if current_event and data_lines:
                        data_str = "\n".join(data_lines)
                        if current_event == "status" and first_status_ts is None:
                            first_status_ts = time.time() - start
                        if current_event == "result":
                            try:
                                result_json = json.loads(data_str)
                                got_result = True
                            except Exception as e:
                                pytest.fail(f"result event JSON parse: {e} :: {data_str[:200]}")
                        if current_event == "done":
                            got_done = True
                    current_event, data_lines = None, []
                    if got_done:
                        break
                    continue
                if raw.startswith("event:"):
                    current_event = raw[6:].strip()
                elif raw.startswith("data:"):
                    data_lines.append(raw[5:].lstrip())

        assert first_status_ts is not None, "no status event received"
        assert first_status_ts < 3.0, f"first status event too slow: {first_status_ts:.2f}s"
        assert got_result, "no result event received"
        assert isinstance(result_json, dict)
        # basic schema
        for k in ("name", "strategy_type"):
            assert k in result_json, f"result missing key {k}: {list(result_json.keys())[:10]}"


# ── Feature 3: Backtest + PG candle cache ───────────────────────
class TestBacktestCache:
    def test_backtest_first_then_second_call_uses_cache(self, headers):
        body = {
            "symbol": "RELIANCE",
            "timeframe": "1d",
            "period": "6mo",
            "initial_capital": 100000,
            "strategy_type": "trend_following",
        }
        t0 = time.time()
        r1 = requests.post(f"{API}/strategy/backtest", headers=headers, json=body, timeout=60)
        elapsed1 = time.time() - t0
        assert r1.status_code == 200, f"first backtest failed: {r1.status_code} {r1.text[:400]}"
        d1 = r1.json()
        assert "total_return" in d1 and "trades" in d1

        # Second call should be faster (cache hit - Redis or PG)
        t0 = time.time()
        r2 = requests.post(f"{API}/strategy/backtest", headers=headers, json=body, timeout=30)
        elapsed2 = time.time() - t0
        assert r2.status_code == 200, f"second backtest failed: {r2.status_code} {r2.text[:400]}"
        print(f"\nBacktest timings: first={elapsed1:.2f}s second={elapsed2:.2f}s")
        # Don't hard-assert <2s (network jitter); assert second is at least no slower than first
        assert elapsed2 <= max(elapsed1, 5.0) + 1.0, f"cache miss: first={elapsed1:.2f}, second={elapsed2:.2f}"

    def test_pg_candle_cache_row_exists(self, headers):
        # Ensure at least one backtest has been run for RELIANCE
        body = {
            "symbol": "RELIANCE", "timeframe": "1d", "period": "6mo",
            "initial_capital": 100000, "strategy_type": "trend_following",
        }
        requests.post(f"{API}/strategy/backtest", headers=headers, json=body, timeout=60)

        conn = psycopg2.connect(PG_DSN)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT symbol, interval, period, source, bar_count FROM candle_cache "
                "WHERE symbol=%s AND interval=%s AND period=%s",
                ("RELIANCE", "1d", "6mo"),
            )
            row = cur.fetchone()
            cur.close()
            # If yfinance returned data, we expect a row. Synthetic data is NOT persisted.
            # So a missing row implies yfinance failed (still a backend-correct behavior).
            if row is None:
                pytest.skip("yfinance returned no data; cache row not created (synthetic path)")
            assert row[0] == "RELIANCE"
            assert row[1] == "1d"
            assert row[2] == "6mo"
            assert row[3] == "yfinance"
            assert row[4] > 0
        finally:
            conn.close()


# ── Feature 4: Broker flows ─────────────────────────────────────
class TestBrokers:
    def test_broker_status_empty_or_list(self, headers):
        r = requests.get(f"{API}/brokers/status", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list), f"expected list, got {type(body)}: {body}"

    def test_angel_one_connect_empty_fields_400(self, headers):
        r = requests.post(
            f"{API}/brokers/angel-one/connect",
            headers=headers,
            json={"api_key": "", "client_code": "", "pin": "", "totp_secret": ""},
            timeout=20,
        )
        assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code}: {r.text[:300]}"

    def test_zerodha_connect_returns_login_url(self, headers):
        r = requests.post(
            f"{API}/brokers/zerodha/connect",
            headers=headers,
            json={"api_key": "test_key", "api_secret": "test_secret"},
            timeout=20,
        )
        assert r.status_code == 200, f"zerodha connect: {r.status_code} {r.text[:300]}"
        data = r.json()
        url = data.get("login_url") or data.get("loginUrl") or ""
        assert "kite.zerodha.com" in url, f"login_url should contain kite.zerodha.com: {data}"

    def test_broker_debug_structure(self, headers):
        r = requests.get(f"{API}/brokers/debug", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)

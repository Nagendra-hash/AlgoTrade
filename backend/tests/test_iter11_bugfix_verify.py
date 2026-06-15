"""Iter11 — verify the 3 bug fixes from iter9/iter10 report.

(1) HIGH:  auto_start=true when engine stopped → engine actually starts.
(2) MINOR: deploy → GET status shows new strategy in active_strategies immediately (no 30s lag).
(3) MINOR: ai_brain rule_fallback decisions are cached in Redis with TTL <= 60s.
"""
import os
import time
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend .env file load
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = f"{BASE_URL}/api/v1"
EMAIL = "demo@tradeai.com"
PASSWORD = "Demo1234!"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def session(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"})
    return s


# --- Bug #1: HIGH — auto_start path actually starts the engine ---
def test_bug1_auto_start_starts_engine(session):
    # 1. Stop the engine first
    stop = session.post(f"{API}/auto-trade/stop", timeout=30)
    assert stop.status_code in (200, 201), stop.text

    # Verify stopped
    status = session.get(f"{API}/auto-trade/status", timeout=30).json()
    assert status.get("is_running") is False, f"engine still running after stop: {status}"

    # 2. Deploy ai-brain with auto_start=true
    payload = {
        "symbols": ["RELIANCE", "TCS"],
        "timeframe": "1d",
        "exchange": "NSE",
        "mode": "paper",
        "auto_start": True,
    }
    r = session.post(f"{API}/auto-trade/ai-brain/deploy", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    body = r.json()

    # Engine should report started
    assert body.get("engine_started") is True, f"engine_started=False — BUG #1 not fixed: {body}"
    assert body.get("engine", {}).get("is_running") is True, f"engine.is_running=False: {body.get('engine')}"

    # 3. GET /status to double-confirm
    status2 = session.get(f"{API}/auto-trade/status", timeout=30).json()
    assert status2.get("is_running") is True, f"status.is_running=False: {status2}"


# --- Bug #2: MINOR — new strategy visible in active_strategies immediately (no 30s lag) ---
def test_bug2_no_active_strategies_lag(session):
    # snapshot active_strategies count
    before = session.get(f"{API}/auto-trade/status", timeout=30).json()
    before_count = before.get("active_strategies", 0)

    # Deploy a fresh ai-brain strategy
    payload = {
        "symbols": ["WIPRO", "BAJFINANCE"],
        "timeframe": "1d",
        "exchange": "NSE",
        "mode": "paper",
        "auto_start": False,
    }
    r = session.post(f"{API}/auto-trade/ai-brain/deploy", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text

    # Immediately GET status — must show incremented count (commit-before-refresh fix)
    after = session.get(f"{API}/auto-trade/status", timeout=30).json()
    after_count = after.get("active_strategies", 0)
    assert after_count > before_count, (
        f"active_strategies did not increase: before={before_count}, after={after_count} — "
        f"BUG #2 (commit-before-cache-refresh) not fixed"
    )


# --- Bug #3: MINOR — ai_brain rule_fallback decisions cached in Redis with TTL <= 60s ---
def test_bug3_rule_fallback_cached():
    """Inspect Redis directly via redis-cli (requires redis-cli installed in container)."""
    import subprocess

    # Allow up to ~45s for the engine to tick & cache rule_fallback decisions
    found_keys = []
    ttls = []
    for _ in range(9):  # 9 * 5s = 45s max
        time.sleep(5)
        try:
            keys_out = subprocess.run(
                ["redis-cli", "KEYS", "ai_brain:*"],
                capture_output=True, text=True, timeout=10,
            )
            keys = [k for k in keys_out.stdout.strip().split("\n") if k]
            if keys:
                found_keys = keys
                for k in keys[:5]:
                    ttl_out = subprocess.run(
                        ["redis-cli", "TTL", k],
                        capture_output=True, text=True, timeout=10,
                    )
                    try:
                        ttls.append(int(ttl_out.stdout.strip()))
                    except ValueError:
                        pass
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("redis-cli not available in test environment")

    assert found_keys, (
        "No ai_brain:* keys found in Redis after 45s of engine ticking — "
        "BUG #3 (rule_fallback never cached) not fixed OR engine not ticking"
    )

    # rule_fallback uses 60s TTL; successful LLM decisions use 300s. We just need at least one <= 60.
    assert any(0 < t <= 60 for t in ttls), (
        f"No ai_brain key has TTL <= 60s — rule_fallback short-TTL caching not active. TTLs: {ttls}"
    )

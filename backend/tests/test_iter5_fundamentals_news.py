"""
Iteration 5 backend tests — validates the two P1 deltas:
  1. Real fundamentals (market_cap / promoter / FII / DII) in /opportunities
  2. AI-upgraded /news/impact via ai_router.chat with rule-based fallback

Auth: demo@tradeai.com / Demo1234! (see /app/memory/test_credentials.md)
"""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://func-test.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/v1"

DEMO_EMAIL = "demo@tradeai.com"
DEMO_PASSWORD = "Demo1234!"


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(
        f"{API}/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No access_token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_session(session, token):
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ── 1. Login still works ──────────────────────────────────────────────────────
class TestAuth:
    def test_login_returns_access_token(self, session):
        r = session.post(
            f"{API}/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            timeout=20,
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data or "token" in data
        assert isinstance(data.get("access_token") or data.get("token"), str)


# ── 2. Opportunities with real fundamentals ───────────────────────────────────
class TestOpportunitiesFundamentals:
    """Verify P1 delta — real market_cap / promoter / FII / DII populated."""

    cached_items = None
    first_call_seconds = None

    def test_opportunities_first_call_returns_8_items(self, auth_session):
        t0 = time.time()
        r = auth_session.get(f"{API}/opportunities?limit=8", timeout=90)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:300]}"
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("opportunities") or []
        assert len(items) == 8, f"Expected 8 items, got {len(items)}"
        TestOpportunitiesFundamentals.cached_items = items
        TestOpportunitiesFundamentals.first_call_seconds = elapsed
        print(f"[opportunities first call] {elapsed:.2f}s  items={len(items)}")

    def test_market_cap_coverage_at_least_70pct(self, auth_session):
        items = TestOpportunitiesFundamentals.cached_items
        assert items, "depends on prior test"
        with_mc = [it for it in items if isinstance(it.get("market_cap"), (int, float)) and it["market_cap"]]
        coverage = len(with_mc) / len(items)
        sample = [(it.get("symbol"), it.get("market_cap")) for it in items]
        print(f"market_cap sample: {sample}")
        assert coverage >= 0.70, f"market_cap coverage only {coverage:.0%}: {sample}"
        # at least one should be a sensible INR int (> 1 crore)
        assert any(isinstance(it["market_cap"], int) and it["market_cap"] > 10_000_000 for it in with_mc)

    def test_shareholding_coverage_at_least_50pct(self, auth_session):
        items = TestOpportunitiesFundamentals.cached_items
        assert items, "depends on prior test"
        for key in ("promoter_holding", "fii_holding", "dii_holding"):
            with_val = [
                it for it in items
                if isinstance(it.get(key), (int, float)) and 0 <= it[key] <= 100
            ]
            coverage = len(with_val) / len(items)
            sample = [(it.get("symbol"), it.get(key)) for it in items]
            print(f"{key} coverage {coverage:.0%} sample: {sample}")
            assert coverage >= 0.50, f"{key} coverage only {coverage:.0%}: {sample}"

    def test_original_fields_still_present(self, auth_session):
        items = TestOpportunitiesFundamentals.cached_items
        assert items
        required = [
            "ltp", "rsi", "macd_state", "recommended_action", "ai_summary",
            "composite_score", "confidence", "high_52w", "low_52w", "risk_level",
        ]
        first = items[0]
        missing = [k for k in required if k not in first]
        assert not missing, f"Missing original fields: {missing}; got keys={list(first.keys())}"

    def test_opportunities_second_call_cache_under_3s(self, auth_session):
        t0 = time.time()
        r = auth_session.get(f"{API}/opportunities?limit=8", timeout=15)
        elapsed = time.time() - t0
        assert r.status_code == 200
        print(f"[opportunities second call] {elapsed:.2f}s")
        assert elapsed < 3.0, f"Second call took {elapsed:.2f}s — cache not working"


# ── 3. News impact with AI upgrade ────────────────────────────────────────────
class TestNewsImpactAI:
    first_call_seconds = None

    def test_news_impact_requires_auth(self, session):
        # Use a fresh session WITHOUT auth header
        s = requests.Session()
        r = s.get(f"{API}/news/impact?limit=10", timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text[:200]}"

    def test_news_impact_ai_true_returns_mixed(self, auth_session):
        t0 = time.time()
        r = auth_session.get(
            f"{API}/news/impact?limit=10&ai=true&ai_top_n=5",
            timeout=120,
        )
        elapsed = time.time() - t0
        TestNewsImpactAI.first_call_seconds = elapsed
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:300]}"
        body = r.json()
        print(f"[news/impact ai=true first] {elapsed:.2f}s  keys={list(body.keys())}")
        assert body.get("articles_analyzed") == 10, f"articles_analyzed={body.get('articles_analyzed')}"
        assert body.get("ai_analyzed") == 5, f"ai_analyzed={body.get('ai_analyzed')}"
        items = body.get("items") or []
        assert len(items) == 10, f"Got {len(items)} items"
        ai_items = [it for it in items if it.get("ai_powered") is True]
        assert len(ai_items) == 5, f"Expected 5 ai_powered=true, got {len(ai_items)}"
        # AI-powered items should carry ai_provider
        providers = [it.get("ai_provider") for it in ai_items]
        print(f"ai_providers: {providers}")
        assert all(p for p in providers), f"Some AI items missing ai_provider: {providers}"
        # Remaining 5 are rule-based fallback
        non_ai = [it for it in items if not it.get("ai_powered")]
        assert len(non_ai) == 5

    def test_news_impact_ai_false(self, auth_session):
        r = auth_session.get(f"{API}/news/impact?limit=10&ai=false", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ai_analyzed") == 0
        items = body.get("items") or []
        assert len(items) >= 1
        for it in items:
            assert not it.get("ai_powered"), f"Item should not be ai_powered when ai=false: {it.get('headline')}"

    def test_news_impact_second_call_cache_under_10s(self, auth_session):
        t0 = time.time()
        r = auth_session.get(
            f"{API}/news/impact?limit=10&ai=true&ai_top_n=5",
            timeout=30,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200
        print(f"[news/impact ai=true second] {elapsed:.2f}s (first was {TestNewsImpactAI.first_call_seconds:.2f}s)")
        assert elapsed < 10.0, f"Second AI call took {elapsed:.2f}s — per-article cache not working"
        # Should also be faster than first (allow 0.1s noise floor — both may be sub-100ms when Redis is pre-warmed)
        if TestNewsImpactAI.first_call_seconds and TestNewsImpactAI.first_call_seconds > 0.2:
            assert elapsed <= TestNewsImpactAI.first_call_seconds + 0.05, \
                f"Second {elapsed:.2f}s not faster than first {TestNewsImpactAI.first_call_seconds:.2f}s"


# ── 4. Regression tests ───────────────────────────────────────────────────────
class TestRegressions:
    def test_portfolio_summary_no_fake_data(self, auth_session):
        r = auth_session.get(f"{API}/portfolio/summary", timeout=15)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body.get("no_live_data") is True, f"Expected no_live_data=true: {body}"
        assert body.get("source") == "none", f"Expected source='none', got {body.get('source')}"

    def test_ai_models_providers_list(self, auth_session):
        r = auth_session.get(f"{API}/ai-models/providers", timeout=15)
        assert r.status_code == 200
        body = r.json()
        providers = body if isinstance(body, list) else body.get("providers") or body.get("items") or []
        assert len(providers) == 9, f"Expected 9 providers, got {len(providers)}: {providers}"

    def test_ai_models_full_crud_anthropic(self, auth_session):
        # CREATE
        r = auth_session.post(
            f"{API}/ai-models",
            json={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": ""},
            timeout=15,
        )
        assert r.status_code == 201, f"Create failed: {r.status_code} {r.text[:200]}"
        created = r.json()
        model_id = created.get("id")
        assert model_id, f"No id in created: {created}"

        try:
            # TEST connection
            r2 = auth_session.post(f"{API}/ai-models/{model_id}/test", timeout=30)
            assert r2.status_code == 200, f"Test status {r2.status_code}: {r2.text[:300]}"
            tb = r2.json()
            print(f"[ai-models test] {tb}")
            assert tb.get("ok") is True, f"Expected ok=true: {tb}"
            assert "Connection successful" in (tb.get("message") or ""), f"message={tb.get('message')}"
        finally:
            # DELETE
            r3 = auth_session.delete(f"{API}/ai-models/{model_id}", timeout=15)
            assert r3.status_code in (200, 204), f"Delete status {r3.status_code}: {r3.text[:200]}"

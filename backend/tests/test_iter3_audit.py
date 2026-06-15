"""
Iteration 3 backend tests for TradeAI audit/transform.

Covers:
- Auth login (demo user)
- AI Models CRUD + activate + test
- Opportunities engine
- News impact analysis
- Portfolio no_live_data behavior
- Market quotes (Yahoo Finance v8)
- News listing & screener
- Removed endpoints (geo-monitor)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pro-quant-trading.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/v1"

DEMO_EMAIL = "demo@tradeai.com"
DEMO_PASSWORD = "Demo1234!"

SUPPORTED_PROVIDERS = {
    "openai", "anthropic", "gemini", "openrouter",
    "groq", "deepseek", "mistral", "perplexity", "ollama",
}


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(session):
    r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data, f"no access_token in {data}"
    return data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- auth ----------
class TestAuth:
    def test_login_demo(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10


# ---------- ai models ----------
class TestAIModels:
    def test_providers_list(self, session):
        r = session.get(f"{API}/ai-models/providers", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Accept either {"providers":[...]} or list
        if isinstance(body, dict):
            providers = body.get("providers") or body.get("items") or []
        else:
            providers = body
        ids = set()
        for p in providers:
            if isinstance(p, str):
                ids.add(p.lower())
            elif isinstance(p, dict):
                pid = (p.get("id") or p.get("name") or p.get("provider") or "").lower()
                if pid:
                    ids.add(pid)
        missing = SUPPORTED_PROVIDERS - ids
        assert not missing, f"missing providers in /ai-models/providers: {missing}; got {ids}"

    def test_initial_list_empty(self, session, auth_headers):
        # Clean up any existing configs first to ensure starting state
        r = session.get(f"{API}/ai-models", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        items = body if isinstance(body, list) else body.get("items", [])
        # Delete leftover configs from prior runs
        for it in items:
            cid = it.get("id")
            if cid:
                session.delete(f"{API}/ai-models/{cid}", headers=auth_headers, timeout=10)
        # Re-list
        r2 = session.get(f"{API}/ai-models", headers=auth_headers, timeout=15)
        assert r2.status_code == 200
        body2 = r2.json()
        items2 = body2 if isinstance(body2, list) else body2.get("items", [])
        assert items2 == [], f"expected empty list, got {items2}"

    def test_full_ai_model_lifecycle(self, session, auth_headers):
        # CREATE / upsert (universal key path: api_key empty)
        payload = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "api_key": "",
        }
        r = session.post(f"{API}/ai-models", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
        created = r.json()
        assert created.get("provider") == "anthropic"
        assert created.get("model") == "claude-sonnet-4-6"
        # api_key_preview should be null/None for universal-key path
        assert created.get("api_key_preview") in (None, "", "null"), f"expected null preview, got {created.get('api_key_preview')}"
        cid = created.get("id")
        assert cid

        # ACTIVATE
        r2 = session.post(f"{API}/ai-models/{cid}/activate", headers=auth_headers, timeout=15)
        assert r2.status_code in (200, 201, 204), f"activate failed: {r2.status_code} {r2.text}"
        # Verify is_active=true
        r3 = session.get(f"{API}/ai-models", headers=auth_headers, timeout=15)
        items = r3.json() if isinstance(r3.json(), list) else r3.json().get("items", [])
        target = next((x for x in items if x.get("id") == cid), None)
        assert target is not None
        assert target.get("is_active") is True, f"is_active not true: {target}"

        # TEST endpoint - real LLM call. Should return 200 with ok bool either way.
        r4 = session.post(f"{API}/ai-models/{cid}/test", headers=auth_headers, timeout=90)
        assert r4.status_code == 200, f"test endpoint not 200: {r4.status_code} {r4.text}"
        tb = r4.json()
        assert "ok" in tb, f"missing 'ok' in response: {tb}"
        assert isinstance(tb["ok"], bool)
        if not tb["ok"]:
            assert "message" in tb or "error" in tb, f"ok=false but no message: {tb}"

        # DELETE
        r5 = session.delete(f"{API}/ai-models/{cid}", headers=auth_headers, timeout=15)
        assert r5.status_code in (200, 204), f"delete failed: {r5.status_code} {r5.text}"

        # Verify removed
        r6 = session.get(f"{API}/ai-models", headers=auth_headers, timeout=15)
        items6 = r6.json() if isinstance(r6.json(), list) else r6.json().get("items", [])
        assert not any(x.get("id") == cid for x in items6), "config still present after delete"


# ---------- opportunities ----------
class TestOpportunities:
    def test_opportunities_list(self, session, auth_headers):
        r = session.get(f"{API}/opportunities?limit=10", headers=auth_headers, timeout=120)
        assert r.status_code == 200, f"opportunities failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        items = body.get("items") if isinstance(body, dict) else body
        assert isinstance(items, list)
        assert len(items) >= 1, f"expected items, got {len(items)}"
        # Validate first item shape
        first = items[0]
        for field in ("ltp", "rsi", "composite_score", "recommended_action", "ai_summary"):
            assert field in first, f"missing field '{field}' in opportunity: {list(first.keys())}"
        assert first["ltp"] is not None
        assert first["rsi"] is not None
        assert first["composite_score"] is not None
        assert first["recommended_action"] is not None
        assert isinstance(first["ai_summary"], str)


# ---------- news impact ----------
class TestNewsImpact:
    def test_news_impact(self, session, auth_headers):
        # generous timeout for first call (LLM + RSS)
        r = session.get(f"{API}/news/impact?limit=5", headers=auth_headers, timeout=180)
        assert r.status_code == 200, f"news/impact failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        assert "articles_analyzed" in body
        assert body["articles_analyzed"] >= 1, f"articles_analyzed={body['articles_analyzed']}"
        assert "items" in body and isinstance(body["items"], list)
        assert body.get("no_live_data") is False
        assert "top_stocks" in body
        assert "top_sectors" in body
        first = body["items"][0]
        assert "affected_stocks" in first
        assert isinstance(first["affected_stocks"], list)
        assert first.get("impact_direction") in {"positive", "negative", "neutral"}
        conf = first.get("confidence")
        assert conf is not None and 0 <= float(conf) <= 100, f"confidence out of range: {conf}"


# ---------- portfolio no_live_data ----------
class TestPortfolioNoLiveData:
    def test_summary_no_live_data(self, session, auth_headers):
        r = session.get(f"{API}/portfolio/summary", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("no_live_data") is True, f"expected no_live_data=true, got {body}"
        assert body.get("source") == "none", f"expected source='none', got source={body.get('source')}"
        assert body.get("source") != "sample"

    def test_positions_empty(self, session, auth_headers):
        r = session.get(f"{API}/portfolio/positions", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("positions") == [], f"expected positions=[], got {body.get('positions')}"
        assert body.get("no_live_data") is True

    def test_funds_no_live_data(self, session, auth_headers):
        r = session.get(f"{API}/portfolio/funds", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("no_live_data") is True
        assert body.get("source") == "none", f"expected source='none', got {body.get('source')}"
        assert body.get("source") != "sample"


# ---------- market ----------
class TestMarket:
    def test_indices(self, session, auth_headers):
        r = session.get(f"{API}/market/indices", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        # accept list or {indices:[...]}/{items:[...]} shape
        items = body if isinstance(body, list) else (body.get("indices") or body.get("items") or [])
        symbols_found = set()
        for it in items:
            sym = (it.get("symbol") or it.get("name") or "").upper()
            symbols_found.add(sym)
            if it.get("ltp") is not None:
                assert isinstance(it["ltp"], (int, float))
        # require all 3 indices to be present
        for must in ("NIFTY50", "BANKNIFTY", "SENSEX"):
            assert any(must in s for s in symbols_found), f"missing index {must} in {symbols_found}"

    def test_quote_reliance(self, session, auth_headers):
        r = session.get(f"{API}/market/quote/RELIANCE", headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"quote failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        # field can be nested under data or top-level
        q = body.get("data") if isinstance(body, dict) and "data" in body else body
        assert q.get("ltp") is not None
        assert isinstance(q["ltp"], (int, float))
        assert q.get("change_pct") is not None
        assert q.get("volume") is not None


# ---------- news ----------
class TestNews:
    def test_news_list(self, session, auth_headers):
        r = session.get(f"{API}/news?per_page=5", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        items = body.get("items") if isinstance(body, dict) else body
        if items is None and isinstance(body, dict):
            items = body.get("articles") or body.get("news") or []
        assert isinstance(items, list)
        assert len(items) >= 1, f"expected >=1 article, got {len(items)}"

    def test_news_screener(self, session, auth_headers):
        r = session.get(f"{API}/news/screener?limit=5", headers=auth_headers, timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        # accept list, items, or recommendations key
        recs = None
        if isinstance(body, dict):
            recs = body.get("recommendations") or body.get("items")
        if recs is None and isinstance(body, list):
            recs = body
        assert recs is not None, f"no recommendations key in {body}"
        assert isinstance(recs, list)


# ---------- removed endpoints ----------
class TestRemoved:
    def test_geo_monitor_removed(self, session, auth_headers):
        r = session.get(f"{API}/news/geo-monitor", headers=auth_headers, timeout=15)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"

    def test_geo_monitor_history_removed(self, session, auth_headers):
        r = session.get(f"{API}/news/geo-monitor/history", headers=auth_headers, timeout=15)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"

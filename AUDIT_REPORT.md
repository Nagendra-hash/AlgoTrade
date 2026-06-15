# TradeAI — Phase 1 Full Project Audit

## 1. Files / Modules to REMOVE (decorative, off-scope, or dead)

| Path | Purpose | Action | Reason |
|------|---------|--------|--------|
| `frontend/src/app/admin/` | Admin panel UI | **REMOVE** | Not in target navigation; admin handled via backend only |
| `frontend/src/app/backtest/` | Backtesting page | **REMOVE** | Not in target nav (functionality folded into Strategies page where needed) |
| `frontend/src/app/geo-monitor/` | Geopolitical world-map dashboard | **REMOVE** | Decorative; off-scope for focused algo trading. News impact handled inside `/alerts-news`. |
| `frontend/src/app/marketplace/` | Strategy marketplace | **REMOVE** | Not in target nav |
| `frontend/src/app/risk/` | Risk manager page | **REMOVE** | Folded into Portfolio summary |
| `frontend/src/app/auto-trade/` | Auto-trade dashboard | **REMOVE** | Folded into `/strategies` (live deploy + monitor inline) |
| `frontend/src/app/settings/` | Generic settings | **RENAME → `broker-settings/`** | Keep only broker config (Phase 3 nav requires "Broker Settings") |
| `frontend/src/app/ai-chat/` | AI chat page | **RENAME → `ai-assistant/`** | Match required nav label |
| `frontend/src/app/strategy/` | Strategy builder | **RENAME → `strategies/`** | Match required nav label |
| `frontend/src/app/market/` | Market quotes/chart | **RENAME → `markets/`** | Match required nav label |
| `backend/app/api/v1/news.py::geo-monitor*` | Geo dashboard endpoints | **REMOVE endpoints** | Geo-monitor page removed |

## 2. Files / Modules to REFACTOR (remove mocks / show "No live data")

| Path | What to change |
|------|----------------|
| `backend/app/api/v1/portfolio.py` | Return `{"no_data": true}` envelope when no broker session; never fake holdings |
| `backend/app/api/v1/orders.py` | Return empty list when no orders; remove sample seed |
| `backend/app/services/news_service.py` | Already real (RSS+NewsAPI+Finnhub). Keep, expand impact analysis. |
| `backend/seed_demo.py` | Keep demo user **only**; remove any fake holdings/strategies seeding |
| `backend/app/services/portfolio_broadcaster.py` | Verify zero-fake; emit `{positions: []}` when none |
| `frontend/src/app/dashboard/page.tsx` | Replace any placeholder widgets with empty state CTAs |

## 3. New Files to CREATE

| Path | Purpose |
|------|---------|
| `frontend/src/app/trading-opportunities/page.tsx` | Phase 4 — pro table of top opportunities |
| `frontend/src/app/ai-models/page.tsx` | Phase 6 — manage LLM providers + Ollama |
| `frontend/src/app/watchlist/page.tsx` | Phase 3 nav item |
| `frontend/src/app/positions/page.tsx` | Phase 3 nav item |
| `frontend/src/app/alerts-news/` (rename from alerts) | Phase 3 nav: "Alerts & News" |
| `frontend/src/components/news/NewsImpactPanel.tsx` | Phase 5 — Affected Stocks panel |
| `backend/app/api/v1/opportunities.py` | Aggregator endpoint for Trading Opportunities table |
| `backend/app/api/v1/ai_models.py` | CRUD for user AI model configs (API keys + provider) |
| `backend/app/models/ai_model_config.py` | DB model: per-user AI provider rows |
| `backend/app/services/ai_router.py` | Multi-provider LLM dispatcher w/ fallback chain |
| `backend/app/services/opportunity_engine.py` | Composes opportunities from screener+news+sentiment |
| `backend/app/services/news_impact.py` | Phase 5 — per-article impact analyzer |

## 4. Database changes
- New table `ai_model_configs` (provider, api_key encrypted, model, temperature, max_tokens, system_prompt, is_active, fallback_order)
- Migration `005_ai_model_configs.py`

## 5. Dependencies
- Remove unused frontend libs: `react-simple-maps` (geo monitor only)
- Backend additions: `ollama` python client (optional)

## 6. Final navigation (Phase 3)
1. Dashboard
2. Markets
3. Watchlist
4. Trading Opportunities
5. Orders
6. Positions
7. Portfolio
8. Alerts & News
9. Strategies
10. AI Assistant
11. AI Models
12. Broker Settings

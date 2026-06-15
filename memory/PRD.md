# TradeAI — Product Requirements Document

## Original problem statement
Audit, clean up, and transform the existing **AlgoTrade** GitHub project
(https://github.com/Nagendra-hash/AlgoTrade.git) into a focused, real-data-only
Algorithmic Trading Platform. Eight phases: audit → fake-data removal → focused
navigation → new Trading Opportunities page → news impact analysis → multi-provider
AI Model Management → performance → final validation.

## Tech stack (existing — kept as-is)
- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind + React Query + Zustand
- **Backend**: FastAPI (Python 3.11) + SQLAlchemy 2 async + Alembic
- **DB**: PostgreSQL 15 + Redis 7
- **AI**: emergentintegrations (Claude/OpenAI/Gemini via universal key) + direct REST for OpenRouter, Groq, DeepSeek, Mistral, Perplexity + Ollama for local
- **Market data**: Yahoo Finance v8 REST (working) + Angel One + Zerodha (when broker connected)
- **News**: Moneycontrol / Economic Times / Foreign Policy RSS + NewsAPI + Finnhub

## User personas
- **Retail Indian algo trader** with a Zerodha or Angel One account who wants AI-assisted screening, alerts, and execution.

## Core requirements (locked)
1. Real data only (no fake portfolios, holdings, P&L). Show "No live data available" when no broker is connected.
2. Single fixed navigation: Dashboard / Markets / Watchlist / Trading Opportunities / Orders / Positions / Portfolio / Alerts & News / Strategies / AI Assistant / AI Models / Broker Settings.
3. Bring-your-own-key AI provider management with automatic fallback chain.

## Implementation status (2026-06-15)

### Phase 1 — Audit & cleanup ✅
Deleted: `frontend/src/app/admin`, `backtest`, `geo-monitor`, `marketplace`, `risk`, `auto-trade`. Removed `geo-monitor*` endpoints from `news.py`. Removed `useBacktest.ts`, `useAutoTrade.ts`. Marketplace hook stubbed. `react-simple-maps` uninstalled. Full audit report at `/app/AUDIT_REPORT.md`.

### Phase 2 — Fake data removal ✅
`portfolio.py` summary / positions / funds now return `source: "none"` + `no_live_data: true` instead of sample data. Dashboard rebuilt to drop hardcoded fallback numbers (1,284,500 / 8,240 / 42,180 etc.) and instead show `—` placeholders + empty states.

### Phase 3 — Streamlined nav ✅
Sidebar rebuilt with the exact 12-item layout, grouped Trade / Execution / Intelligence / Account. Folder renames: `market→markets`, `strategy→strategies`, `ai-chat→ai-assistant`, `settings→broker-settings`, `alerts→alerts-news`. New folders: `watchlist`, `positions`, `trading-opportunities`, `ai-models`.

### Phase 4 — Trading Opportunities ✅
- Backend: `app/services/opportunity_engine.py` composes screener (RSI, MACD, momentum, trend, mean-reversion) + sentiment + 52-week range. Endpoint: `GET /api/v1/opportunities`.
- Frontend: `/trading-opportunities` shows the full pro table (Symbol, Company, LTP, Δ%, Volume, News Sentiment, Bull, Bear, Promoter %, FII %, DII %, M-Cap, Sector, RSI, MACD, 52W H/L, Risk, Confidence, Action) + AI summary panel.
- Promoter/FII/DII/M-Cap are explicitly `null` (UI shows `—`) until a real fundamentals provider is wired.

### Phase 5 — News impact ✅
- Backend: `app/services/news_impact.py` + `GET /api/v1/news/impact` per-article direction / confidence / affected stocks + sectors.
- Frontend: `components/news/NewsImpactPanel.tsx` plus new **Impact** tab on `/alerts-news`.

### Phase 6 — AI Model Management ✅
- DB: `ai_model_configs` table (migration `005_ai_model_configs.py`).
- Backend: `app/services/ai_router.py` (multi-provider dispatcher w/ fallback) + `app/api/v1/ai_models.py` (CRUD, test, activate, reorder, chat).
- Frontend: `/ai-models` provider grid (9 providers) + fallback-chain editor + connection-test probe + delete.

### Phase 7 — Perf hardening ✅
- Replaced broken `yfinance` calls in `stock_screener.py` with Yahoo Finance v8 REST (the same fast path market.py already used).
- Pinned `openai==1.99.9` + `httpx==0.28.1` to fix emergentintegrations probe errors.
- Postgres + Redis installed and persistent in container.

### Phase 8 — Final validation ✅
- Backend: testing_agent_v3 iter3 → **15/15 PASS**.
- Frontend: testing_agent_v3 iter4 → **13/13 PASS**.
- Demo login → JWT → all new pages render with the required data-testids.

## Files added / modified / removed

### Removed (frontend)
`src/app/admin/`, `src/app/backtest/`, `src/app/geo-monitor/`, `src/app/marketplace/`, `src/app/risk/`, `src/app/auto-trade/`, `src/hooks/useBacktest.ts`, `src/hooks/useAutoTrade.ts`.

### Renamed
`market→markets`, `strategy→strategies`, `ai-chat→ai-assistant`, `settings→broker-settings`, `alerts→alerts-news`.

### New
- `frontend/src/app/trading-opportunities/page.tsx`
- `frontend/src/app/ai-models/page.tsx`
- `frontend/src/app/watchlist/page.tsx`
- `frontend/src/app/positions/page.tsx`
- `frontend/src/components/news/NewsImpactPanel.tsx`
- `backend/app/api/v1/ai_models.py`
- `backend/app/api/v1/opportunities.py`
- `backend/app/services/ai_router.py`
- `backend/app/services/opportunity_engine.py`
- `backend/app/services/news_impact.py`
- `backend/app/models/ai_model_config.py`
- `backend/alembic/versions/005_ai_model_configs.py`
- `AUDIT_REPORT.md`

### Modified
- `backend/app/main.py` (registers ai_models + opportunities routers)
- `backend/app/api/v1/news.py` (added /impact, removed /geo-monitor*)
- `backend/app/api/v1/portfolio.py` (Phase 2 — no-fake-data invariant)
- `backend/app/services/stock_screener.py` (Yahoo v8 REST instead of yfinance)
- `backend/requirements.txt` (openai 1.99.9, httpx 0.28.1)
- `frontend/src/components/layout/Sidebar.tsx` (new 12-item nav)
- `frontend/src/components/layout/DashboardLayout.tsx` + `Topbar.tsx` (path renames)
- `frontend/src/app/dashboard/page.tsx` (real-only stats + empty states)
- `frontend/src/app/alerts-news/page.tsx` (new Impact tab)
- `frontend/src/hooks/useStrategies.ts` (marketplace stub)
- `frontend/package.json` (yarn start uses next dev for hot reload + removed react-simple-maps)

## Prioritized backlog
- P1: Wire **real fundamentals** (Promoter / FII / DII / Market Cap) into Trading Opportunities — currently `null` → "—". Candidates: NSE bhavcopy / Alpha Vantage / Tijori.
- P1: Per-article **Claude impact analysis** (currently rule-based via news_impact). Route through `ai_router.chat` for high-confidence rows.
- P2: Persisted server-side watchlist (currently localStorage-only).
- P2: Strategies page link to **AI Models** — let user pick which provider generates the strategy.
- P3: Ollama local model auto-detect (list installed models from `GET /api/tags`).
- P3: Move AI Models system_prompt to a per-task templates picker.

## Functional test — 2026-06-15 (iter7)
Full re-test after env recreate (Postgres + Redis re-installed, .env files re-created, migrations + demo seed re-run, datastores added to supervisor).

- **Backend**: 20/20 pytest GREEN on `test_iter6_full_smoke.py` (auth, /me, market, portfolio invariant, orders, alerts CRUD, notifications, news, sentiment, strategy, opportunities, ai-models)
- **Frontend**: login → /dashboard works; all 12 sidebar routes navigate cleanly; empty-states correct (no forbidden fake numbers); Trading Opportunities pro table renders; AI Models 9-provider grid renders
- **Datastores**: Postgres + Redis now under `/etc/supervisor/conf.d/supervisord_datastores.conf` so they auto-restart (iter6 single-point-of-failure resolved)

### Open low-priority items (non-blocking)
- P3: `SentimentBadge` renders `<button>` nested inside another `<button>` → React hydration warning
- P3: `Invalid language tag: en-US@posix` runtime error on some pages (normalise locale before passing to `Intl`)
- P3: Portfolio header still says "Showing real portfolio data from Angel One ()" when broker is disconnected — show "Broker not connected" instead

## Iter8 — live integration wiring (2026-06-15)

### Added
- **OpenAI direct fallback** in `backend/app/services/sentiment_service.py` (`_openai_direct`) and `backend/app/api/v1/strategy.py`. When `EMERGENT_LLM_KEY` is absent but `OPENAI_API_KEY` is set, both endpoints call `gpt-4o-mini` directly. Currently 429-blocked by quota on the supplied key.
- **OpenAI direct path** in `backend/app/services/ai_router.py` (`_call_openai_direct`) — when user's `cfg.api_key` starts with `sk-`, the router calls `api.openai.com/v1/chat/completions` directly instead of going through `emergentintegrations.LlmChat`.
- **Telegram alerts**: per-user `telegram_bot_token` + `telegram_chat_id` stored on the demo user. Alert engine already wires this — verified end-to-end (Telegram API HTTP 200, message delivered to user's phone).

### Fixed (low-priority items from iter7)
- `SentimentBadge` no longer renders `<button>` inside `<button>` (changed wrapper to `<span role="button">`).
- `toLocaleTimeString()` in SentimentBadge now explicitly passes `"en-IN"` to avoid `en-US@posix` `Intl` errors.
- Portfolio header now distinguishes 3 states: `Live data from Angel One · {client_id}` / `Broker connected — waiting for live holdings` / `Broker not connected — connect Angel One in Settings`.

### Broker live
- Angel One connected for demo user as `N513357` (session in `broker_connections` table, persistent across restarts).

### Open
- OpenAI quota top-up still needed by user before AI sentiment/strategy go live.
- OpenRouter key not yet provided — once user hands over `sk-or-...`, register via `POST /api/v1/ai-models`.

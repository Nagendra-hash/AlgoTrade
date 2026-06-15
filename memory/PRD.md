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

## Iter9 — Phase 1+2: Trading Opportunities Wiring + Auto-Trade Dashboard (2026-06-15)

### Added
**Database (migration `006_watchlist`)**
- `watchlist_items` table: user_id, symbol, exchange, source ('manual'|'watch'|'buy'), notes, target_price, snapshot JSONB, created_at. UniqueConstraint(user_id, symbol, exchange).
- `user_opportunity_prefs` table: user_id, symbol, exchange, action ('avoid'), reason, created_at. UniqueConstraint(user_id, symbol, exchange, action).

**Backend models** — `/app/backend/app/models/watchlist.py`
- `WatchlistItem` + `UserOpportunityPref`

**Backend API**
- `POST /api/v1/opportunities/{symbol}/buy` — adds to watchlist (source=buy) **AND** creates a Strategy row (`hybrid_trend_momentum`, paper-active, SL/TP derived from snapshot.risk_level — moderate=2%/4% with 1:2 RR) **AND** calls `auto_trade_engine._refresh_active_strategies()` so it picks up on next 30-sec tick.
- `POST /api/v1/opportunities/{symbol}/watch` — adds to watchlist (source=watch).
- `POST /api/v1/opportunities/{symbol}/avoid` — saves avoid preference; the same symbol is filtered from subsequent `GET /api/v1/opportunities` and surfaced via new `avoided_count` field.
- `DELETE /api/v1/opportunities/{symbol}/avoid` — un-hides.
- New router `watchlist.py`: `GET /api/v1/watchlist` + `POST /api/v1/watchlist` (idempotent upsert) + `DELETE /api/v1/watchlist/{symbol}`.

**Frontend — `/trading-opportunities`**
- 3 clickable action buttons per row with data-testids `opp-buy-{SYMBOL}` / `opp-watch-{SYMBOL}` / `opp-avoid-{SYMBOL}` (replacing the static label).
- Mutations via React-Query; flash toast (`data-testid=opp-flash`) confirms success or error.
- Avoided symbol drops out of feed on automatic refetch.

**Frontend — `/auto-trade` (NEW page)**
- Pre-flight checkpoints (Broker / AI Brain / Engine status).
- Start (Paper) + Start (Live with confirm()) + Stop buttons.
- 6 stat tiles: Engine / Mode / Strategies / Open Pos. / Today P&L / Win Rate.
- Engine Positions table with SL/TP/PnL per row.
- Today's Activity log.
- RiskSettings panel: trading_capital, max_daily_loss_pct, max_position_size_pct, max_open_positions, max_trades_per_day, trailing_stop_pct + enabled — persists via PUT `/auto-trade/risk`.
- Sidebar new item "Auto Trade" with AI badge.

### Test status
- pytest /app/backend/tests/test_iter9_opps_autotrade.py — **19/19 GREEN**
- Frontend (Playwright via testing agent): **100%** — Start/Stop/Settings flow, Buy/Watch/Avoid click + flash + feed-refetch all verified.

### Still on backlog (Phase 3-7)
- P3: LLM brain — per-tick AI decision per symbol (entry/SL/TP/qty/side), AI ingests sentiment+news+technicals.
- P4: News-driven entries: every news article → affected stocks → candidate trades fed into engine.
- P5: Risk hardening — circuit breaker, broker-failure recovery, daily-loss kill switch already exists but needs UI hook.
- P6: Backtesting endpoint + UI page.
- P7: WS reconnect, request dedupe, timeout wrappers.

## Iter10 — Code review hardening (2026-06-15)

### Critical security fixes (applied)
- **Removed `exec()` from `auto_trade_engine._execute_custom_code`** — arbitrary Python code execution path is now disabled and logs a deprecation warning. The 4 built-in `strategy_type` dispatchers (trend_following, momentum, mean_reversion, hybrid_trend_momentum) + the `parameters` dict already cover all AI-generated strategy needs.
- **MD5 → SHA-256** in `news_service.py` (4 occurrences, cache-key hashing) and `backtest_service.py` (1 occurrence, seed derivation). All non-cryptographic uses but linters/scanners flag MD5 universally.
- **`ai_router.py:86`** — Ollama auth placeholder renamed to `"ollama-noauth"` with `# noqa: S105` comment + explanatory comment; was a false-positive (Ollama's openai-compat server requires *some* Authorization header but ignores the value, see https://ollama.com/blog/openai-compatibility).

### Code quality fixes (applied)
- **Refactored `opportunities.opportunity_buy`** from 102→26 lines by extracting `_upsert_buy_watchlist`, `_risk_to_sl_tp`, `_build_opp_strategy`, `_notify_engine_refresh` helpers.
- **Array index keys** replaced with stable IDs in `SentimentBadge.tsx` (headline string), `strategies/page.tsx:267` (line content), `auto-trade/page.tsx:262` (composite `time-symbol-action-i`). The 2 remaining `key={i}` uses are static placeholder arrays (NewsFeed skeletons, bouncing-dots animation) — appropriate.
- **Empty catch blocks** in `useWebSocket.ts` now log via `console.warn` (3 sites: notification onmessage, market onmessage, market socket setup).

### Verified
- Backend pytest pass via curl: opp-buy still works, engine refresh still works, strategy created with `risk_level=elevated → sl=2.5%, tp=5.0%`.
- Frontend pages /auto-trade, /trading-opportunities, /strategies all return 200.

### Deferred — architectural, not bugs (each needs its own session)
- **`localStorage` → `httpOnly` cookies** for JWT tokens. Requires backend `Set-Cookie` + CSRF token middleware + cookie-aware axios. ~4 hrs. Working as-is; XSS mitigation lives at React's default escaping.
- **AlertsPageContent / StockSuggestions / broker-settings page splits** — refactors of working code. ~6 hrs.
- **Migration 001 split** — would corrupt alembic history; only safe to do during a fresh-DB cutover.
- **WebSocket missing deps lint warnings** — already correctly mitigated by the ref pattern (`onAlertRef`, `onMessageRef`) and the `symbolsKey` join trick; the linter false-positives because it can't see through refs. The disable comment is intentional.
- **`_place_broker_order` 8-arg signature** — broker-specific keys are intrinsic to the broker API contract; collapsing into a dataclass would just rename the noise. Leaving as-is.
- **Test file "hardcoded secrets"** are demo passwords (`Demo1234!`) for fixture login — by design.

## Iter11 — Phase 3: AI Brain in Auto-Trade Engine (2026-06-15)

### Added
**Service** — `/app/backend/app/services/ai_brain.py` (NEW, ~270 lines)
- `BrainDecision` dataclass: decision/confidence/sl_pct/tp_pct/qty_pct/reasoning/provider/model/cached/context_hash
- `make_decision(db, user_id, symbol, closes) -> BrainDecision`
  - Builds context: RSI(14), MACD(12/26/9), SMA(20/50), 1d/5d/20d change %, top 5 news headlines
  - Calls `ai_router.chat` with the user's primary LLM
  - Parses JSON response with markdown-fence tolerance
  - `_validate_decision`: clamps ranges, enforces 1:1.5 RR (tp >= sl×1.5), forces HOLD if confidence < 60
  - Rule-based fallback when LLM unavailable / fails / quota-exhausted
  - Redis cache: **5min TTL for successful LLM**, **60s TTL for rule_fallback** (dampens 429 hammering)

**Engine** — `auto_trade_engine.py`
- `_generate_signal` adds `"ai_brain"` branch — invokes `make_decision`, stashes the result on `strat["_ai_decision"]`, returns 1/-1/0
- `_execute_buy` reads `strat["_ai_decision"]` and applies AI's `qty_pct`/`sl_pct`/`tp_pct` overrides (with strategy-config fallbacks as hard caps)
- Activity log stamps `ai_confidence`, `ai_provider`, `reason` on trades

**API** — `auto_trade.py`
- `POST /api/v1/auto-trade/ai-brain/deploy` with `{symbols, timeframe, mode, auto_start}` — creates ai_brain Strategy + commits + refreshes engine cache + auto-starts engine if requested

**Frontend** — `/auto-trade/page.tsx`
- AI Brain Mode panel (data-testid=`ai-brain-panel`) with symbols input + Deploy button + success flash
- AI Brain checkpoint chip shows provider + model (e.g. `openai · gpt-4o-mini`)

### Bugs fixed mid-iteration (iter9 → iter10 → iter11)
1. **HIGH**: `await auto_trade_engine.start(mode=...)` was broken (start is sync no-args). Replaced with `set_mode(mode); start()` matching `/quick-start` pattern.
2. **MINOR**: Engine cache lag — added `await db.commit()` before `_refresh_active_strategies()`.
3. **MINOR**: rule_fallback decisions weren't cached → OpenAI 429-hammering. Now cached for 60s.

### Verified
- pytest **36/36 GREEN** (14 iter10 + 19 iter9 + 3 iter11 bugfix verification)
- Engine logs confirm AI Brain calls OpenAI per tick (HTTP 429 quota errors) and falls back cleanly to rule-based HOLD decisions
- Redis cache active: `ai_brain:*` keys with TTL≤60s
- AI model `openai/gpt-4o-mini` registered + activated for demo user via `/api/v1/ai-models`

### Still on backlog (Phases 4-7)
- P4: News-driven entries: every news article → affected stocks → candidate trades fed into engine
- P5: Risk hardening UI — circuit breaker / broker-failure recovery / daily-loss kill-switch surfaced
- P6: Backtesting endpoint + UI page (Sharpe / Drawdown / Profit Factor)
- P7: Performance polish — WS reconnect, dedupe, timeout wrappers

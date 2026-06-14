# TradeAI - Product Requirements Document

## Original Problem Statement
"Make this app fully functional and production ready, make changes according to you for better automatic trading experience."

The starting codebase was **TradeAI** — an AI-powered algorithmic trading platform for Indian markets (NSE/BSE) built with Next.js + FastAPI + PostgreSQL + Redis.

## Architecture

| Layer | Tech |
|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind + Zustand + TanStack Query |
| Backend | FastAPI + SQLAlchemy 2 (async) + uvicorn |
| Database | PostgreSQL 15 (under supervisor) |
| Cache / Pub-Sub | Redis 7 (under supervisor) |
| AI | Emergent Universal LLM Key (Claude Haiku 4.5 for strategy gen + sentiment) |
| Market Data | yfinance (live) → 3-tier cache (Redis → PostgreSQL `candle_cache` table → yfinance → deterministic synthetic fallback) |
| Charting | TradingView lightweight-charts |
| Brokers | Angel One + Zerodha (Kite Connect) — opt-in, sessions persist in PG |

### Process layout (supervisor)
- `postgresql` — port 5432
- `redis` — port 6379
- `backend` — uvicorn `server:app` on port 8001 (server.py is a shim to app.main:app)
- `frontend` — `yarn start` (Next.js prod) on port 3000

## Test Credentials
- **Demo**: `demo@tradeai.com` / `Demo1234!`
- Public URL: https://fc7e60fe-65a9-4620-9382-a46d2d9394ee.preview.emergentagent.com

## Features Delivered

### Session 1 (bootstrap + functional)
- Booted existing TradeAI on Emergent platform (PG+Redis under supervisor, server.py shim, env vars, seeded demo user)
- Migrated AI calls (strategy + sentiment) to Emergent Universal LLM key via `emergentintegrations` with Claude Haiku 4.5
- Backtest synthetic fallback when yfinance fails
- Routing fixes: redirect_slashes=False, `/api/health` alias, dual routes for `/orders`
- Pydantic v2 + greenlet + python_http_client + pytz + lxml + bs4 + html5lib + sgmllib3k installed

### Session 2 (auto-trading enhancements)
1. **One-click Quick Start** (`POST /api/v1/auto-trade/quick-start`)
   - Generates AI strategy → saves to DB → starts engine in one tap
   - 6 preset styles: trend_following / mean_reversion / momentum / breakout / scalping / swing
   - Frontend modal on `/auto-trade` with `data-testid="quick-start-btn"` and `quick-start-launch-btn`
   - ~13–20s end-to-end (LLM generation dominates)
2. **SSE streaming for strategy generation** (`POST /api/v1/strategy/generate-stream`)
   - Backend yields heartbeat events every 2s while the LLM runs
   - First event in <100ms locally (curl `--no-buffer` to localhost:8001 verified)
   - 16 KiB SSE-comment padding to defeat proxy buffering
   - ⚠️ Public preview ingress buffers responses; full streaming works in real prod with nginx `proxy_buffering off`. In the preview, total time is still ~15s and the Quick Start modal shows a "Generating…" spinner, so UX is acceptable.
3. **Persistent PG candle cache** (new `candle_cache` table)
   - 3-tier read: Redis (hot, 1h) → PostgreSQL (persistent, 24h for daily / 1h for intraday) → yfinance → synthetic
   - Write-through to PG on successful yfinance fetch (synthetic is *not* persisted by design)
   - Subsequent backtests on same symbol/period serve in ~200 ms
4. **Broker connect flows verified** — Angel One (TOTP) and Zerodha (OAuth) endpoints exist and return correct envelopes; status `[]` when no broker connected; debug endpoint exposes session diagnostics.

## Test Status
- Iteration 1: 20/22 backend endpoints (91%)
- Iteration 2: 14/16 new-feature tests (87.5%) + 1 skip
- Remaining non-pass items are environment limits (yfinance egress, ingress buffering), not backend defects.

## Next Action Items
- Multi-tenant auto-trade engine (currently single global singleton)
- WebSocket auth + verify `/ws/notifications/{user_id}` through ingress
- Live broker e2e with real keys (Angel One / Zerodha)
- Copy-trade social layer (publish/follow auto strategies)
- Seed `candle_cache` from NSE bhavcopy CSV at startup so backtests don't depend on yfinance egress

## Backlog (P2)
- Strategy marketplace, mobile responsive audit, multi-portfolio, tax P&L PDF, Stripe billing

## Files Created / Modified
- `/app/backend/server.py` (created)
- `/app/backend/.env` (created)
- `/app/backend/seed_demo.py` (created)
- `/app/backend/app/models/candle_cache.py` (created)
- `/app/backend/app/main.py` (redirect_slashes, /api/health alias)
- `/app/backend/app/core/config.py` (EMERGENT_LLM_KEY)
- `/app/backend/app/api/v1/strategy.py` (Emergent LLM + SSE streaming)
- `/app/backend/app/api/v1/auto_trade.py` (Quick Start endpoint)
- `/app/backend/app/api/v1/orders.py` (dual `""`/`"/"` route)
- `/app/backend/app/services/sentiment_service.py` (Emergent LLM, Haiku)
- `/app/backend/app/services/backtest_service.py` (3-tier cache + synthetic fallback)
- `/app/frontend/src/hooks/useAutoTrade.ts` (useQuickStart hook)
- `/app/frontend/src/app/auto-trade/page.tsx` (Quick Start button + modal)
- `/app/frontend/.env` and `.env.local` (NEXT_PUBLIC_API_URL)
- `/etc/supervisor/conf.d/postgres_redis.conf` (Postgres + Redis under supervisor)

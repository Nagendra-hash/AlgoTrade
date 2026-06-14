# TradeAI — AI-Powered Algorithmic Trading Platform

A full-stack, production-ready algorithmic trading platform for Indian markets (NSE/BSE) with AI strategy generation, real-time alerts, news sentiment analysis, and broker integrations.

---

## 🚀 Quick Start

### Option 1 — Automated (Recommended)
```bash
git clone <repo-url> tradeai && cd tradeai
bash setup.sh      # installs everything, creates demo user
bash start.sh      # starts all services
```

### Option 2 — Docker Compose
```bash
cp backend/.env.example backend/.env  # fill in your API keys
docker-compose up --build
```

### Option 3 — Manual
```bash
# Terminal 1 — Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
docker compose up postgres redis -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

---

## 🔐 Demo Credentials
| Field    | Value              |
|----------|--------------------|
| Email    | demo@tradeai.com   |
| Password | Demo1234!          |
| API Docs | http://localhost:8000/api/docs |

---

## 📋 Environment Variables

### backend/.env
```env
# ── Required ──────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://trader:trader123@localhost:5432/tradeai
DATABASE_SYNC_URL=postgresql://trader:trader123@localhost:5432/tradeai
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-change-this-in-production
JWT_SECRET_KEY=your-jwt-secret-change-this-in-production

# ── AI (at least one recommended) ─────────────────────────────
ANTHROPIC_API_KEY=sk-ant-api03-...   # Claude (best quality)
OPENAI_API_KEY=sk-...                # GPT-4o (fallback)

# ── News (optional — RSS feeds work without these) ─────────────
NEWSAPI_KEY=your-newsapi-key
FINNHUB_KEY=your-finnhub-key

# ── Broker APIs (optional — paper trading works without) ───────
ANGEL_ONE_API_KEY=
ANGEL_ONE_CLIENT_ID=
ANGEL_ONE_PASSWORD=
ANGEL_ONE_TOTP_SECRET=
ZERODHA_API_KEY=
ZERODHA_API_SECRET=

# ── Notifications (optional) ───────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── Tuning ─────────────────────────────────────────────────────
ALERT_CHECK_INTERVAL_SECONDS=15
SENTIMENT_CACHE_MINUTES=15
MAX_ALERTS_PER_USER=50
DEBUG=true
```

### frontend/.env.local
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=TradeAI
```

---

## 🏗️ Project Structure

```
tradeai/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── auth.py           # signup, login, refresh
│   │   │   ├── users.py          # /me + get_current_user dep
│   │   │   ├── market.py         # quotes, candles, search, indices
│   │   │   ├── orders.py         # place, list, cancel orders
│   │   │   ├── portfolio.py      # holdings, summary, positions
│   │   │   ├── alerts.py         # CRUD + pause/resume
│   │   │   ├── notifications.py  # list, mark-read, delete
│   │   │   ├── news.py           # paginated news feed
│   │   │   ├── sentiment.py      # AI sentiment analysis
│   │   │   ├── strategy.py       # AI generation + CRUD
│   │   │   └── admin.py          # stats, user management
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic settings from .env
│   │   │   ├── database.py       # Async SQLAlchemy engine
│   │   │   ├── security.py       # JWT + bcrypt
│   │   │   └── redis.py          # Redis helpers
│   │   ├── models/
│   │   │   ├── user.py           # User, UserRole
│   │   │   ├── order.py          # Order, enums
│   │   │   ├── strategy.py       # Strategy, StrategyStatus
│   │   │   └── alert.py          # Alert, Notification, SentimentCache
│   │   ├── schemas/
│   │   │   ├── user.py           # UserCreate, UserResponse, TokenResponse
│   │   │   ├── order.py          # PlaceOrderRequest, OrderResponse
│   │   │   ├── strategy.py       # StrategyCreate, StrategyResponse
│   │   │   └── alert.py          # AlertCreate, SentimentResponse, etc.
│   │   ├── services/
│   │   │   ├── alert_engine.py   # Background price poller (15s interval)
│   │   │   ├── news_service.py   # RSS + NewsAPI + Finnhub aggregator
│   │   │   └── sentiment_service.py # Claude → OpenAI → rule-based
│   │   ├── websockets/
│   │   │   ├── notification_ws.py # User-specific alert delivery
│   │   │   └── market_ws.py       # Live price streaming
│   │   └── main.py               # FastAPI app + lifespan
│   ├── alembic/
│   │   └── versions/001_initial_schema.py
│   ├── tests/
│   │   └── test_main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx        # Root layout with providers
│       │   ├── page.tsx          # Landing page
│       │   ├── not-found.tsx     # 404 page
│       │   ├── login/page.tsx    # Auth — login
│       │   ├── signup/page.tsx   # Auth — signup
│       │   ├── dashboard/page.tsx# Main dashboard
│       │   ├── market/page.tsx   # Candlestick chart + watchlist
│       │   ├── portfolio/page.tsx# Holdings table + P&L
│       │   ├── orders/page.tsx   # Order book + placement
│       │   ├── strategy/page.tsx # AI strategy builder
│       │   ├── alerts/page.tsx   # News feed + alerts panel
│       │   └── settings/page.tsx # Broker config + preferences
│       ├── components/
│       │   ├── layout/           # Sidebar, Topbar, DashboardLayout
│       │   ├── providers/        # QueryProvider, ThemeProvider
│       │   ├── alerts/           # AlertBell, AlertCard, AlertsManager, CreateAlertModal
│       │   ├── news/             # NewsCard, NewsFeed
│       │   └── sentiment/        # SentimentBadge, MarketSentimentWidget
│       ├── hooks/                # useAlerts, useMarket, useOrders, usePortfolio,
│       │                         # useSentiment, useNews, useStrategies, useWebSocket
│       ├── store/                # authStore (Zustand), notificationStore
│       ├── types/index.ts        # All TypeScript interfaces
│       └── lib/                  # api.ts (axios), utils.ts
│
├── docker-compose.yml
├── setup.sh
├── start.sh
└── stop.sh
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/signup | Create account |
| POST | /api/v1/auth/login | Get JWT tokens |
| POST | /api/v1/auth/refresh | Refresh access token |
| GET | /api/v1/users/me | Get current user |
| GET | /api/v1/market/quote/{symbol} | Live price quote |
| GET | /api/v1/market/candles/{symbol} | OHLCV candle data |
| GET | /api/v1/market/indices | NIFTY, BANKNIFTY, SENSEX |
| GET | /api/v1/market/search | Symbol search |
| POST | /api/v1/orders/place | Place order |
| GET | /api/v1/orders/ | List orders |
| GET | /api/v1/portfolio/holdings | Portfolio holdings |
| GET | /api/v1/portfolio/summary | P&L summary |
| GET | /api/v1/alerts | List alerts |
| POST | /api/v1/alerts | Create alert |
| POST | /api/v1/alerts/{id}/pause | Pause alert |
| POST | /api/v1/alerts/{id}/resume | Resume alert |
| GET | /api/v1/notifications | List notifications |
| POST | /api/v1/notifications/read | Mark read |
| GET | /api/v1/news | News feed |
| GET | /api/v1/sentiment/{symbol} | AI sentiment |
| POST | /api/v1/sentiment/bulk | Bulk sentiment |
| POST | /api/v1/strategy/generate | Generate strategy (no save) |
| POST | /api/v1/strategy/generate-and-save | Generate + save |
| GET | /api/v1/strategy | List my strategies |
| POST | /api/v1/strategy/{id}/deploy | Deploy to paper/live |
| WS | /ws/notifications/{user_id} | Real-time alerts |
| WS | /ws/market | Live price stream |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 App Router, TypeScript, Tailwind CSS |
| State | Zustand (auth + notifications), React Query (server state) |
| Charts | lightweight-charts (TradingView-style), Recharts |
| Backend | FastAPI, Python 3.11, Pydantic v2 |
| Database | PostgreSQL 15 + SQLAlchemy 2 async |
| Cache | Redis 7 (quotes, sentiment, news) |
| Auth | JWT (access 30min + refresh 7d) + bcrypt |
| AI | Claude (primary), GPT-4o (fallback), rule-based (offline) |
| Market Data | yfinance (NSE + BSE via Yahoo Finance) |
| Real-time | WebSockets (FastAPI native) |
| Migrations | Alembic |
| Deployment | Docker Compose |

---

## 🧪 Running Tests

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## 🔧 Troubleshooting

### Backend won't start
```bash
# Check logs
tail -f /tmp/tradeai-backend.log

# Verify DB connection
cd backend && python3 -c "from app.core.config import settings; print(settings.DATABASE_URL)"

# Re-run migrations
cd backend && alembic upgrade head
```

### Frontend can't reach backend
```bash
# Check .env.local
cat frontend/.env.local
# Should show: NEXT_PUBLIC_API_URL=http://localhost:8000

# Test backend health
curl http://localhost:8000/health
```

### Sentiment not working
- Add `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `backend/.env`
- Without keys, rule-based fallback is used automatically (confidence: ~50%)

### Alerts not triggering
- Alert engine runs every 15 seconds
- Check `ALERT_CHECK_INTERVAL_SECONDS` in `.env`
- Market must be open for ABOVE/BELOW triggers (NSE: 9:15–15:30 IST)

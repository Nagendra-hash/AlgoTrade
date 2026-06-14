"""
FastAPI application entry point — all routes, middleware, lifespan.
Path: backend/app/main.py
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, users, brokers, market, orders, portfolio, alerts, notifications, news, sentiment, strategy, admin
from app.api.v1 import auto_trade
from app.websockets.notification_ws import notification_ws_endpoint
from app.services.alert_engine import alert_engine
from app.services.portfolio_broadcaster import portfolio_broadcaster
from app.services.auto_trade_engine import auto_trade_engine
from app.services.angel_one import load_all_active_sessions as load_angel_sessions
from app.services.zerodha import load_all_active_sessions as load_zerodha_sessions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 TradeAI Platform starting up...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables verified")

    # Load active broker sessions from database so connections survive restarts
    angel_count = await load_angel_sessions()
    if angel_count:
        logger.info(f"✅ Loaded {angel_count} Angel One session(s) from database")
    zerodha_count = await load_zerodha_sessions()
    if zerodha_count:
        logger.info(f"✅ Loaded {zerodha_count} Zerodha session(s) from database")

    alert_engine.start()
    logger.info(f"✅ Alert engine started (interval={settings.ALERT_CHECK_INTERVAL_SECONDS}s)")
    portfolio_broadcaster.start()
    auto_trade_engine.start()
    logger.info("✅ Auto-trade engine started")
    yield
    auto_trade_engine.stop()
    portfolio_broadcaster.stop()
    alert_engine.stop()
    logger.info("🛑 TradeAI Platform shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── REST Routes ───────────────────────────────────────────────
app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(market.router,        prefix="/api/v1/market",        tags=["Market"])
app.include_router(orders.router,        prefix="/api/v1/orders",        tags=["Orders"])
app.include_router(portfolio.router,     prefix="/api/v1/portfolio",     tags=["Portfolio"])
app.include_router(alerts.router,        prefix="/api/v1/alerts",        tags=["Alerts"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(news.router,          prefix="/api/v1/news",          tags=["News"])
app.include_router(sentiment.router,     prefix="/api/v1/sentiment",     tags=["Sentiment"])
app.include_router(strategy.router,      prefix="/api/v1/strategy",      tags=["Strategy"])
app.include_router(brokers.router, prefix="/api/v1/brokers", tags=["Brokers"])
app.include_router(admin.router,         prefix="/api/v1/admin",         tags=["Admin"])
app.include_router(auto_trade.router,     prefix="/api/v1/auto-trade",     tags=["Auto Trade"])

# ── WebSocket Routes ──────────────────────────────────────────
@app.websocket("/ws/notifications/{user_id}")
async def ws_notifications(websocket: WebSocket, user_id: str):
    await notification_ws_endpoint(websocket, user_id)


@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    from app.websockets.market_ws import market_ws_endpoint
    # Optional user_id query param for broker-aware data source
    user_id = websocket.query_params.get("user_id")
    await market_ws_endpoint(websocket, user_id=user_id)


# ── Health Checks ─────────────────────────────────────────────
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "alert_engine": alert_engine.is_running,
        "auto_trade_engine": auto_trade_engine.is_running,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "status": "online",
    }

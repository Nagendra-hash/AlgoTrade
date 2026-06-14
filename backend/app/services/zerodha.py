"""
Zerodha Kite Connect service — market data via REST + WebSocket streaming.
Path: backend/app/services/zerodha.py

Provides:
  - Session management (store/retrieve access tokens via DB)
  - Market quotes (LTP, OHLC) via KiteConnect REST API
  - Historical candle data via KiteConnect REST API
  - Real-time WebSocket streaming via KiteTicker (background thread)
"""
import asyncio
import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.broker import BrokerConnection

logger = logging.getLogger(__name__)

KITE_BASE = "https://api.kite.trade"

# In-memory session cache (reuses Angel One's pattern)
_session_cache: dict = {}

# ── Symbol → instrument token mapping for NSE equities ──────
# Zerodha instrument tokens for common NSE symbols
# These are stable numeric tokens from Zerodha's master contract
NSE_INSTRUMENT_TOKENS: dict[str, int] = {
    "RELIANCE": 738561, "TCS": 2953217, "INFY": 408065,
    "HDFCBANK": 341249, "ICICIBANK": 1270529, "SBIN": 779521,
    "WIPRO": 199177, "BAJFINANCE": 4268801, "TATAMOTORS": 884737,
    "HINDUNILVR": 1394, "ADANIENT": 1594, "BHARTIARTL": 2714625,
    "ASIANPAINT": 2953217, "MARUTI": 4264193, "SUNPHARMA": 3409921,
    # Indices
    "NIFTY50": 256265, "BANKNIFTY": 260105, "SENSEX": 265,
}


def _kite_headers(access_token: str, api_key: str) -> dict:
    return {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}",
    }


# ── Session management ──────────────────────────────────────

async def _load_from_db(user_id: str) -> Optional[dict]:
    """Load Zerodha session from database."""
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.user_id == user_id,
                    BrokerConnection.is_active == True,
                    BrokerConnection.broker_name == "zerodha",
                ).order_by(BrokerConnection.created_at.desc()).limit(1)
            )
            bc = r.scalar_one_or_none()
            if bc and bc.jwt_token:
                data = {
                    "access_token": bc.jwt_token,
                    "api_key": bc.api_key,
                    "client_id": bc.client_id,
                    "login_id": bc.client_id,
                    "token_expires_at": bc.token_expires_at,
                    "db_id": str(bc.id),
                }
                _session_cache[str(user_id)] = data
                logger.info(f"Loaded Zerodha session from DB for user {user_id[:8]}")
                return data
    except Exception as e:
        logger.error(f"Failed to load Zerodha session: {e}")
    return None


async def _save_to_db(user_id: str, data: dict) -> None:
    """Save Zerodha session to database."""
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.user_id == user_id,
                    BrokerConnection.broker_name == "zerodha",
                    BrokerConnection.is_active == True,
                )
            )
            bc = r.scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if bc:
                bc.jwt_token = data.get("access_token", bc.jwt_token)
                bc.client_id = data.get("login_id", bc.client_id)
                bc.last_connected_at = now
                bc.is_active = True
                bc.error_message = None
                if data.get("access_token"):
                    bc.token_expires_at = now + timedelta(days=1)
            else:
                import uuid
                bc = BrokerConnection(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    broker_name="zerodha",
                    api_key=data.get("api_key", ""),
                    client_id=data.get("login_id", ""),
                    jwt_token=data.get("access_token"),
                    is_active=True,
                    last_connected_at=now,
                    token_expires_at=(now + timedelta(days=1) if data.get("access_token") else None),
                )
                db.add(bc)

            await db.commit()
            logger.info(f"Zerodha session saved to DB for user {str(user_id)[:8]}")
    except Exception as e:
        logger.error(f"Failed to save Zerodha session: {e}")


async def get_session(user_id: str) -> Optional[dict]:
    """Get Zerodha session — cache first, then DB."""
    uid = str(user_id)
    if uid in _session_cache:
        return _session_cache[uid]
    return await _load_from_db(uid)


async def store_session(
    user_id: str,
    access_token: str,
    api_key: str,
    login_id: str,
) -> None:
    """Store Zerodha session in DB and cache."""
    data = {
        "access_token": access_token,
        "api_key": api_key,
        "login_id": login_id,
    }
    await _save_to_db(str(user_id), data)
    _session_cache[str(user_id)] = {**data, "token_expires_at": None, "db_id": None}
    logger.info(f"Zerodha session stored for user {str(user_id)[:8]}")


async def clear_session(user_id: str) -> None:
    """Remove Zerodha session."""
    _session_cache.pop(str(user_id), None)
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.user_id == user_id,
                    BrokerConnection.broker_name == "zerodha",
                    BrokerConnection.is_active == True,
                )
            )
            bc = r.scalar_one_or_none()
            if bc:
                bc.is_active = False
                bc.jwt_token = None
                await db.commit()
                logger.info(f"Zerodha session cleared for user {user_id[:8]}")
    except Exception as e:
        logger.error(f"Failed to clear Zerodha session: {e}")


async def load_all_active_sessions() -> int:
    """Load all active Zerodha sessions into cache on startup."""
    count = 0
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.is_active == True,
                    BrokerConnection.broker_name == "zerodha",
                    BrokerConnection.jwt_token.isnot(None),
                )
            )
            connections = r.scalars().all()
            for bc in connections:
                uid = str(bc.user_id)
                _session_cache[uid] = {
                    "access_token": bc.jwt_token,
                    "api_key": bc.api_key,
                    "login_id": bc.client_id,
                    "token_expires_at": bc.token_expires_at,
                    "db_id": str(bc.id),
                }
                count += 1
        if count:
            logger.info(f"Loaded {count} active Zerodha session(s) from database")
    except Exception as e:
        logger.error(f"Failed to load Zerodha sessions: {e}")
    return count


# ── OAuth: Login / Token exchange ──────────────────────────

async def login(api_key: str, api_secret: str, request_token: str) -> dict:
    """
    Exchange request_token for access_token using Zerodha's API.
    This is called after the user completes OAuth login on Zerodha.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                f"{KITE_BASE}/session/token",
                data={
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "request_token": request_token,
                },
            )
            data = resp.json()
            if "access_token" in data:
                return {
                    "success": True,
                    "access_token": data["access_token"],
                    "login_id": data.get("user_id", data.get("login_id", "")),
                    "user_name": data.get("user_name", ""),
                    "user_short": data.get("user_short", ""),
                    "user_type": data.get("user_type", ""),
                }
            return {"success": False, "error": data.get("error_description", "Token exchange failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Market Data ─────────────────────────────────────────────

def _get_kite_symbol(symbol: str, exchange: str = "NSE") -> str:
    """Convert our symbol format to Kite's trading symbol format."""
    sym = symbol.upper()
    if sym in ("NIFTY50", "BANKNIFTY", "SENSEX"):
        # Indices
        index_map = {"NIFTY50": "NIFTY 50", "BANKNIFTY": "NIFTY BANK", "SENSEX": "SENSEX"}
        return f"{exchange}:{index_map.get(sym, sym)}"
    return f"{exchange}:{sym}"


async def get_market_quote_zerodha(user_id: str, symbol: str, exchange: str = "NSE") -> Optional[dict]:
    """
    Get real-time quote from Zerodha Kite Connect REST API.
    Returns None if unavailable (will fall back to yfinance).
    """
    session = await get_session(user_id)
    if not session:
        return None

    sym = symbol.upper()
    kite_sym = _get_kite_symbol(sym, exchange)

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            # Use OHLC endpoint for compact data
            resp = await c.get(
                f"{KITE_BASE}/quote/ohlc",
                params={"i": kite_sym},
                headers=_kite_headers(session["access_token"], session["api_key"]),
            )
            data = resp.json()
            if "data" in data and kite_sym in data["data"]:
                q = data["data"][kite_sym]
                ltp = float(q.get("last_price", 0) or 0)
                prev = float(q.get("ohlc", {}).get("close", ltp) or ltp)
                change = ltp - prev
                change_pct = (change / prev * 100) if prev else 0

                return {
                    "ltp": round(ltp, 2),
                    "open": round(float(q.get("ohlc", {}).get("open", ltp) or ltp), 2),
                    "high": round(float(q.get("ohlc", {}).get("high", ltp) or ltp), 2),
                    "low": round(float(q.get("ohlc", {}).get("low", ltp) or ltp), 2),
                    "prev_close": round(prev, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": int(q.get("volume", 0) or 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "zerodha",
                }

            logger.warning(f"Zerodha quote empty for {kite_sym}: {data}")
            return None
    except Exception as e:
        logger.warning(f"Zerodha quote failed for {sym}: {e}")
        return None


async def get_market_candles_zerodha(
    user_id: str, symbol: str, exchange: str,
    interval: str, from_date: str, to_date: str,
) -> Optional[list]:
    """
    Get historical candle data from Zerodha Kite Connect.
    Returns None if unavailable (will fall back to yfinance).
    """
    session = await get_session(user_id)
    if not session:
        return None

    sym = symbol.upper()
    token = NSE_INSTRUMENT_TOKENS.get(sym)
    if not token:
        logger.warning(f"No Zerodha instrument token for {sym}")
        return None

    # Map interval to Kite format
    kite_interval = interval  # Kite uses same format: minute, 5minute, 15minute, day, etc.
    if interval == "1m":
        kite_interval = "minute"
    elif interval == "5m":
        kite_interval = "5minute"
    elif interval == "15m":
        kite_interval = "15minute"
    elif interval == "30m":
        kite_interval = "30minute"
    elif interval == "1h":
        kite_interval = "60minute"
    elif interval == "1d":
        kite_interval = "day"
    elif interval == "1w":
        kite_interval = "week"

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{KITE_BASE}/instruments/historical/{token}/{kite_interval}",
                params={"from": from_date, "to": to_date},
                headers=_kite_headers(session["access_token"], session["api_key"]),
            )
            data = resp.json()
            if "data" in data and isinstance(data["data"], list):
                candles = []
                for entry in data["data"]:
                    # Format: [timestamp, open, high, low, close, volume, oi]
                    if isinstance(entry, list) and len(entry) >= 6:
                        t = entry[0]
                        if isinstance(t, str):
                            t = int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())
                        candles.append({
                            "time": int(t),
                            "open": round(float(entry[1]), 2),
                            "high": round(float(entry[2]), 2),
                            "low": round(float(entry[3]), 2),
                            "close": round(float(entry[4]), 2),
                            "volume": int(entry[5]),
                        })
                if candles:
                    return sorted(candles, key=lambda x: x["time"])
    except Exception as e:
        logger.warning(f"Zerodha candles failed for {sym}: {e}")

    return None


# ── WebSocket streaming via KiteTicker ─────────────────────

class ZerodhaTickerManager:
    """
    Manages a KiteTicker WebSocket connection in a background thread.
    Bridges tick events from the Twisted-based KiteTicker to asyncio callbacks.
    """

    def __init__(self, api_key: str, access_token: str, on_tick: Optional[Callable] = None):
        self.api_key = api_key
        self.access_token = access_token
        self.on_tick = on_tick
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._ticker = None
        self._tick_queue: queue.Queue = queue.Queue()
        self._subscribed_tokens: list = []
        self._last_ping: float = 0

    @property
    def is_connected(self) -> bool:
        return self._running and self._ticker is not None

    def connect(self):
        """Start the KiteTicker in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_ticker, daemon=True)
        self._thread.start()
        logger.info("Zerodha KiteTicker thread started")

    def disconnect(self):
        """Stop the KiteTicker."""
        self._running = False
        if self._ticker:
            try:
                self._ticker.close()
            except Exception:
                pass
            self._ticker = None
        logger.info("Zerodha KiteTicker stopped")

    def subscribe(self, tokens: list):
        """Subscribe to instrument tokens (numbers)."""
        self._subscribed_tokens.extend(tokens)
        if self._ticker:
            try:
                self._ticker.subscribe(tokens)
                self._ticker.set_mode(self._ticker.MODE_QUOTE, tokens)
            except Exception as e:
                logger.warning(f"KiteTicker subscribe failed: {e}")

    def _run_ticker(self):
        """Run KiteTicker in this thread (Twisted event loop)."""
        try:
            from kiteconnect import KiteTicker

            self._ticker = KiteTicker(self.api_key, self.access_token)

            def on_ticks(ws, ticks):
                """Callback for incoming ticks."""
                for tick in ticks:
                    self._tick_queue.put(tick)

            def on_connect(ws, response):
                logger.info("KiteTicker connected")
                if self._subscribed_tokens:
                    ws.subscribe(self._subscribed_tokens)
                    ws.set_mode(ws.MODE_QUOTE, self._subscribed_tokens)

            def on_close(ws, code, reason):
                logger.info(f"KiteTicker closed: {code} {reason}")
                if self._running:
                    # Auto-reconnect after 5s
                    time.sleep(5)
                    if self._running:
                        try:
                            ws.connect()
                        except Exception:
                            pass

            def on_error(ws, error):
                logger.warning(f"KiteTicker error: {error}")

            self._ticker.on_ticks = on_ticks
            self._ticker.on_connect = on_connect
            self._ticker.on_close = on_close
            self._ticker.on_error = on_error
            self._ticker.connect()

        except Exception as e:
            logger.error(f"KiteTicker thread error: {e}")
        finally:
            self._running = False

    def get_pending_ticks(self) -> list:
        """Get all pending ticks from the queue."""
        ticks = []
        while not self._tick_queue.empty():
            try:
                ticks.append(self._tick_queue.get_nowait())
            except queue.Empty:
                break
        return ticks


# Global ticker instances keyed by user_id
_ticker_managers: dict[str, ZerodhaTickerManager] = {}


def get_ticker_manager(user_id: str) -> Optional[ZerodhaTickerManager]:
    """Get the active Zerodha KiteTicker manager for a user."""
    return _ticker_managers.get(user_id)


async def start_ticker(user_id: str, api_key: str, access_token: str) -> Optional[ZerodhaTickerManager]:
    """Start a KiteTicker for a user."""
    if user_id in _ticker_managers and _ticker_managers[user_id].is_connected:
        return _ticker_managers[user_id]

    manager = ZerodhaTickerManager(api_key, access_token)
    manager.connect()
    _ticker_managers[user_id] = manager
    return manager


def stop_ticker(user_id: str):
    """Stop a KiteTicker for a user."""
    manager = _ticker_managers.pop(user_id, None)
    if manager:
        manager.disconnect()

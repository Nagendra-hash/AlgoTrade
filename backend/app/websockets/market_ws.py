"""
Market data WebSocket — pushes live price updates to browser.
Supports two data sources:
  - Angel One SmartAPI WebSocket V2 (real-time) when broker is connected
  - yfinance (delayed) as fallback when no broker available
Path: backend/app/websockets/market_ws.py
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Set

import yfinance as yf
from fastapi import WebSocket, WebSocketDisconnect

from app.services.angel_ws import (
    get_or_create_angel_ws,
    get_angel_ws_manager,
    disconnect_angel_ws,
    QUOTE_MODE,
    NSE_CM,
)
from app.services.angel_one import get_session as get_angel_session, get_symbol_token
from app.services.zerodha import (
    get_session as get_zerodha_session,
    get_ticker_manager as get_zerodha_ticker,
    start_ticker as start_zerodha_ticker,
    NSE_INSTRUMENT_TOKENS as ZERODHA_TOKENS,
)

logger = logging.getLogger(__name__)

NSE_TO_YF = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "WIPRO": "WIPRO.NS", "BAJFINANCE": "BAJFINANCE.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
}


class MarketWSManager:
    def __init__(self):
        self._connections: Dict[WebSocket, Set[str]] = {}
        self._user_ids: Dict[WebSocket, Optional[str]] = {}
        self._task: asyncio.Task = None

        # Angel One WS state
        self._angel_ws_user_id: Optional[str] = None
        self._angel_initialized = False
        self._subscribed_tokens: Set[str] = set()
        self._token_to_symbol: Dict[str, str] = {}

        # Zerodha WS state
        self._zerodha_initialized = False
        self._zerodha_user_id: Optional[str] = None

        # Tick cache (symbol -> tick data) for broadcasting
        self._tick_cache: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        await websocket.accept()
        self._connections[websocket] = set()
        self._user_ids[websocket] = user_id

        # Try to initialize broker WebSocket for real-time streaming
        if user_id:
            if not self._angel_initialized:
                await self._init_angel_ws()
            if not self._zerodha_initialized:
                await self._init_zerodha()

        if len(self._connections) == 1:
            self._task = asyncio.create_task(self._yfinance_poll_loop())

        payload = {"type": "connected"}
        if user_id:
            payload["user_id"] = user_id
        await websocket.send_text(json.dumps(payload))

    def disconnect(self, websocket: WebSocket):
        self._connections.pop(websocket, None)
        self._user_ids.pop(websocket, None)
        if not self._connections and self._task:
            self._task.cancel()
            self._task = None

        # If no more users, disconnect broker WS after a delay
        if not self._connections:
            if self._angel_initialized:
                asyncio.create_task(self._shutdown_angel_ws())
            if self._zerodha_initialized:
                asyncio.create_task(self._shutdown_zerodha())

    def subscribe(self, websocket: WebSocket, symbols: list):
        if websocket in self._connections:
            self._connections[websocket].update(s.upper() for s in symbols)

            # Subscribe to broker WebSockets
            asyncio.create_task(self._subscribe_to_angel(symbols))
            asyncio.create_task(self._subscribe_to_zerodha(symbols))

    async def _init_zerodha(self):
        """Initialize Zerodha KiteTicker streaming."""
        if self._zerodha_initialized:
            return

        for ws, uid in self._user_ids.items():
            if uid:
                session = await get_zerodha_session(uid)
                if session:
                    try:
                        await start_zerodha_ticker(
                            user_id=uid,
                            api_key=session["api_key"],
                            access_token=session["access_token"],
                        )
                        self._zerodha_user_id = uid
                        self._zerodha_initialized = True
                        logger.info(f"Zerodha KiteTicker initialized for user {uid[:8]}")
                        return
                    except Exception as e:
                        logger.warning(f"Zerodha ticker init failed: {e}")

    async def _init_angel_ws(self):
        """Initialize the Angel One WebSocket V2 connection using the first available broker session."""
        if self._angel_initialized:
            return

        # Find first user with an active broker session
        for ws, uid in self._user_ids.items():
            if uid:
                session = await get_session(uid)
                if session:
                    try:
                        auth_token = session.get("jwt_token", "")
                        api_key = session.get("api_key", "")
                        client_code = session.get("client_id", "")
                        feed_token = session.get("feed_token", "")

                        if not all([auth_token, api_key, client_code, feed_token]):
                            logger.warning("Angel One WS: missing credentials in session")
                            continue

                        await get_or_create_angel_ws(
                            user_id=uid,
                            auth_token=auth_token,
                            api_key=api_key,
                            client_code=client_code,
                            feed_token=feed_token,
                            on_tick=self._on_angel_tick,
                        )
                        self._angel_ws_user_id = uid
                        self._angel_initialized = True
                        logger.info(f"Angel One WS initialized for user {uid[:8]}")
                        return
                    except Exception as e:
                        logger.warning(f"Angel One WS init failed: {e}")

    async def _subscribe_to_angel(self, symbols: list):
        """Subscribe to symbols on Angel One WebSocket."""
        if not self._angel_initialized:
            return

        manager = None
        if self._angel_ws_user_id:
            manager = get_angel_ws_manager(self._angel_ws_user_id)

        if not manager or not manager.is_connected:
            return

        # Collect tokens to subscribe
        new_tokens = []
        for symbol in symbols:
            sym = symbol.upper()
            if sym in self._subscribed_tokens:
                continue  # Already subscribed
            token = await get_symbol_token(sym, "NSE")
            if token:
                self._subscribed_tokens.add(sym)
                self._token_to_symbol[token] = sym
                new_tokens.append({"exchangeType": NSE_CM, "tokens": [token]})

        if new_tokens:
            try:
                await manager.subscribe(
                    correlation_id=f"ws-{datetime.now().timestamp()}",
                    mode=QUOTE_MODE,  # Full quote data
                    token_list=new_tokens,
                )
                logger.info(f"Subscribed {len(new_tokens)} token groups to Angel One WS")
            except Exception as e:
                logger.warning(f"Angel One WS subscribe failed: {e}")

    def _on_angel_tick(self, tick: dict):
        """Callback when a tick arrives from Angel One WebSocket V2."""
        try:
            token = tick.get("token", "")
            symbol = self._token_to_symbol.get(token)
            if not symbol:
                return

            browser_tick = {
                "ltp": tick.get("last_traded_price", 0),
                "change": tick.get("last_traded_price", 0) - tick.get("closed_price", 0),
                "change_pct": 0,
                "open": tick.get("open_price_of_the_day", 0),
                "high": tick.get("high_price_of_the_day", 0),
                "low": tick.get("low_price_of_the_day", 0),
                "volume": tick.get("volume_trade_for_the_day", 0),
                "timestamp": datetime.now().isoformat(),
                "source": "angel_one",
            }

            # Calculate change percentage
            prev_close = tick.get("closed_price", 0)
            ltp = browser_tick["ltp"]
            if prev_close and prev_close > 0:
                browser_tick["change"] = round(ltp - prev_close, 2)
                browser_tick["change_pct"] = round((ltp - prev_close) / prev_close * 100, 2)

            # Cache the tick
            self._tick_cache[symbol] = browser_tick

            # Broadcast to all connected clients watching this symbol
            payload = json.dumps({"type": "quote", "data": {"symbol": symbol, **browser_tick}})
            dead = set()
            for ws, syms in self._connections.items():
                if symbol in syms:
                    try:
                        # Fire-and-forget send via asyncio
                        asyncio.ensure_future(self._safe_send(ws, payload))
                    except Exception:
                        dead.add(ws)
            for ws in dead:
                self._connections.pop(ws, None)
                self._user_ids.pop(ws, None)

        except Exception as e:
            logger.warning(f"Angel One tick handler error: {e}")

    async def _safe_send(self, ws: WebSocket, payload: str):
        """Safely send a message to a WebSocket client."""
        try:
            await ws.send_text(payload)
        except Exception:
            pass

    async def _shutdown_zerodha(self):
        """Shutdown Zerodha ticker after a delay."""
        await asyncio.sleep(30)
        if not self._connections and self._zerodha_user_id:
            from app.services.zerodha import stop_ticker as stop_zerodha_ticker
            stop_zerodha_ticker(self._zerodha_user_id)
            self._zerodha_initialized = False
            self._zerodha_user_id = None
            logger.info("Zerodha ticker shut down (no clients)")

    async def _subscribe_to_zerodha(self, symbols: list):
        """Subscribe to symbols on Zerodha KiteTicker."""
        if not self._zerodha_initialized or not self._zerodha_user_id:
            return

        manager = get_zerodha_ticker(self._zerodha_user_id)
        if not manager or not manager.is_connected:
            return

        # Collect instrument tokens to subscribe
        tokens = []
        for symbol in symbols:
            sym = symbol.upper()
            token = ZERODHA_TOKENS.get(sym)
            if token and sym not in self._subscribed_tokens:
                tokens.append(token)
                self._subscribed_tokens.add(sym)

        if tokens:
            manager.subscribe(tokens)
            logger.info(f"Subscribed {len(tokens)} symbols to Zerodha KiteTicker")

    async def _shutdown_angel_ws(self):
        """Shutdown Angel One WS after a delay when no clients are connected."""
        await asyncio.sleep(30)  # Keep alive for 30s in case of reconnect
        if not self._connections and self._angel_ws_user_id:
            await disconnect_angel_ws(self._angel_ws_user_id)
            self._angel_initialized = False
            self._angel_ws_user_id = None
            self._subscribed_tokens.clear()
            self._token_to_symbol.clear()
            logger.info("Angel One WS shut down (no clients)")

    # ── YFinance fallback poll loop ───────────────────────────

    async def _yfinance_poll_loop(self):
        """
        Main poll loop:
        1. Drain Zerodha KiteTicker ticks (real-time from broker)
        2. Fall back to yfinance for symbols not covered by brokers
        """
        while self._connections:
            try:
                # 1. Poll Zerodha ticker for real-time ticks
                if self._zerodha_initialized and self._zerodha_user_id:
                    manager = get_zerodha_ticker(self._zerodha_user_id)
                    if manager:
                        zerodha_ticks = manager.get_pending_ticks()
                        for tick in zerodha_ticks:
                            self._broadcast_zerodha_tick(tick)

                # 2. Poll yfinance for symbols not covered by any broker
                all_symbols: Set[str] = set()
                for syms in self._connections.values():
                    all_symbols.update(syms)

                for symbol in all_symbols:
                    try:
                        # Skip if any broker is covering this symbol
                        if self._angel_initialized and symbol in self._subscribed_tokens:
                            continue
                        if self._zerodha_initialized and symbol in self._subscribed_tokens:
                            continue
                        if symbol in self._tick_cache:
                            continue

                        # Fallback to yfinance
                        price = await self._fetch_yfinance_price(symbol)
                        if price:
                            price["source"] = "yfinance"
                            self._tick_cache[symbol] = price
                            payload = json.dumps({"type": "quote", "data": {"symbol": symbol, **price}})
                            dead = set()
                            for ws, syms in self._connections.items():
                                if symbol in syms:
                                    try:
                                        await ws.send_text(payload)
                                    except Exception:
                                        dead.add(ws)
                            for ws in dead:
                                self._connections.pop(ws, None)
                                self._user_ids.pop(ws, None)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Market stream error: {e}")
            await asyncio.sleep(2)

    def _broadcast_zerodha_tick(self, tick: dict):
        """Convert a raw Zerodha tick to browser format and broadcast."""
        try:
            instrument_token = tick.get("instrument_token", 0)
            # Find symbol from token
            symbol = None
            for sym, tok in ZERODHA_TOKENS.items():
                if tok == instrument_token:
                    symbol = sym
                    break
            if not symbol:
                return

            ltp = float(tick.get("last_price", 0) or 0)
            if ltp <= 0:
                return

            browser_tick = {
                "ltp": round(ltp, 2),
                "change": round(ltp - float(tick.get("ohlc", {}).get("close", ltp) or ltp), 2),
                "change_pct": 0,
                "open": round(float(tick.get("ohlc", {}).get("open", ltp) or ltp), 2),
                "high": round(float(tick.get("ohlc", {}).get("high", ltp) or ltp), 2),
                "low": round(float(tick.get("ohlc", {}).get("low", ltp) or ltp), 2),
                "volume": int(tick.get("volume", 0) or 0),
                "timestamp": datetime.now().isoformat(),
                "source": "zerodha",
            }

            # Calculate change percentage
            prev_close = float(tick.get("ohlc", {}).get("close", ltp) or ltp)
            if prev_close > 0:
                browser_tick["change"] = round(ltp - prev_close, 2)
                browser_tick["change_pct"] = round((ltp - prev_close) / prev_close * 100, 2)

            self._tick_cache[symbol] = browser_tick

            payload = json.dumps({"type": "quote", "data": {"symbol": symbol, **browser_tick}})
            dead = set()
            for ws, syms in self._connections.items():
                if symbol in syms:
                    try:
                        asyncio.ensure_future(self._safe_send(ws, payload))
                    except Exception:
                        dead.add(ws)
            for ws in dead:
                self._connections.pop(ws, None)
                self._user_ids.pop(ws, None)

        except Exception as e:
            logger.warning(f"Zerodha tick broadcast error: {e}")

    async def _fetch_yfinance_price(self, symbol: str) -> dict:
        """Fetch price from yfinance (delayed)."""
        yf_sym = NSE_TO_YF.get(symbol, symbol + ".NS")
        loop = asyncio.get_event_loop()
        try:
            price = await loop.run_in_executor(None, self._fetch_yf_price_sync, yf_sym)
            return price or {}
        except Exception:
            return {}

    @staticmethod
    def _fetch_yf_price_sync(yf_sym: str) -> dict:
        try:
            t = yf.Ticker(yf_sym)
            i = t.fast_info
            ltp = float(getattr(i, "last_price", 0) or 0)
            prev = float(getattr(i, "previous_close", ltp) or ltp)
            chg = ((ltp - prev) / prev * 100) if prev else 0
            return {
                "ltp": round(ltp, 2),
                "change_pct": round(chg, 2),
                "change": round(ltp - prev, 2),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception:
            return {}


market_manager = MarketWSManager()


async def market_ws_endpoint(websocket: WebSocket, user_id: Optional[str] = None):
    await market_manager.connect(websocket, user_id)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("action") == "subscribe":
                    market_manager.subscribe(websocket, msg.get("symbols", []))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        market_manager.disconnect(websocket)
    except Exception:
        market_manager.disconnect(websocket)

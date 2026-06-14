"""
Angel One SmartAPI WebSocket V2 — async binary protocol decoder.
Connects to wss://smartapisocket.angelone.in/smart-stream for real-time ticks.
Path: backend/app/services/angel_ws.py

This implements the binary protobuf protocol directly using Python's `struct`
module, matching the official smartapi-python SmartWebSocketV2 exactly.
"""
import asyncio
import json
import logging
import struct
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ROOT_URI = "wss://smartapisocket.angelone.in/smart-stream"

# Exchange types
NSE_CM = 1
NSE_FO = 2
BSE_CM = 3
BSE_FO = 4
MCX_FO = 5
NCX_FO = 7
CDE_FO = 13

# Subscription modes
LTP_MODE = 1
QUOTE_MODE = 2
SNAP_QUOTE_MODE = 3
DEPTH_MODE = 4

# Exchange type constants for Angel One SmartAPI
# Maps our exchange string to Angel One exchange type
EXCHANGE_MAP = {
    "NSE": NSE_CM,
    "NFO": NSE_FO,
    "BSE": BSE_CM,
    "MCX": MCX_FO,
}


class AngelOneWSManager:
    """
    Async WebSocket V2 client for Angel One SmartAPI.
    Connects to the smart-stream endpoint and decodes binary protobuf ticks.

    Usage:
        manager = AngelOneWSManager(auth_token, api_key, client_code, feed_token)
        await manager.connect()
        await manager.subscribe("corr123", QUOTE_MODE, [{"exchangeType": 1, "tokens": ["2885"]}])
        # ... ticks arrive via on_tick callback
        await manager.disconnect()
    """

    def __init__(
        self,
        auth_token: str,
        api_key: str,
        client_code: str,
        feed_token: str,
        on_tick: Optional[Callable] = None,
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.auth_token = auth_token
        self.api_key = api_key
        self.client_code = client_code
        self.feed_token = feed_token
        self.on_tick = on_tick
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_error = on_error

        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._connected = False
        self._subscribed_tokens: dict = {}  # mode -> {exchangeType: [tokens]}
        self._last_pong = datetime.now(timezone.utc)

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self):
        """Connect to Angel One smart-stream WebSocket."""
        import websockets

        headers = {
            "Authorization": self.auth_token,
            "x-api-key": self.api_key,
            "x-client-code": self.client_code,
            "x-feed-token": self.feed_token,
        }

        try:
            self._ws = await websockets.connect(
                ROOT_URI,
                extra_headers=headers,
                ping_interval=10,
                ping_timeout=5,
                max_size=2**20,  # 1MB max message
            )
            self._connected = True
            logger.info("Angel One SmartWebSocket V2 connected")

            if self.on_connect:
                self.on_connect()

            # Start message reader task
            self._task = asyncio.create_task(self._reader_loop())
        except Exception as e:
            logger.error(f"Angel One WS connection failed: {e}")
            self._connected = False
            if self.on_error:
                self.on_error(str(e))
            raise

    async def disconnect(self):
        """Disconnect from Angel One WebSocket."""
        self._connected = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        logger.info("Angel One SmartWebSocket V2 disconnected")
        if self.on_disconnect:
            self.on_disconnect()

    async def subscribe(self, correlation_id: str, mode: int, token_list: list):
        """
        Subscribe to tokens for real-time data.

        Args:
            correlation_id: Client tracking ID (string)
            mode: 1=LTP, 2=Quote, 3=Snap Quote
            token_list: [{"exchangeType": 1, "tokens": ["2885", "11536"]}]
        """
        if not self._connected or not self._ws:
            logger.warning("Cannot subscribe: not connected")
            return

        request = {
            "correlationID": correlation_id,
            "action": 1,  # SUBSCRIBE
            "params": {
                "mode": mode,
                "tokenList": token_list,
            },
        }

        # Track subscribed tokens for reconnection
        if mode not in self._subscribed_tokens:
            self._subscribed_tokens[mode] = {}
        for entry in token_list:
            et = entry["exchangeType"]
            if et not in self._subscribed_tokens[mode]:
                self._subscribed_tokens[mode][et] = []
            self._subscribed_tokens[mode][et].extend(entry["tokens"])

        await self._ws.send(json.dumps(request))
        logger.info(f"Subscribed (mode={mode}): {len(token_list)} exchange groups")

    async def unsubscribe(self, correlation_id: str, mode: int, token_list: list):
        """Unsubscribe from tokens."""
        if not self._connected or not self._ws:
            return

        request = {
            "correlationID": correlation_id,
            "action": 0,  # UNSUBSCRIBE
            "params": {
                "mode": mode,
                "tokenList": token_list,
            },
        }
        await self._ws.send(json.dumps(request))

        # Remove from tracked tokens
        if mode in self._subscribed_tokens:
            for entry in token_list:
                et = entry["exchangeType"]
                if et in self._subscribed_tokens[mode]:
                    for t in entry["tokens"]:
                        if t in self._subscribed_tokens[mode][et]:
                            self._subscribed_tokens[mode][et].remove(t)

    async def _reader_loop(self):
        """Read and decode binary messages from the WebSocket."""
        try:
            async for message in self._ws:
                if isinstance(message, str):
                    # Control message (ping/pong)
                    if message == "pong":
                        self._last_pong = datetime.now(timezone.utc)
                        logger.debug("Received pong from Angel One WS")
                    else:
                        logger.debug(f"Angel One WS text message: {message[:100]}")
                elif isinstance(message, bytes):
                    # Binary data — decode protobuf tick
                    try:
                        tick = self._decode_tick(message)
                        if tick and self.on_tick:
                            self.on_tick(tick)
                    except Exception as e:
                        logger.warning(f"Failed to decode Angel One tick: {e}")
                else:
                    logger.debug(f"Angel One WS unknown message type: {type(message)}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Angel One WS reader error: {e}")
            self._connected = False
            if self.on_error:
                self.on_error(str(e))
            # Auto-reconnect after 5 seconds
            await asyncio.sleep(5)
            if not self._connected:
                try:
                    await self.connect()
                    await self._resubscribe_all()
                except Exception as reconnect_error:
                    logger.error(f"Angel One WS reconnection failed: {reconnect_error}")

    async def _resubscribe_all(self):
        """Resubscribe to all previously subscribed tokens after reconnect."""
        for mode, exchanges in self._subscribed_tokens.items():
            token_list = []
            for exchange_type, tokens in exchanges.items():
                if tokens:
                    token_list.append({"exchangeType": exchange_type, "tokens": tokens})
            if token_list:
                await self.subscribe(f"reconnect-{mode}", mode, token_list)

    def _decode_tick(self, data: bytes) -> Optional[dict]:
        """
        Decode binary protobuf tick data matching Angel One's V2 protocol.
        Uses little-endian byte order.
        """
        if len(data) < 51:
            return None

        try:
            subscription_mode = struct.unpack_from("<B", data, 0)[0]
            exchange_type = struct.unpack_from("<B", data, 1)[0]
            token = self._parse_token(data[2:27])
            sequence_number = struct.unpack_from("<q", data, 27)[0]
            exchange_timestamp = struct.unpack_from("<q", data, 35)[0]
            last_traded_price = struct.unpack_from("<q", data, 43)[0]

            tick = {
                "subscription_mode": subscription_mode,
                "exchange_type": exchange_type,
                "token": token,
                "sequence_number": sequence_number,
                "exchange_timestamp": exchange_timestamp,
                "last_traded_price": last_traded_price / 100,  # Convert paise to rupees
            }

            # Parse additional fields for Quote/SnapQuote mode
            if subscription_mode in (QUOTE_MODE, SNAP_QUOTE_MODE) and len(data) >= 123:
                tick["last_traded_quantity"] = struct.unpack_from("<q", data, 51)[0]
                tick["average_traded_price"] = struct.unpack_from("<q", data, 59)[0] / 100
                tick["volume_trade_for_the_day"] = struct.unpack_from("<q", data, 67)[0]
                tick["total_buy_quantity"] = struct.unpack_from("<d", data, 75)[0]
                tick["total_sell_quantity"] = struct.unpack_from("<d", data, 83)[0]
                tick["open_price_of_the_day"] = struct.unpack_from("<q", data, 91)[0] / 100
                tick["high_price_of_the_day"] = struct.unpack_from("<q", data, 99)[0] / 100
                tick["low_price_of_the_day"] = struct.unpack_from("<q", data, 107)[0] / 100
                tick["closed_price"] = struct.unpack_from("<q", data, 115)[0] / 100

            # Parse SnapQuote fields
            if subscription_mode == SNAP_QUOTE_MODE and len(data) >= 379:
                tick["last_traded_timestamp"] = struct.unpack_from("<q", data, 123)[0]
                tick["open_interest"] = struct.unpack_from("<q", data, 131)[0]
                tick["open_interest_change_percentage"] = struct.unpack_from("<q", data, 139)[0] / 100
                if len(data) >= 379:
                    tick["upper_circuit_limit"] = struct.unpack_from("<q", data, 347)[0] / 100
                    tick["lower_circuit_limit"] = struct.unpack_from("<q", data, 355)[0] / 100
                    tick["52_week_high_price"] = struct.unpack_from("<q", data, 363)[0] / 100
                    tick["52_week_low_price"] = struct.unpack_from("<q", data, 371)[0] / 100

            return tick

        except struct.error as e:
            logger.warning(f"struct decode error: {e}")
            return None
        except Exception as e:
            logger.warning(f"Tick decode error: {e}")
            return None

    @staticmethod
    def _parse_token(binary_packet: bytes) -> str:
        """Extract null-terminated token string from binary packet."""
        token = ""
        for byte in binary_packet:
            if byte == 0:
                break
            token += chr(byte)
        return token

    def build_tick_for_browser(self, tick: dict) -> Optional[dict]:
        """
        Convert an Angel One tick dict into the format expected by our browser clients.
        Returns None if the tick doesn't have meaningful LTP data.
        """
        ltp = tick.get("last_traded_price", 0)
        if not ltp or ltp <= 0:
            return None

        open_price = tick.get("open_price_of_the_day", ltp) or ltp
        high_price = tick.get("high_price_of_the_day", ltp) or ltp
        low_price = tick.get("low_price_of_the_day", ltp) or ltp
        close_price = tick.get("closed_price", ltp) or ltp
        prev_close = close_price  # closed_price from previous day

        change = ltp - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "ltp": round(ltp, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(prev_close, 2),
            "volume": int(tick.get("volume_trade_for_the_day", 0)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "angel_one",
            "token": tick.get("token", ""),
        }


# ── Global singleton instances keyed by user_id ──────────────

_ws_managers: dict[str, AngelOneWSManager] = {}


def get_angel_ws_manager(user_id: str) -> Optional[AngelOneWSManager]:
    """Get the active Angel One WS manager for a user, if any."""
    return _ws_managers.get(user_id)


async def get_or_create_angel_ws(
    user_id: str,
    auth_token: str,
    api_key: str,
    client_code: str,
    feed_token: str,
    on_tick: Optional[Callable] = None,
) -> AngelOneWSManager:
    """
    Get or create an Angel One WebSocket V2 connection for a user.
    If a connection already exists for this user_id, return it.
    """
    if user_id in _ws_managers and _ws_managers[user_id].is_connected:
        return _ws_managers[user_id]

    manager = AngelOneWSManager(
        auth_token=auth_token,
        api_key=api_key,
        client_code=client_code,
        feed_token=feed_token,
        on_tick=on_tick,
    )
    try:
        await manager.connect()
        _ws_managers[user_id] = manager
    except Exception as e:
        logger.error(f"Failed to create Angel One WS for user {user_id[:8]}: {e}")
        raise
    return manager


async def disconnect_angel_ws(user_id: str):
    """Disconnect and remove an Angel One WS connection for a user."""
    manager = _ws_managers.pop(user_id, None)
    if manager:
        await manager.disconnect()


async def disconnect_all_angel_ws():
    """Disconnect all Angel One WS connections (called on shutdown)."""
    for user_id, manager in list(_ws_managers.items()):
        await manager.disconnect()
    _ws_managers.clear()

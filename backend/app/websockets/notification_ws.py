"""
WebSocket notification manager — limits 3 connections per user.
Path: backend/app/websockets/notification_ws.py
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER = 3


class NotificationManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()

        if user_id not in self._connections:
            self._connections[user_id] = set()

        # Close oldest connections if over limit
        existing = list(self._connections[user_id])
        if len(existing) >= MAX_CONNECTIONS_PER_USER:
            for old_ws in existing[: len(existing) - MAX_CONNECTIONS_PER_USER + 1]:
                try:
                    await old_ws.close(code=1000)
                except Exception:
                    pass
                self._connections[user_id].discard(old_ws)

        self._connections[user_id].add(websocket)
        total = self.total_connections
        logger.info(f"WS connected: user={user_id[:8]} total={total}")

        try:
            await websocket.send_text(json.dumps({
                "type":      "connected",
                "message":   "Notification stream active",
                "timestamp": datetime.now().isoformat(),
            }))
        except Exception:
            pass

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WS disconnected: user={user_id[:8]} total={self.total_connections}")

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        sockets = list(self._connections.get(user_id, set()))
        dead = []
        for ws in sockets:
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.get(user_id, set()).discard(ws)

    @property
    def total_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


notification_manager = NotificationManager()


async def notification_ws_endpoint(websocket: WebSocket, user_id: str) -> None:
    await notification_manager.connect(websocket, user_id)
    try:
        while True:
            try:
                # Add timeout so dead connections are detected quickly
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                try:
                    msg = json.loads(raw)
                    if msg.get("action") == "ping":
                        await websocket.send_text(json.dumps({
                            "type":      "pong",
                            "timestamp": datetime.now().isoformat(),
                        }))
                except (json.JSONDecodeError, Exception):
                    pass
            except asyncio.TimeoutError:
                # Send ping to check if client is alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Silently handle disconnect errors — these are normal
        if "IncompleteReadError" not in str(type(e).__name__):
            logger.debug(f"WS closed: user={user_id[:8]} reason={type(e).__name__}")
    finally:
        notification_manager.disconnect(websocket, user_id)

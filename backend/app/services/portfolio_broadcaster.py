"""
Portfolio data broadcaster — pushes periodic "refresh" signals over notification WebSocket.
Lives alongside the AlertEngine so the Risk Manager page gets live updates without polling.
Path: backend/app/services/portfolio_broadcaster.py
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.websockets.notification_ws import notification_manager

logger = logging.getLogger(__name__)


class PortfolioBroadcaster:
    """Periodically pushes portfolio_update signals to all connected users."""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._interval = 5  # seconds between broadcast cycles

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Portfolio broadcaster started (interval={self._interval}s)")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Portfolio broadcaster stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._broadcast_cycle()
            except Exception as e:
                logger.error(f"Portfolio broadcast error: {e}")
            await asyncio.sleep(self._interval)

    async def _broadcast_cycle(self) -> None:
        """Push a portfolio_update signal to every user who has an active WebSocket."""
        # Access the internal connections dict to find active users
        active_users = list(notification_manager._connections.keys())
        if not active_users:
            return

        now = datetime.now(timezone.utc).isoformat()
        for user_id in active_users:
            try:
                payload = {
                    "type": "portfolio_update",
                    "data": {
                        "timestamp": now,
                    },
                }
                await notification_manager.send_to_user(user_id, payload)
            except Exception as e:
                logger.debug(f"Portfolio broadcast to user {user_id[:8]}: {e}")


portfolio_broadcaster = PortfolioBroadcaster()

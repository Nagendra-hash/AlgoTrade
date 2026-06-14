"""
Paper Trade Tracker — persists paper trade history and computes cumulative P&L.

Every paper trade executed by the auto-trade engine is recorded here.
On server restart, historical data is loaded from the database, so
cumulative P&L, win rate, equity curve, and performance analytics survive restarts.

Path: backend/app/services/paper_trade_tracker.py
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.paper_trade import PaperTrade, PaperDailySnapshot

logger = logging.getLogger(__name__)


class PaperTradeTracker:
    """
    Records paper trades and maintains cumulative performance stats.

    All methods are async and use the database. This ensures data
    survives server restarts and provides a single source of truth.
    """

    def __init__(self):
        self._cached_stats: Optional[dict] = None
        self._cache_time: Optional[datetime] = None

    # ── Record a paper trade ────────────────────────────────────

    async def record_buy(
        self, user_id: str, symbol: str, exchange: str,
        quantity: int, price: float, stop_loss: float,
        take_profit: float, strategy_id: str = "",
        strategy_name: str = "",
    ) -> str:
        """Record a paper BUY trade. Returns the trade ID."""
        try:
            async with AsyncSessionLocal() as db:
                trade = PaperTrade(
                    user_id=user_id,
                    strategy_id=strategy_id or None,
                    strategy_name=strategy_name,
                    symbol=symbol,
                    exchange=exchange,
                    side="BUY",
                    quantity=quantity,
                    entry_price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    status="OPEN",
                    entry_time=datetime.now(timezone.utc),
                )
                db.add(trade)
                await db.commit()
                trade_id = str(trade.id)
                logger.debug(f"Paper BUY recorded: {trade_id} — {quantity} {symbol} @ ₹{price:,.2f}")
                return trade_id
        except Exception as e:
            logger.error(f"Failed to record paper BUY: {e}")
            return ""

    async def record_sell(
        self, user_id: str, trade_id: str, price: float,
        reason: str = "Signal",
    ) -> Optional[dict]:
        """
        Record a paper SELL (close) for an existing BUY trade.
        Returns the trade details with P&L, or None on failure.
        """
        try:
            async with AsyncSessionLocal() as db:
                # Find the open trade
                if trade_id:
                    r = await db.execute(
                        select(PaperTrade).where(PaperTrade.id == trade_id)
                    )
                else:
                    # Fallback: find most recent OPEN BUY for this user+symbol
                    r = await db.execute(
                        select(PaperTrade).where(
                            PaperTrade.user_id == user_id,
                            PaperTrade.side == "BUY",
                            PaperTrade.status == "OPEN",
                        ).order_by(PaperTrade.created_at.desc()).limit(1)
                    )
                trade = r.scalar_one_or_none()
                if not trade:
                    logger.warning(f"No open paper trade found for sell")
                    return None

                # Calculate P&L
                pnl = (price - trade.entry_price) * trade.quantity
                pnl_pct = ((price - trade.entry_price) / trade.entry_price * 100) if trade.entry_price else 0

                # Determine status
                status = "CLOSED"
                if "Stop Loss" in reason:
                    status = "STOPPED"
                elif "Take Profit" in reason:
                    status = "TAKE_PROFIT"

                # Update trade
                trade.exit_price = price
                trade.pnl = round(pnl, 2)
                trade.pnl_pct = round(pnl_pct, 2)
                trade.status = status
                trade.close_reason = reason
                trade.exit_time = datetime.now(timezone.utc)

                await db.commit()

                result = {
                    "trade_id": str(trade.id),
                    "symbol": trade.symbol,
                    "quantity": trade.quantity,
                    "entry_price": trade.entry_price,
                    "exit_price": price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "status": status,
                    "reason": reason,
                    "entry_time": trade.entry_time.isoformat() if trade.entry_time else "",
                    "exit_time": datetime.now(timezone.utc).isoformat(),
                }
                logger.debug(f"Paper SELL recorded: {trade.symbol} P&L ₹{pnl:,.2f}")
                return result
        except Exception as e:
            logger.error(f"Failed to record paper SELL: {e}")
            return None

    # ── Cumulative stats ────────────────────────────────────────

    async def get_cumulative_stats(self, user_id: str) -> dict:
        """Get cumulative performance stats for a user."""
        # Check cache (refresh every 60s)
        now = datetime.now(timezone.utc)
        if (self._cached_stats and self._cache_time
                and (now - self._cache_time).seconds < 60):
            return self._cached_stats

        try:
            async with AsyncSessionLocal() as db:
                # Total trades
                r = await db.execute(
                    select(func.count(PaperTrade.id)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.status.in_(["CLOSED", "STOPPED", "TAKE_PROFIT"]),
                    )
                )
                total_trades = r.scalar() or 0

                # Wins and losses
                r = await db.execute(
                    select(func.count(PaperTrade.id)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.pnl > 0,
                        PaperTrade.status.in_(["CLOSED", "STOPPED", "TAKE_PROFIT"]),
                    )
                )
                wins = r.scalar() or 0

                # Total P&L
                r = await db.execute(
                    select(func.coalesce(func.sum(PaperTrade.pnl), 0)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.pnl.isnot(None),
                    )
                )
                total_pnl = float(r.scalar() or 0)

                # Best and worst trade
                r = await db.execute(
                    select(func.max(PaperTrade.pnl)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.pnl.isnot(None),
                    )
                )
                best_trade = float(r.scalar() or 0)

                r = await db.execute(
                    select(func.min(PaperTrade.pnl)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.pnl.isnot(None),
                    )
                )
                worst_trade = float(r.scalar() or 0)

                # Profit factor
                r = await db.execute(
                    select(func.coalesce(func.sum(PaperTrade.pnl), 0)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.pnl > 0,
                    )
                )
                sum_wins = float(r.scalar() or 0)

                r = await db.execute(
                    select(func.coalesce(func.abs(func.sum(PaperTrade.pnl)), 0)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.pnl < 0,
                    )
                )
                sum_losses = float(r.scalar() or 0)
                profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 0 else (999.0 if sum_wins > 0 else 0)

                # Stop loss vs take profit counts
                r = await db.execute(
                    select(func.count(PaperTrade.id)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.close_reason.like("%Stop Loss%"),
                    )
                )
                stop_loss_count = r.scalar() or 0

                r = await db.execute(
                    select(func.count(PaperTrade.id)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.close_reason.like("%Take Profit%"),
                    )
                )
                take_profit_count = r.scalar() or 0

                # Win rate
                win_rate = round((wins / total_trades * 100) if total_trades > 0 else 0, 2)

                # Starting capital (from latest snapshot or default)
                starting_capital = 100000.0
                r = await db.execute(
                    select(PaperDailySnapshot).where(
                        PaperDailySnapshot.user_id == user_id,
                    ).order_by(PaperDailySnapshot.date.desc()).limit(1)
                )
                latest_snap = r.scalar_one_or_none()
                if latest_snap:
                    starting_capital = latest_snap.starting_capital

                stats = {
                    "total_trades": total_trades,
                    "wins": wins,
                    "losses": total_trades - wins,
                    "win_rate": win_rate,
                    "total_pnl": round(total_pnl, 2),
                    "total_return_pct": round((total_pnl / starting_capital * 100) if starting_capital else 0, 2),
                    "best_trade": round(best_trade, 2),
                    "worst_trade": round(worst_trade, 2),
                    "profit_factor": profit_factor,
                    "stop_loss_count": stop_loss_count,
                    "take_profit_count": take_profit_count,
                    "starting_capital": starting_capital,
                    "current_value": round(starting_capital + total_pnl, 2),
                }

                self._cached_stats = stats
                self._cache_time = now
                return stats
        except Exception as e:
            logger.error(f"Failed to get cumulative stats: {e}")
            return {"total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0}

    # ── Trade history ───────────────────────────────────────────

    async def get_trade_history(
        self, user_id: str, limit: int = 50, offset: int = 0,
        symbol: str = "", status: str = "",
    ) -> List[dict]:
        """Get paginated trade history for a user."""
        try:
            async with AsyncSessionLocal() as db:
                q = select(PaperTrade).where(PaperTrade.user_id == user_id)
                if symbol:
                    q = q.where(PaperTrade.symbol == symbol.upper())
                if status:
                    q = q.where(PaperTrade.status == status.upper())
                q = q.order_by(PaperTrade.created_at.desc()).limit(limit).offset(offset)

                r = await db.execute(q)
                trades = r.scalars().all()

                return [
                    {
                        "id": str(t.id),
                        "symbol": t.symbol,
                        "exchange": t.exchange,
                        "side": t.side,
                        "quantity": t.quantity,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "stop_loss": t.stop_loss,
                        "take_profit": t.take_profit,
                        "pnl": t.pnl,
                        "pnl_pct": t.pnl_pct,
                        "status": t.status,
                        "close_reason": t.close_reason,
                        "strategy_name": t.strategy_name,
                        "entry_time": t.entry_time.isoformat() if t.entry_time else "",
                        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                        "is_open": t.status == "OPEN",
                    }
                    for t in trades
                ]
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []

    # ── Equity curve ────────────────────────────────────────────

    async def get_equity_curve(self, user_id: str, days: int = 30) -> List[dict]:
        """Get equity curve data for charting."""
        try:
            async with AsyncSessionLocal() as db:
                since = datetime.now(timezone.utc) - timedelta(days=days)
                r = await db.execute(
                    select(PaperDailySnapshot).where(
                        PaperDailySnapshot.user_id == user_id,
                        PaperDailySnapshot.date >= since,
                    ).order_by(PaperDailySnapshot.date.asc())
                )
                snapshots = r.scalars().all()

                return [
                    {
                        "date": s.date.isoformat(),
                        "value": round(s.current_value, 2),
                        "pnl": round(s.cumulative_pnl, 2),
                        "daily_pnl": round(s.daily_pnl, 2),
                        "trades": s.daily_trades,
                        "win_rate": round(s.win_rate, 1),
                    }
                    for s in snapshots
                ]
        except Exception as e:
            logger.error(f"Failed to get equity curve: {e}")
            return []

    # ── Daily snapshot ──────────────────────────────────────────

    async def save_daily_snapshot(
        self, user_id: str, current_value: float, starting_capital: float = 100000,
        open_positions: Optional[list] = None,
    ) -> None:
        """Save or update today's daily snapshot."""
        try:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            async with AsyncSessionLocal() as db:
                # Check if today's snapshot exists
                r = await db.execute(
                    select(PaperDailySnapshot).where(
                        PaperDailySnapshot.user_id == user_id,
                        PaperDailySnapshot.date == today,
                    )
                )
                snap = r.scalar_one_or_none()

                # Get cumulative stats
                stats = await self.get_cumulative_stats(user_id)

                daily_pnl = current_value - starting_capital

                if snap:
                    # Update existing
                    snap.current_value = current_value
                    snap.cumulative_pnl = stats.get("total_pnl", 0)
                    snap.total_trades = stats.get("total_trades", 0)
                    snap.total_wins = stats.get("wins", 0)
                    snap.total_losses = stats.get("losses", 0)
                    snap.win_rate = stats.get("win_rate", 0)
                    snap.open_positions = open_positions
                else:
                    # Create new
                    snap = PaperDailySnapshot(
                        user_id=user_id,
                        date=today,
                        starting_capital=starting_capital,
                        current_value=current_value,
                        cash=current_value,
                        daily_pnl=daily_pnl,
                        cumulative_pnl=stats.get("total_pnl", 0),
                        total_trades=stats.get("total_trades", 0),
                        total_wins=stats.get("wins", 0),
                        total_losses=stats.get("losses", 0),
                        win_rate=stats.get("win_rate", 0),
                        open_positions=open_positions,
                    )
                    db.add(snap)

                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save daily snapshot: {e}")


# Singleton
paper_trade_tracker = PaperTradeTracker()

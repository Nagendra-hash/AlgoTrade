"""
Trading Opportunities API.
Path: backend/app/api/v1/opportunities.py
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.users import get_current_user
from app.models.user import User
from app.models.watchlist import WatchlistItem, UserOpportunityPref
from app.models.strategy import Strategy, StrategyStatus
from app.services.opportunity_engine import build_opportunities

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Feed ────────────────────────────────────────────────────────

@router.get("")
async def get_opportunities(
    limit: int = Query(25, ge=5, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feed = await build_opportunities(limit=limit, db=db)
    # Filter out symbols the user has marked Avoid
    r = await db.execute(
        select(UserOpportunityPref.symbol).where(
            UserOpportunityPref.user_id == current_user.id,
            UserOpportunityPref.action == "avoid",
        )
    )
    avoided = {row[0] for row in r.all()}
    if avoided:
        feed["items"] = [it for it in feed["items"] if it["symbol"] not in avoided]
        feed["avoided_count"] = len(avoided)
    else:
        feed["avoided_count"] = 0
    return feed


# ── Buy / Watch / Avoid actions ─────────────────────────────────

class OpportunityAction(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=40)
    exchange: str = Field("NSE", max_length=10)
    snapshot: Optional[dict] = None    # opportunity row at click-time
    notes: Optional[str] = None


@router.post("/{symbol}/watch", status_code=201)
async def opportunity_watch(
    symbol: str,
    body: OpportunityAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add to watchlist (track sentiment/news, no order)."""
    symbol = symbol.upper().strip()

    r = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.symbol == symbol,
            WatchlistItem.exchange == body.exchange,
        )
    )
    item = r.scalar_one_or_none()
    if item:
        if body.snapshot:
            item.snapshot = body.snapshot
        item.source = "watch"
        await db.flush()
        return {"action": "watch", "symbol": symbol, "added": False, "watchlist_id": str(item.id)}

    item = WatchlistItem(
        user_id=current_user.id,
        symbol=symbol,
        exchange=body.exchange,
        source="watch",
        notes=body.notes,
        snapshot=body.snapshot,
    )
    db.add(item)
    await db.flush()
    return {"action": "watch", "symbol": symbol, "added": True, "watchlist_id": str(item.id)}


@router.post("/{symbol}/avoid", status_code=201)
async def opportunity_avoid(
    symbol: str,
    body: OpportunityAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hide this symbol from the opportunity feed (Avoid preference)."""
    symbol = symbol.upper().strip()

    r = await db.execute(
        select(UserOpportunityPref).where(
            UserOpportunityPref.user_id == current_user.id,
            UserOpportunityPref.symbol == symbol,
            UserOpportunityPref.exchange == body.exchange,
            UserOpportunityPref.action == "avoid",
        )
    )
    if r.scalar_one_or_none():
        return {"action": "avoid", "symbol": symbol, "added": False}

    pref = UserOpportunityPref(
        user_id=current_user.id,
        symbol=symbol,
        exchange=body.exchange,
        action="avoid",
        reason=body.notes,
    )
    db.add(pref)
    await db.flush()
    return {"action": "avoid", "symbol": symbol, "added": True}


@router.delete("/{symbol}/avoid")
async def opportunity_unavoid(
    symbol: str,
    exchange: str = "NSE",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unhide an avoided symbol."""
    await db.execute(
        delete(UserOpportunityPref).where(
            UserOpportunityPref.user_id == current_user.id,
            UserOpportunityPref.symbol == symbol.upper().strip(),
            UserOpportunityPref.exchange == exchange,
            UserOpportunityPref.action == "avoid",
        )
    )
    await db.flush()
    return {"action": "unavoid", "symbol": symbol.upper()}


# ── Helpers for opportunity_buy (extracted to keep handler simple) ───────────

_RISK_TO_SL: dict[str, float] = {"low": 1.5, "moderate": 2.0, "elevated": 2.5, "high": 3.0}


def _risk_to_sl_tp(risk_level: str) -> tuple[float, float]:
    """Map snapshot risk_level → (stop-loss %, take-profit %) with 1:2 minimum risk-reward."""
    sl = _RISK_TO_SL.get(risk_level, 2.0)
    return sl, sl * 2


async def _upsert_buy_watchlist(db: AsyncSession, user_id, symbol: str, exchange: str, snapshot: dict) -> WatchlistItem:
    r = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol == symbol,
            WatchlistItem.exchange == exchange,
        )
    )
    wl = r.scalar_one_or_none()
    if wl:
        wl.source = "buy"
        if snapshot:
            wl.snapshot = snapshot
    else:
        wl = WatchlistItem(user_id=user_id, symbol=symbol, exchange=exchange, source="buy", snapshot=snapshot)
        db.add(wl)
    await db.flush()
    return wl


def _build_opp_strategy(user_id, symbol: str, exchange: str, snap: dict, sl_pct: float, tp_pct: float) -> Strategy:
    risk_level = snap.get("risk_level", "moderate")
    confidence = snap.get("confidence", 60)
    description = snap.get("ai_summary") or (
        f"Auto-generated from Trading Opportunities — confidence {confidence:.0f}/100, risk {risk_level}."
    )
    return Strategy(
        user_id=user_id,
        name=f"Opp · {symbol} ({snap.get('recommended_action', 'Buy')})",
        description=description,
        strategy_type="hybrid_trend_momentum",
        user_prompt=f"Bought from Trading Opportunities feed. AI says: {snap.get('ai_summary', 'High confidence setup')}",
        entry_logic="SMA fast/slow crossover with Momentum ROC > 1% confirmation",
        exit_logic=f"Stop-loss at -{sl_pct}% OR Take-profit at +{tp_pct}% OR Trailing stop 1.5%",
        risk_rules="Max position size: 10% of capital. Max drawdown: 10%.",
        indicators=["SMA(20)", "SMA(50)", "ROC(10)"],
        parameters={"fast_period": 20, "slow_period": 50, "roc_period": 10, "roc_threshold": 1.0},
        symbols=[symbol],
        timeframe="1d",
        exchange=exchange,
        tags=["opportunity-buy", risk_level],
        status=StrategyStatus.ACTIVE.value,
        is_paper_active=True,
        is_live_active=False,
        stop_loss_pct=sl_pct,
        take_profit_pct=tp_pct,
        trailing_stop_enabled=True,
        trailing_stop_pct=1.5,
        max_position_size=10.0,
        max_drawdown_pct=10.0,
    )


async def _notify_engine_refresh() -> None:
    """Refresh engine cache so the new strategy is picked up on the next tick."""
    try:
        from app.services.auto_trade_engine import auto_trade_engine
        await auto_trade_engine._refresh_active_strategies()  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning(f"Engine refresh after opp-buy failed: {e}")


@router.post("/{symbol}/buy", status_code=201)
async def opportunity_buy(
    symbol: str,
    body: OpportunityAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buy = (1) add to watchlist + (2) create a deployed `hybrid_trend_momentum`
    Strategy + (3) notify the engine to refresh. SL/TP derived from snapshot.risk_level
    with 1:2 risk-reward minimum."""
    symbol = symbol.upper().strip()
    snap = body.snapshot or {}

    wl = await _upsert_buy_watchlist(db, current_user.id, symbol, body.exchange, snap)

    sl_pct, tp_pct = _risk_to_sl_tp(snap.get("risk_level", "moderate"))
    strategy = _build_opp_strategy(current_user.id, symbol, body.exchange, snap, sl_pct, tp_pct)
    db.add(strategy)
    await db.flush()

    await _notify_engine_refresh()

    return {
        "action": "buy",
        "symbol": symbol,
        "watchlist_id": str(wl.id),
        "strategy": {
            "id":               str(strategy.id),
            "name":             strategy.name,
            "type":             strategy.strategy_type,
            "stop_loss_pct":    sl_pct,
            "take_profit_pct":  tp_pct,
            "trailing_stop_pct": 1.5,
        },
        "engine_will_pick_up_within_seconds": 30,
    }

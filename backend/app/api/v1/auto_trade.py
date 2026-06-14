"""
Auto-Trading Engine API — control, monitor, and configure the auto-trader.
Path: backend/app/api/v1/auto_trade.py
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.v1.users import get_current_user
from app.models.user import User
from app.services.auto_trade_engine import auto_trade_engine

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response schemas ──────────────────────────────────

class EngineStartRequest(BaseModel):
    mode: str = Field("paper", pattern="^(paper|live)$")


class RiskConfigUpdate(BaseModel):
    max_daily_loss_pct: Optional[float] = Field(None, ge=0.1, le=50)
    max_position_size_pct: Optional[float] = Field(None, ge=1, le=100)
    max_open_positions: Optional[int] = Field(None, ge=1, le=50)
    max_trades_per_day: Optional[int] = Field(None, ge=1, le=200)
    trailing_stop_enabled: Optional[bool] = None
    trailing_stop_pct: Optional[float] = Field(None, ge=0.1, le=10)
    trading_capital: Optional[float] = Field(None, ge=1000)


class TrailingStopUpdate(BaseModel):
    strategy_id: str
    trailing_stop_enabled: Optional[bool] = None
    trailing_stop_pct: Optional[float] = Field(None, ge=0.1, le=10)


class ScreenRequest(BaseModel):
    strategy_type: str = "momentum"
    min_volume: int = 100000
    limit: int = 10


# ── Engine control ──────────────────────────────────────────────

@router.post("/start")
async def start_engine(
    req: EngineStartRequest = EngineStartRequest(),
    current_user: User = Depends(get_current_user),
):
    """Start the auto-trading engine."""
    auto_trade_engine.set_mode(req.mode)
    auto_trade_engine.start()
    return {
        "message": f"Auto-trade engine started in {req.mode} mode",
        "mode": req.mode,
        "is_running": True,
    }


@router.post("/stop")
async def stop_engine(current_user: User = Depends(get_current_user)):
    """Stop the auto-trading engine."""
    auto_trade_engine.stop()
    return {"message": "Auto-trade engine stopped", "is_running": False}


@router.get("/status")
async def engine_status(current_user: User = Depends(get_current_user)):
    """Get current engine status."""
    return auto_trade_engine.get_status()


# ── Positions ───────────────────────────────────────────────────

@router.get("/positions")
async def get_positions(current_user: User = Depends(get_current_user)):
    """Get all open positions managed by the engine."""
    return {"positions": auto_trade_engine.get_positions()}


# ── Activity / Trades ───────────────────────────────────────────

@router.get("/activity")
async def get_activity(
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
):
    """Get today's trading activity from the engine."""
    activity = auto_trade_engine.get_today_activity()
    return {"activity": activity[-limit:], "total": len(activity)}


# ── Risk Management ─────────────────────────────────────────────

@router.get("/risk")
async def get_risk_config(current_user: User = Depends(get_current_user)):
    """Get current risk management configuration."""
    return {"risk_config": auto_trade_engine.state.risk_config}


@router.put("/risk")
async def update_risk_config(
    req: RiskConfigUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update risk management configuration."""
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    auto_trade_engine.update_risk_config(update_data)
    return {"message": "Risk config updated", "risk_config": auto_trade_engine.state.risk_config}


# ── Stock Screener ──────────────────────────────────────────────

@router.post("/screen")
async def screen_stocks(
    req: ScreenRequest = ScreenRequest(),
    current_user: User = Depends(get_current_user),
):
    """
    Screen stocks for auto-trading opportunities.
    Returns ranked candidates based on technical analysis.
    """
    from app.services.stock_screener import stock_screener

    candidates = await stock_screener.screen_stocks(
        criteria={
            "min_volume": req.min_volume,
            "strategy_type": req.strategy_type,
        },
        limit=req.limit,
    )
    return {
        "candidates": candidates,
        "total": len(candidates),
        "strategy_type": req.strategy_type,
    }

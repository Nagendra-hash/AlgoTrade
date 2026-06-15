"""
Auto-Trading Engine API — control, monitor, and configure the auto-trader.
Path: backend/app/api/v1/auto_trade.py
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.strategy import Strategy, StrategyStatus
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


class QuickStartRequest(BaseModel):
    """One-click auto-trade: generate strategy → deploy → start engine in one tap."""
    strategy_type: str = Field("trend_following", pattern="^(trend_following|mean_reversion|momentum|breakout|scalping|swing)$")
    symbols: List[str] = Field(default_factory=lambda: ["RELIANCE", "TCS", "INFY"])
    timeframe: str = "1d"
    exchange: str = "NSE"
    mode: str = Field("paper", pattern="^(paper|live)$")
    trading_capital: float = Field(100000, ge=1000)
    max_position_size_pct: float = Field(10, ge=1, le=100)


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


# ── One-Click Quick Start ───────────────────────────────────────

QUICK_START_PROMPTS = {
    "trend_following": "EMA(20)/EMA(50) crossover with volume confirmation and 2% stop-loss, 4% take-profit for Indian equities",
    "mean_reversion": "Bollinger Band mean reversion (2 std dev) with RSI(14) <30 entry filter and 1.5% trailing stop",
    "momentum": "RSI(14) momentum strategy entering on RSI 50→70 with 3% stop-loss",
    "breakout": "20-day high breakout with volume spike (>1.5x avg) and ATR(14) based 2x stop-loss",
    "scalping": "5-minute VWAP scalping with 0.5% target and 0.3% stop-loss",
    "swing": "Daily swing trade using MACD crossover + ADX>25 trend confirmation, 5% target",
}


@router.post("/quick-start")
async def quick_start(
    req: QuickStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """One-tap auto-trading: generate AI strategy → save → deploy → start engine.

    Returns the generated strategy plus the engine status so the UI can render
    everything instantly.
    """
    from app.api.v1.strategy import _generate_ai

    # 1. Generate strategy using Emergent LLM
    prompt = QUICK_START_PROMPTS.get(req.strategy_type, QUICK_START_PROMPTS["trend_following"])
    result = await _generate_ai(prompt, req.symbols, req.timeframe)

    # 2. Persist strategy
    strategy = Strategy(
        user_id=current_user.id,
        name=f"Quick Start: {result.get('name', req.strategy_type.title())}",
        description=result.get("description"),
        strategy_type=result.get("strategy_type", req.strategy_type),
        user_prompt=prompt,
        python_code=result.get("python_code"),
        entry_logic=result.get("entry_logic"),
        exit_logic=result.get("exit_logic"),
        risk_rules=result.get("risk_rules"),
        indicators=result.get("indicators", []),
        parameters=result.get("parameters", {}),
        symbols=req.symbols,
        timeframe=req.timeframe,
        exchange=req.exchange,
        tags=(result.get("tags", []) or []) + ["quick-start"],
        status=StrategyStatus.ACTIVE.value,
        is_paper_active=(req.mode == "paper"),
        is_live_active=(req.mode == "live"),
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
        trailing_stop_enabled=True,
        trailing_stop_pct=1.5,
        max_position_size=req.max_position_size_pct,
    )
    db.add(strategy)
    await db.flush()

    # 3. Apply user risk config and start engine
    auto_trade_engine.update_risk_config({
        "trading_capital": req.trading_capital,
        "max_position_size_pct": req.max_position_size_pct,
    })
    auto_trade_engine.set_mode(req.mode)
    auto_trade_engine.start()

    return {
        "message": f"Auto-trade engine started in {req.mode} mode with new {req.strategy_type} strategy.",
        "strategy": {
            "id": str(strategy.id),
            "name": strategy.name,
            "strategy_type": strategy.strategy_type,
            "symbols": strategy.symbols,
            "indicators": strategy.indicators,
        },
        "engine": auto_trade_engine.get_status(),
    }


# ── AI Brain mode — Phase 3 ───────────────────────────────────────

class AIBrainDeploy(BaseModel):
    """Deploy a single 'ai_brain' strategy that lets the AI decide everything."""
    symbols: List[str] = Field(..., min_length=1, max_length=20)
    exchange: str = Field("NSE", max_length=10)
    timeframe: str = Field("1d", pattern="^(1d|1h|15m|5m)$")
    mode: str = Field("paper", pattern="^(paper|live)$")
    auto_start: bool = True


@router.post("/ai-brain/deploy", status_code=201)
async def deploy_ai_brain(
    body: AIBrainDeploy,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a deployed ai_brain strategy + (optionally) start the engine.

    The AI brain picks BUY/SELL/HOLD per symbol per tick, with its own
    SL/TP/qty% — the rule-based parameters are only used as a hard cap.
    """
    symbols = [s.upper().strip() for s in body.symbols]

    strategy = Strategy(
        user_id=current_user.id,
        name=f"AI Brain · {', '.join(symbols[:3])}{'…' if len(symbols) > 3 else ''}",
        description=f"LLM-driven decisions for {len(symbols)} symbols on {body.timeframe} timeframe.",
        strategy_type="ai_brain",
        user_prompt="AI brain quick-deploy from /auto-trade dashboard.",
        entry_logic="LLM evaluates technicals + sentiment + recent news → JSON decision",
        exit_logic="AI-supplied SL/TP/trailing stop. Hard caps: 5% SL / 15% TP / 25% qty.",
        risk_rules="AI must produce confidence >= 60 to trade. Default rule-based fallback if AI unavailable.",
        indicators=["RSI(14)", "MACD", "SMA(20/50)", "Volume", "News sentiment"],
        parameters={"min_confidence": 60, "decision_cache_min": 5},
        symbols=symbols,
        timeframe=body.timeframe,
        exchange=body.exchange,
        tags=["ai-brain", "auto-pilot"],
        status=StrategyStatus.ACTIVE.value,
        is_paper_active=(body.mode == "paper"),
        is_live_active=(body.mode == "live"),
        stop_loss_pct=3.0,          # hard cap; AI's value is used if smaller
        take_profit_pct=8.0,        # hard cap
        trailing_stop_enabled=True,
        trailing_stop_pct=1.5,
        max_position_size=15.0,
        max_drawdown_pct=10.0,
    )
    db.add(strategy)
    await db.flush()
    await db.refresh(strategy)

    # Refresh engine cache
    try:
        await auto_trade_engine._refresh_active_strategies()  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning(f"Engine refresh after ai-brain deploy failed: {e}")

    # Optionally start the engine
    engine_started = False
    if body.auto_start and not auto_trade_engine.get_status().get("is_running"):
        try:
            await auto_trade_engine.start(mode=body.mode)
            engine_started = True
        except Exception as e:
            logger.warning(f"Engine auto-start failed: {e}")

    return {
        "strategy": {
            "id":            str(strategy.id),
            "name":          strategy.name,
            "strategy_type": strategy.strategy_type,
            "symbols":       strategy.symbols,
            "timeframe":     strategy.timeframe,
            "mode":          body.mode,
        },
        "engine_started":  engine_started,
        "engine":          auto_trade_engine.get_status(),
        "message":         "AI Brain is now monitoring your symbols. First decision will appear within 30 seconds.",
    }

"""
Strategy CRUD + AI generation API.
Path: backend/app/api/v1/strategy.py
"""
import uuid
import json
import logging
import re
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.strategy import Strategy, StrategyStatus
from app.models.user import User
from app.schemas.strategy import (
    StrategyCreate, StrategyUpdate, StrategyResponse, StrategyGenerateRequest,
    BacktestRequest, BacktestResult,
    BacktestCompareRequest, BacktestCompareItem, CompareStrategyConfig,
)
from app.api.v1.users import get_current_user
from app.services.backtest_service import fetch_candles, run_backtest

logger = logging.getLogger(__name__)
router = APIRouter()

STRATEGY_SYSTEM_PROMPT = """You are an expert quantitative trader specializing in Indian stock markets (NSE/BSE).
Generate complete trading strategies based on the user request.
Respond ONLY with a valid JSON object (no markdown, no extra text):
{
  "name": "Strategy name",
  "description": "2-3 sentence description",
  "strategy_type": "trend_following|mean_reversion|momentum|breakout|scalping|swing|custom",
  "entry_logic": "Detailed entry conditions",
  "exit_logic": "Detailed exit conditions",
  "risk_rules": "Risk management rules",
  "indicators": ["SMA(20)", "RSI(14)"],
  "parameters": {"fast_period": {"value": 20, "min": 5, "max": 100, "step": 1, "description": "Fast MA period"}},
  "python_code": "complete runnable Python code with generate_signals(df) function",
  "tags": ["tag1", "tag2"],
  "explanation": "Beginner-friendly explanation"
}"""

FALLBACK_STRATEGY = {
    "name": "Moving Average Crossover",
    "description": "Classic trend-following strategy using 20 and 50 period EMAs.",
    "strategy_type": "trend_following",
    "entry_logic": "- EMA(20) crosses above EMA(50)\n- Price above both MAs\n- Volume above average",
    "exit_logic": "- EMA(20) crosses below EMA(50)\n- Stop loss at 2% below entry\n- Take profit at 4% above entry",
    "risk_rules": "- Max 10% capital per trade\n- 2% stop loss\n- 4% take profit\n- Max 15% drawdown",
    "indicators": ["EMA(20)", "EMA(50)", "Volume MA(20)"],
    "parameters": {
        "fast_period": {"value": 20, "min": 5, "max": 50, "step": 1, "description": "Fast EMA period"},
        "slow_period": {"value": 50, "min": 20, "max": 200, "step": 5, "description": "Slow EMA period"},
    },
    "python_code": """import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    fast, slow = 20, 50
    df["ema_fast"] = df["close"].ewm(span=fast).mean()
    df["ema_slow"] = df["close"].ewm(span=slow).mean()
    df["vol_ma"]   = df["volume"].rolling(20).mean()
    df["prev_fast"] = df["ema_fast"].shift(1)
    df["prev_slow"] = df["ema_slow"].shift(1)
    df["signal"] = 0
    buy  = (df["ema_fast"] > df["ema_slow"]) & (df["prev_fast"] <= df["prev_slow"]) & (df["volume"] > df["vol_ma"])
    sell = (df["ema_fast"] < df["ema_slow"]) & (df["prev_fast"] >= df["prev_slow"])
    df.loc[buy,  "signal"] = 1
    df.loc[sell, "signal"] = -1
    df["stop_loss"]   = 0.0
    df["take_profit"] = 0.0
    df.loc[buy, "stop_loss"]   = df.loc[buy, "close"] * 0.98
    df.loc[buy, "take_profit"] = df.loc[buy, "close"] * 1.04
    df.drop(columns=["prev_fast", "prev_slow"], inplace=True)
    df.dropna(inplace=True)
    return df
""",
    "tags": ["moving-average", "trend", "beginner"],
    "explanation": "Buy when the short-term average crosses above the long-term average (uptrend signal). Sell when it crosses below. Simple and effective for trending markets.",
}


async def _generate_ai(prompt: str, symbols: list, timeframe: str) -> dict:
    full_prompt = f"Create a trading strategy for:\nRequest: {prompt}\nSymbols: {', '.join(symbols)}\nTimeframe: {timeframe}\nMarket: NSE India\n\nRespond with JSON only."

    # Primary: Emergent Universal LLM key (Claude Sonnet 4.6)
    emergent_key = settings.EMERGENT_LLM_KEY or os.environ.get("EMERGENT_LLM_KEY")
    if emergent_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"strategy-gen-{uuid.uuid4().hex[:8]}",
                system_message=STRATEGY_SYSTEM_PROMPT,
            ).with_model("anthropic", "claude-haiku-4-5-20251001")
            response = await chat.send_message(UserMessage(text=full_prompt))
            raw = (response or "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Emergent LLM strategy generation: {e}")

    return FALLBACK_STRATEGY


@router.post("/generate")
async def generate_strategy(
    req: StrategyGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    return await _generate_ai(req.prompt, req.symbols, req.timeframe)


@router.post("/generate-and-save", response_model=StrategyResponse)
async def generate_and_save(
    req: StrategyGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await _generate_ai(req.prompt, req.symbols, req.timeframe)
    strategy = Strategy(
        user_id=current_user.id,
        name=result["name"],
        description=result.get("description"),
        strategy_type=result.get("strategy_type", "custom"),
        user_prompt=req.prompt,
        python_code=result.get("python_code"),
        entry_logic=result.get("entry_logic"),
        exit_logic=result.get("exit_logic"),
        risk_rules=result.get("risk_rules"),
        indicators=result.get("indicators", []),
        parameters=result.get("parameters", {}),
        symbols=req.symbols,
        timeframe=req.timeframe,
        exchange=req.exchange,
        tags=result.get("tags", []),
        status=StrategyStatus.DRAFT,
    )
    db.add(strategy)
    await db.flush()
    return strategy


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Strategy).where(Strategy.user_id == current_user.id)
        .order_by(Strategy.created_at.desc()).limit(limit).offset(offset)
    )
    return r.scalars().all()


@router.get("/marketplace", response_model=list[StrategyResponse])
async def marketplace(
    limit: int = Query(20, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Strategy).where(Strategy.is_public == True)
    if search:
        q = q.where(or_(
            Strategy.name.ilike(f"%{search}%"),
            Strategy.description.ilike(f"%{search}%"),
        ))
    q = q.order_by(Strategy.likes.desc()).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            or_(Strategy.user_id == current_user.id, Strategy.is_public == True),
        )
    )
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found.")
    return s


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = Strategy(user_id=current_user.id, **data.model_dump())
    db.add(s)
    await db.flush()
    return s


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    data: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
    )
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found.")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    s.version += 1
    s.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return s


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
    )
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found.")
    s.status = StrategyStatus.ARCHIVED
    await db.flush()
    return {"message": "Strategy archived."}


@router.post("/{strategy_id}/deploy")
async def deploy_strategy(
    strategy_id: uuid.UUID,
    mode: str = Query("paper"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
    )
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found.")
    if mode == "paper":
        s.is_paper_active = True
        s.status = StrategyStatus.ACTIVE
    elif mode == "live":
        s.is_live_active = True
        s.status = StrategyStatus.ACTIVE
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mode must be paper or live.")
    await db.flush()
    return {"message": f"Strategy deployed to {mode} trading.", "mode": mode}


@router.post("/{strategy_id}/clone", response_model=StrategyResponse)
async def clone_strategy(
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            or_(Strategy.user_id == current_user.id, Strategy.is_public == True),
        )
    )
    orig = r.scalar_one_or_none()
    if not orig:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found.")
    clone = Strategy(
        user_id=current_user.id, name=f"{orig.name} (Clone)",
        description=orig.description, strategy_type=orig.strategy_type,
        python_code=orig.python_code, entry_logic=orig.entry_logic,
        exit_logic=orig.exit_logic, risk_rules=orig.risk_rules,
        indicators=orig.indicators, parameters=orig.parameters,
        symbols=orig.symbols, timeframe=orig.timeframe, exchange=orig.exchange,
        tags=orig.tags, cloned_from=orig.id, status=StrategyStatus.DRAFT,
    )
    db.add(clone)
    orig.clone_count += 1
    await db.flush()
    return clone


@router.post("/backtest", response_model=BacktestResult)
async def run_strategy_backtest(
    req: BacktestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run a backtest simulation server-side.

    - Fetches historical candles from yfinance (cached in Redis)
    - Runs strategy simulation based on strategy_type or saved strategy parameters
    - Optionally saves results back to the strategy record
    """
    # Load strategy if specified
    strategy_params = None
    strategy_type = "trend_following"

    if req.strategy_id:
        r = await db.execute(
            select(Strategy).where(
                Strategy.id == req.strategy_id,
                Strategy.user_id == current_user.id,
            )
        )
        strategy = r.scalar_one_or_none()
        if not strategy:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found.")
        strategy_type = strategy.strategy_type or "trend_following"
        strategy_params = strategy.parameters

    # Fetch candle data
    candles = await fetch_candles(req.symbol, req.timeframe, req.period, req.exchange)
    if not candles:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No candle data available for {req.symbol} ({req.timeframe}/{req.period}).",
        )

    # Run simulation in thread pool (blocking numpy operations)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        run_backtest,
        candles,
        strategy_type,
        req.initial_capital,
        strategy_params,
    )

    # Build the response
    response = BacktestResult(
        total_return=result["total_return"],
        total_pnl=result["total_pnl"],
        final_capital=result["final_capital"],
        total_trades=result["total_trades"],
        win_rate=result["win_rate"],
        max_drawdown=result["max_drawdown"],
        profit_factor=result["profit_factor"],
        sharpe_ratio=result["sharpe_ratio"],
        trades=result["trades"],
        equity_curve=result["equity_curve"],
        strategy_id=str(req.strategy_id) if req.strategy_id else None,
        symbol=req.symbol,
        timeframe=req.timeframe,
        period=req.period,
        initial_capital=req.initial_capital,
        ran_at=result["ran_at"],
    )

    # Save results to strategy if requested
    if req.save_results and req.strategy_id:
        r = await db.execute(
            select(Strategy).where(
                Strategy.id == req.strategy_id,
                Strategy.user_id == current_user.id,
            )
        )
        strategy = r.scalar_one_or_none()
        if strategy:
            strategy.backtest_results = response.model_dump(mode="json")
            strategy.status = StrategyStatus.TESTED
            await db.flush()
            logger.info(f"Backtest results saved to strategy {strategy.id}")

    return response


@router.post("/backtest/compare", response_model=List[BacktestCompareItem])
async def run_compare_backtest(
    req: BacktestCompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run multiple backtests on the same data for side-by-side comparison.

    Accepts up to 6 strategy configs and a shared symbol/timeframe/period.
    Candles are fetched once and reused across all strategies.
    Returns each result with its label for easy frontend rendering.
    """
    # Fetch candles once — shared across all strategies
    candles = await fetch_candles(req.symbol, req.timeframe, req.period, req.exchange)
    if not candles:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No candle data available for {req.symbol} ({req.timeframe}/{req.period}).",
        )

    loop = asyncio.get_event_loop()
    results: list[BacktestCompareItem] = []

    for cfg in req.strategies:
        strategy_type = cfg.strategy_type
        params = cfg.parameters

        # Load from saved strategy if specified
        if cfg.strategy_id:
            r = await db.execute(
                select(Strategy).where(
                    Strategy.id == cfg.strategy_id,
                    Strategy.user_id == current_user.id,
                )
            )
            s = r.scalar_one_or_none()
            if s:
                strategy_type = s.strategy_type or "trend_following"
                params = s.parameters

        # Run in thread pool
        result = await loop.run_in_executor(
            None,
            run_backtest,
            candles,
            strategy_type,
            req.initial_capital,
            params,
        )

        results.append(BacktestCompareItem(
            label=cfg.label,
            result=BacktestResult(
                total_return=result["total_return"],
                total_pnl=result["total_pnl"],
                final_capital=result["final_capital"],
                total_trades=result["total_trades"],
                win_rate=result["win_rate"],
                max_drawdown=result["max_drawdown"],
                profit_factor=result["profit_factor"],
                sharpe_ratio=result["sharpe_ratio"],
                trades=result["trades"],
                equity_curve=result["equity_curve"],
                strategy_id=str(cfg.strategy_id) if cfg.strategy_id else None,
                symbol=req.symbol,
                timeframe=req.timeframe,
                period=req.period,
                initial_capital=req.initial_capital,
                ran_at=result["ran_at"],
            ),
        ))

    return results

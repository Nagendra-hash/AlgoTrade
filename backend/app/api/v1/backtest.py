"""
Backtest API — Phase 6.

POST /api/v1/backtest/run         — single-symbol backtest
GET  /api/v1/backtest/strategies  — list of supported strategy types

Wraps `app.services.backtest_service` (fetch_candles + run_backtest).
The hard work is done in the service; this layer is just request parsing,
auth, and pretty-printing for the UI.

Path: backend/app/api/v1/backtest.py
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.v1.users import get_current_user
from app.models.user import User
from app.services.backtest_service import fetch_candles, run_backtest

logger = logging.getLogger(__name__)
router = APIRouter()


SUPPORTED_STRATEGIES = [
    {"id": "trend_following", "label": "Trend Following (SMA crossover + volume)"},
    {"id": "mean_reversion",  "label": "Mean Reversion (Bollinger Bands)"},
    {"id": "momentum",        "label": "Momentum (Rate-of-change + volume)"},
    {"id": "hybrid_trend_momentum", "label": "Hybrid Trend + Momentum"},
]

# Period options aligned with the underlying yfinance limits
VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d", "1w"}
VALID_PERIODS = {"5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}


class BacktestRequest(BaseModel):
    symbol:         str   = Field(..., min_length=1, max_length=20)
    exchange:       str   = Field("NSE", max_length=10)
    interval:       str   = Field("1d", description="1m|5m|15m|30m|1h|1d|1w")
    period:         str   = Field("1y", description="5d|1mo|3mo|6mo|1y|2y|5y|10y|max")
    strategy_type:  str   = Field("trend_following")
    initial_capital: float = Field(1_000_000, ge=10_000)
    parameters:     dict  = Field(default_factory=dict)


class BacktestSummary(BaseModel):
    symbol: str
    strategy_type: str
    total_return: float
    total_pnl: float
    final_capital: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    profit_factor: float
    sharpe_ratio: float
    candles_used: int
    interval: str
    period: str


@router.get("/strategies")
async def list_strategies(current_user: User = Depends(get_current_user)):
    """List backtestable strategy types — used to populate the form dropdown."""
    return {"strategies": SUPPORTED_STRATEGIES}


@router.post("/run")
async def run(
    body: BacktestRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Run a backtest for one symbol with the chosen strategy + parameters.

    Returns:
      - summary metrics (win rate, Sharpe, drawdown, profit factor, …)
      - the trade ledger (last 50)
      - the equity curve (down-sampled to ≤200 points)
    """
    if body.interval not in VALID_INTERVALS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid interval. Allowed: {sorted(VALID_INTERVALS)}")
    if body.period not in VALID_PERIODS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid period. Allowed: {sorted(VALID_PERIODS)}")
    if body.strategy_type not in {s["id"] for s in SUPPORTED_STRATEGIES}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported strategy_type: {body.strategy_type}")

    candles = await fetch_candles(
        symbol=body.symbol.upper(),
        interval=body.interval,
        period=body.period,
        exchange=body.exchange,
    )
    if not candles:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"No candles returned for {body.symbol}")

    result = run_backtest(
        candles=candles,
        strategy_type=body.strategy_type,
        initial_capital=body.initial_capital,
        parameters=body.parameters or {},
    )

    # Decorate summary keys for the UI
    summary = {
        "symbol":         body.symbol.upper(),
        "exchange":       body.exchange.upper(),
        "strategy_type":  body.strategy_type,
        "interval":       body.interval,
        "period":         body.period,
        "candles_used":   len(candles),
        "initial_capital": body.initial_capital,
        "total_return":   result.get("total_return", 0),
        "total_pnl":      result.get("total_pnl", 0),
        "final_capital":  result.get("final_capital", body.initial_capital),
        "total_trades":   result.get("total_trades", 0),
        "win_rate":       result.get("win_rate", 0),
        "max_drawdown":   result.get("max_drawdown", 0),
        "profit_factor":  result.get("profit_factor", 0),
        "sharpe_ratio":   result.get("sharpe_ratio", 0),
        "ran_at":         result.get("ran_at"),
    }

    return {
        "summary":      summary,
        "trades":       result.get("trades", [])[-50:],
        "equity_curve": result.get("equity_curve", []),
        "error":        result.get("error"),
    }

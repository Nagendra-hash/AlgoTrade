"""
Strategy Pydantic schemas.
Path: backend/app/schemas/strategy.py
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import uuid


class StrategyGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=2000)
    symbols: List[str] = Field(default=["NIFTY50"])
    timeframe: str = "1d"
    exchange: str = "NSE"
    ai_provider: str = "claude"


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    python_code: Optional[str] = None
    entry_logic: Optional[str] = None
    exit_logic: Optional[str] = None
    risk_rules: Optional[str] = None
    indicators: Optional[List[str]] = None
    parameters: Optional[dict] = None
    symbols: Optional[List[str]] = ["NIFTY50"]
    timeframe: Optional[str] = "1d"
    exchange: Optional[str] = "NSE"
    strategy_type: Optional[str] = "custom"
    stop_loss_pct: Optional[float] = 2.0
    take_profit_pct: Optional[float] = 4.0
    trailing_stop_enabled: Optional[bool] = True
    trailing_stop_pct: Optional[float] = 1.5
    tags: Optional[List[str]] = []


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    python_code: Optional[str] = None
    entry_logic: Optional[str] = None
    exit_logic: Optional[str] = None
    parameters: Optional[dict] = None
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None
    is_public: Optional[bool] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_enabled: Optional[bool] = None
    trailing_stop_pct: Optional[float] = Field(None, ge=0.1, le=10)
    tags: Optional[List[str]] = None


class BacktestRequest(BaseModel):
    strategy_id: Optional[uuid.UUID] = None
    symbol: str = "NIFTY50"
    exchange: str = "NSE"
    timeframe: str = "1d"
    period: str = "1y"
    initial_capital: float = 1_000_000
    save_results: bool = True


class BacktestTrade(BaseModel):
    entry_date: str
    exit_date: str
    side: str  # BUY / SELL
    qty: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float


class BacktestResult(BaseModel):
    total_return: float
    total_pnl: float
    final_capital: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    profit_factor: float
    sharpe_ratio: float
    trades: List[BacktestTrade]
    equity_curve: List[dict]
    strategy_id: Optional[str] = None
    symbol: str
    timeframe: str
    period: str
    initial_capital: float
    ran_at: str


class CompareStrategyConfig(BaseModel):
    """Single strategy slot within a comparison."""
    label: str = "Strategy 1"
    strategy_id: Optional[uuid.UUID] = None
    strategy_type: str = "trend_following"
    parameters: Optional[dict] = None


class BacktestCompareRequest(BaseModel):
    """Run multiple backtests on the same data for side-by-side comparison."""
    strategies: List[CompareStrategyConfig] = Field(..., min_length=2, max_length=6)
    symbol: str = "NIFTY50"
    exchange: str = "NSE"
    timeframe: str = "1d"
    period: str = "1y"
    initial_capital: float = 1_000_000


class BacktestCompareItem(BaseModel):
    """One strategy's result within a comparison."""
    label: str
    result: BacktestResult


class StrategyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    strategy_type: str
    status: str
    version: int
    user_prompt: Optional[str]
    python_code: Optional[str]
    entry_logic: Optional[str]
    exit_logic: Optional[str]
    risk_rules: Optional[str]
    indicators: Optional[List[str]]
    parameters: Optional[dict]
    symbols: Optional[List[str]]
    timeframe: str
    exchange: str
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_enabled: bool
    trailing_stop_pct: float
    backtest_results: Optional[dict]
    is_public: bool
    is_paper_active: bool
    is_live_active: bool
    clone_count: int
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

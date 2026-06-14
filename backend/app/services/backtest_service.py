"""
Server-side backtest engine — runs strategy simulations against historical candle data.
Path: backend/app/services/backtest_service.py
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np

from app.core.redis import redis_get, redis_set
from app.core.config import settings

logger = logging.getLogger(__name__)

NSE_TO_YF = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "WIPRO": "WIPRO.NS", "BAJFINANCE": "BAJFINANCE.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "ADANIENT": "ADANIENT.NS", "HINDUNILVR": "HINDUNILVR.NS",
    "BHARTIARTL": "BHARTIARTL.NS", "ASIANPAINT": "ASIANPAINT.NS",
    "MARUTI": "MARUTI.NS", "SUNPHARMA": "SUNPHARMA.NS",
    "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
}


def _fetch_candles_sync(yf_symbol: str, interval: str, period: str) -> list:
    """Fetch historical candles from yfinance (sync, runs in thread pool)."""
    iv_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
              "1h": "1h", "1d": "1d", "1w": "1wk"}
    yf_iv = iv_map.get(interval, "1d")
    try:
        df = yf.download(yf_symbol, period=period, interval=yf_iv, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        if df.empty:
            return []
        out = []
        for ts, row in df.iterrows():
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts.value // 1e9)
            out.append({
                "time": t,
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row.get("volume", 0)),
            })
        return sorted(out, key=lambda x: x["time"])
    except Exception as e:
        logger.error(f"Backtest candle fetch {yf_symbol}: {e}")
        return []


async def fetch_candles(symbol: str, interval: str, period: str, exchange: str = "NSE") -> list:
    """Fetch historical candle data for backtesting with Redis caching."""
    sym = symbol.upper()
    cache_key = f"backtest:candles:{exchange}:{sym}:{interval}:{period}"

    cached = await redis_get(cache_key)
    if cached:
        return cached

    yf_sym = NSE_TO_YF.get(sym, sym + ".NS")
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_candles_sync, yf_sym, interval, period)

    if data:
        # Cache longer for backtest data (1 hour)
        await redis_set(cache_key, data, ttl=3600)
    return data


def run_backtest(
    candles: list,
    strategy_type: str = "trend_following",
    initial_capital: float = 1_000_000,
    parameters: Optional[dict] = None,
) -> dict:
    """
    Run a backtest simulation.

    Supports four strategy types:
    - trend_following: SMA crossover with volume confirmation
    - mean_reversion: Bollinger Band mean reversion
    - momentum: ROC + volume momentum
    - hybrid_trend_momentum: Hybrid of trend following + momentum confirmation

    Returns a dict with performance metrics, trades, and equity curve.
    """
    if not candles or len(candles) < 30:
        return {
            "error": "Insufficient candle data (need at least 30 candles)",
            "total_return": 0, "total_pnl": 0, "final_capital": initial_capital,
            "total_trades": 0, "win_rate": 0, "max_drawdown": 0,
            "profit_factor": 0, "sharpe_ratio": 0, "trades": [], "equity_curve": [],
        }

    capital = float(initial_capital)
    position = 0
    entry_price = 0.0
    trades = []
    equity_curve = []
    peak = capital
    max_drawdown = 0.0
    wins = 0
    losses = 0

    params = parameters or {}
    fast_period = int(params.get("fast_period", 20))
    slow_period = int(params.get("slow_period", 50))
    bb_std = float(params.get("bb_std", 2.5))
    roc_period = int(params.get("roc_period", 10))
    roc_threshold = float(params.get("roc_threshold", 2.0))

    for i in range(len(candles)):
        c = candles[i]
        if i < max(fast_period, slow_period, roc_period):
            equity_curve.append({"date": c["time"], "value": round(capital)})
            continue

        # Calculate indicators for current candle
        closes = [x["close"] for x in candles[:i + 1]]
        volumes = [x["volume"] for x in candles[max(0, i - 10):i + 1]]
        avg_vol = sum(volumes) / len(volumes) if volumes else 1

        sma_fast = sum(closes[-fast_period:]) / fast_period
        sma_slow = sum(closes[-slow_period:]) / slow_period
        sma20 = sum(closes[-20:]) / 20

        signal = 0

        if strategy_type == "mean_reversion":
            std_dev = np.std(closes[-20:]) if len(closes) >= 20 else 0
            bb_upper = sma20 + bb_std * std_dev
            bb_lower = sma20 - bb_std * std_dev
            if c["close"] < bb_lower and c["volume"] > avg_vol * 1.2:
                signal = 1
            elif c["close"] > bb_upper:
                signal = -1

        elif strategy_type == "momentum":
            roc = ((c["close"] / closes[-roc_period]) - 1) * 100
            if roc > roc_threshold and c["volume"] > avg_vol:
                signal = 1
            elif roc < -roc_threshold:
                signal = -1

        elif strategy_type == "hybrid_trend_momentum":
            # Hybrid: Trend Following + Momentum confirmation
            prev_fast = sum(closes[-(fast_period + 1):-1]) / fast_period
            prev_slow = sum(closes[-(slow_period + 1):-1]) / slow_period
            # Momentum: ROC over ROC period
            roc = ((c["close"] / closes[-roc_period]) - 1) * 100
            # Entry: SMA crossover + ROC > 1% (momentum confirmation) + volume
            if sma_fast > sma_slow and prev_fast <= prev_slow and roc > 1.0 and c["volume"] > avg_vol:
                signal = 1
            # Exit: Either trend reversal OR momentum reversal
            elif sma_fast < sma_slow and prev_fast >= prev_slow:
                signal = -1
            elif roc < 0 and position > 0:
                # Momentum fizzled — close position
                signal = -1

        else:
            # Trend following (SMA crossover)
            prev_fast = sum(closes[-(fast_period + 1):-1]) / fast_period
            prev_slow = sum(closes[-(slow_period + 1):-1]) / slow_period
            if sma_fast > sma_slow and prev_fast <= prev_slow and c["volume"] > avg_vol:
                signal = 1
            elif sma_fast < sma_slow and prev_fast >= prev_slow:
                signal = -1

        # Execute signals
        if signal == 1 and position == 0:
            qty = int((capital * 0.95) / c["close"])
            if qty > 0:
                position = qty
                entry_price = c["close"]
                capital -= position * entry_price

        elif signal == -1 and position > 0:
            exit_price = c["close"]
            pnl = (exit_price - entry_price) * position
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            capital += position * exit_price
            trades.append({
                "entry_date": datetime.fromtimestamp(candles[i - 1]["time"]).strftime("%Y-%m-%d"),
                "exit_date": datetime.fromtimestamp(c["time"]).strftime("%Y-%m-%d"),
                "side": "BUY",
                "qty": position,
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            position = 0
            entry_price = 0.0

        total_value = capital + position * (c["close"] if position else 0)
        equity_curve.append({"date": c["time"], "value": round(total_value)})
        peak = max(peak, total_value)
        if peak > 0:
            dd = (peak - total_value) / peak * 100
            max_drawdown = max(max_drawdown, dd)

    # Close any remaining position at last candle
    if position > 0 and candles:
        last = candles[-1]
        exit_price = last["close"]
        pnl = (exit_price - entry_price) * position
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        capital += position * exit_price
        trades.append({
            "entry_date": datetime.fromtimestamp(candles[-2]["time"]).strftime("%Y-%m-%d") if len(candles) >= 2 else "N/A",
            "exit_date": datetime.fromtimestamp(last["time"]).strftime("%Y-%m-%d"),
            "side": "SELL",
            "qty": position,
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
        if pnl > 0:
            wins += 1
        else:
            losses += 1

    total_trades = len(trades)
    total_pnl = capital - initial_capital
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    # Profit factor: sum of wins / sum of losses
    sum_wins = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    sum_losses = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 0 else (999 if total_trades > 0 else 0)

    # Approximate Sharpe ratio (assuming daily returns)
    returns = []
    for i in range(1, len(equity_curve)):
        prev_val = equity_curve[i - 1]["value"]
        cur_val = equity_curve[i]["value"]
        if prev_val > 0:
            returns.append((cur_val - prev_val) / prev_val)
    avg_ret = np.mean(returns) if returns else 0
    std_ret = np.std(returns) if returns else 1
    sharpe = (avg_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0

    return {
        "total_return": round(((capital / initial_capital) - 1) * 100, 2),
        "total_pnl": round(total_pnl),
        "final_capital": round(capital),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_drawdown, 2),
        "profit_factor": profit_factor,
        "sharpe_ratio": round(float(sharpe), 2),
        "trades": trades[-50:],  # Last 50 trades
        "equity_curve": equity_curve[::max(1, len(equity_curve) // 200)],  # Sample to max 200 points
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }

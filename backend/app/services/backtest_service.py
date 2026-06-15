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


def _synthetic_candles(symbol: str, interval: str, period: str) -> list:
    """Generate realistic synthetic OHLC data as a fallback when yfinance is unavailable.

    Uses geometric Brownian motion seeded by the symbol so results are
    reproducible per symbol. This lets users explore the backtest UI even
    when the external data provider rate-limits or fails.
    """
    import hashlib, math, random
    bars_map = {"1d": {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504, "5y": 1260},
                "1h": {"1mo": 160, "3mo": 480, "6mo": 960},
                "1wk": {"6mo": 26, "1y": 52, "2y": 104, "5y": 260}}
    iv = "1d" if interval not in bars_map else interval
    bars = bars_map.get(iv, {}).get(period, 132)
    step_sec = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "1d": 86400, "1wk": 604800}.get(iv, 86400)

    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    price = 1000 + (seed % 4000)  # Starting price between 1000-5000
    drift = 0.0003
    vol = 0.018
    out = []
    import time as _t
    now = int(_t.time())
    start = now - bars * step_sec
    for i in range(bars):
        t = start + i * step_sec
        rtn = drift + vol * rnd.gauss(0, 1)
        open_p = price
        close = round(price * math.exp(rtn), 2)
        high = round(max(open_p, close) * (1 + abs(rnd.gauss(0, 0.004))), 2)
        low = round(min(open_p, close) * (1 - abs(rnd.gauss(0, 0.004))), 2)
        vol_shares = int(100_000 + rnd.random() * 900_000)
        out.append({"time": t, "open": round(open_p, 2), "high": high, "low": low, "close": close, "volume": vol_shares})
        price = close
    return out


async def fetch_candles(symbol: str, interval: str, period: str, exchange: str = "NSE") -> list:
    """Fetch historical candle data for backtesting with layered caching.

    Resolution order:
      1. Redis (hot cache, 1h TTL)
      2. PostgreSQL candle_cache (persistent, refreshed daily)
      3. yfinance (live fetch)
      4. Deterministic synthetic fallback (last resort so the UI stays usable)
    """
    from app.core.database import AsyncSessionLocal
    from app.models.candle_cache import CandleCache
    from sqlalchemy import select
    from datetime import timedelta

    sym = symbol.upper()
    cache_key = f"backtest:candles:{exchange}:{sym}:{interval}:{period}"

    # 1) Redis hot cache
    cached = await redis_get(cache_key)
    if cached:
        return cached

    yf_sym = NSE_TO_YF.get(sym, sym + ".NS")
    now = datetime.now(timezone.utc)
    # Daily candles can be cached for a day; intraday refreshes every hour
    pg_ttl = timedelta(hours=24 if interval in ("1d", "1wk") else 1)

    # 2) PostgreSQL persistent cache
    db_row: Optional[CandleCache] = None
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(CandleCache).where(
                    CandleCache.symbol == sym,
                    CandleCache.exchange == exchange,
                    CandleCache.interval == interval,
                    CandleCache.period == period,
                )
            )
            db_row = r.scalar_one_or_none()
            if db_row and (now - db_row.fetched_at) < pg_ttl and db_row.candles:
                await redis_set(cache_key, db_row.candles, ttl=3600)
                return db_row.candles
    except Exception as e:
        logger.warning(f"PG candle cache read failed: {e}")

    # 3) Try yfinance live fetch
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_candles_sync, yf_sym, interval, period)
    source = "yfinance"

    # 4) Fallback to stale PG cache, then synthetic
    if not data:
        if db_row and db_row.candles:
            logger.info(f"yfinance unavailable for {yf_sym}; serving stale PG cache ({db_row.bar_count} bars)")
            await redis_set(cache_key, db_row.candles, ttl=3600)
            return db_row.candles
        logger.warning(f"yfinance returned no data for {yf_sym}; using synthetic fallback")
        data = _synthetic_candles(sym, interval, period)
        source = "synthetic"

    if data:
        await redis_set(cache_key, data, ttl=3600)
        # Persist to PG (only real yfinance data; not synthetic)
        if source == "yfinance":
            try:
                async with AsyncSessionLocal() as db:
                    r = await db.execute(
                        select(CandleCache).where(
                            CandleCache.symbol == sym,
                            CandleCache.exchange == exchange,
                            CandleCache.interval == interval,
                            CandleCache.period == period,
                        )
                    )
                    existing = r.scalar_one_or_none()
                    if existing:
                        existing.candles = data
                        existing.bar_count = len(data)
                        existing.fetched_at = now
                        existing.source = source
                    else:
                        db.add(CandleCache(
                            symbol=sym, exchange=exchange, interval=interval,
                            period=period, candles=data, bar_count=len(data),
                            fetched_at=now, source=source,
                        ))
                    await db.commit()
            except Exception as e:
                logger.warning(f"PG candle cache write failed: {e}")
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

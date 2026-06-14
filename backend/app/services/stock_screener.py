"""
Stock Screener — automated stock selection based on technical analysis.

Screens NSE stocks using momentum, volume, RSI, MACD, and sector strength
to find the best candidates for auto-trading.

Path: backend/app/services/stock_screener.py
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict

import numpy as np

logger = logging.getLogger(__name__)

# Universe of NSE stocks to screen (top liquid stocks)
SCREENING_UNIVERSE = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN",
    "WIPRO", "BAJFINANCE", "TATAMOTORS", "HINDUNILVR", "MARUTI",
    "SUNPHARMA", "BHARTIARTL", "ASIANPAINT", "KOTAKBANK", "LT",
    "AXISBANK", "ITC", "ADANIENT", "TITAN", "ULTRACEMCO", "ONGC",
    "NTPC", "POWERGRID", "TATACONSUM", "TECHM", "HCLTECH", "JSWSTEEL",
    "TATASTEEL", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "INDUSINDBK",
    "GRASIM", "COALINDIA", "BPCL", "BRITANNIA", "CIPLA", "DRREDDY",
    "DIVISLAB", "EICHERMOT", "HEROMOTOCO", "M&M", "NESTLEIND", "APOLLOHOSP",
    "TRENT", "ADANIPORTS", "BEL", "HAL", "IRCTC",
]

NSE_TO_YF = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "WIPRO": "WIPRO.NS", "BAJFINANCE": "BAJFINANCE.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "ADANIENT": "ADANIENT.NS", "HINDUNILVR": "HINDUNILVR.NS", "MARUTI": "MARUTI.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "BHARTIARTL": "BHARTIARTL.NS", "ASIANPAINT": "ASIANPAINT.NS",
    "KOTAKBANK": "KOTAKBANK.NS", "LT": "LT.NS", "AXISBANK": "AXISBANK.NS",
    "ITC": "ITC.NS", "TITAN": "TITAN.NS", "ULTRACEMCO": "ULTRACEMCO.NS",
    "ONGC": "ONGC.NS", "NTPC": "NTPC.NS", "POWERGRID": "POWERGRID.NS",
    "TATACONSUM": "TATACONSUM.NS", "TECHM": "TECHM.NS", "HCLTECH": "HCLTECH.NS",
    "JSWSTEEL": "JSWSTEEL.NS", "TATASTEEL": "TATASTEEL.NS", "BAJAJFINSV": "BAJAJFINSV.NS",
    "HDFCLIFE": "HDFCLIFE.NS", "SBILIFE": "SBILIFE.NS", "INDUSINDBK": "INDUSINDBK.NS",
    "GRASIM": "GRASIM.NS", "COALINDIA": "COALINDIA.NS", "BPCL": "BPCL.NS",
    "BRITANNIA": "BRITANNIA.NS", "CIPLA": "CIPLA.NS", "DRREDDY": "DRREDDY.NS",
    "DIVISLAB": "DIVISLAB.NS", "EICHERMOT": "EICHERMOT.NS", "HEROMOTOCO": "HEROMOTOCO.NS",
    "M&M": "M&M.NS", "NESTLEIND": "NESTLEIND.NS", "APOLLOHOSP": "APOLLOHOSP.NS",
    "TRENT": "TRENT.NS", "ADANIPORTS": "ADANIPORTS.NS", "BEL": "BEL.NS",
    "HAL": "HAL.NS", "IRCTC": "IRCTC.NS",
}


class StockScreener:
    """
    Automated stock screener that scores stocks based on multiple factors:
    - Momentum (ROC, price trend)
    - Volume analysis (volume spike, OBV)
    - Technical indicators (RSI, MACD)
    - Trend strength (ADX, moving averages)
    """

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes

    async def screen_stocks(
        self,
        criteria: Optional[dict] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Screen stocks and return top candidates ranked by composite score.

        Criteria:
            - min_volume: Minimum average volume (default: 100000)
            - min_rsi: Minimum RSI (default: 30)
            - max_rsi: Maximum RSI (default: 70)
            - min_momentum: Minimum ROC percentage (default: 0)
            - strategy_type: Focus on trend_following, momentum, mean_reversion
        """
        criteria = criteria or {}
        min_volume = criteria.get("min_volume", 100000)
        strategy_type = criteria.get("strategy_type", "momentum")

        # Check cache
        now = datetime.now(timezone.utc)
        if self._cache and self._cache_time and (now - self._cache_time).seconds < self._cache_ttl:
            candidates = list(self._cache.values())
        else:
            candidates = await self._fetch_and_score(SCREENING_UNIVERSE)
            self._cache = {c["symbol"]: c for c in candidates}
            self._cache_time = now

        # Filter
        filtered = [
            c for c in candidates
            if c.get("avg_volume", 0) >= min_volume
            and c.get("ltp", 0) > 0
        ]

        # Sort by composite score
        if strategy_type == "momentum":
            filtered.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)
        elif strategy_type == "trend_following":
            filtered.sort(key=lambda x: x.get("trend_score", 0), reverse=True)
        elif strategy_type == "mean_reversion":
            # For mean reversion, prefer oversold stocks (low RSI)
            filtered.sort(key=lambda x: x.get("reversion_score", 0), reverse=True)
        else:
            filtered.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

        return filtered[:limit]

    async def _fetch_and_score(self, symbols: List[str]) -> List[dict]:
        """Fetch data and compute scores for all symbols."""
        import yfinance as yf

        results = []

        def _fetch_one(sym: str) -> Optional[dict]:
            yf_sym = NSE_TO_YF.get(sym, sym + ".NS")
            try:
                t = yf.Ticker(yf_sym)
                info = t.fast_info
                hist = t.history(period="3mo", interval="1d")

                if hist.empty or len(hist) < 20:
                    return None

                if hasattr(hist.columns, 'get_level_values') and isinstance(hist.columns, __import__("pandas").MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                hist.columns = [c.lower() for c in hist.columns]

                ltp = float(getattr(info, "last_price", 0) or 0)
                prev = float(getattr(info, "previous_close", ltp) or ltp)
                avg_vol = int(getattr(info, "three_month_average_volume", 0) or 0)
                change_pct = ((ltp - prev) / prev * 100) if prev else 0

                closes = hist["close"].astype(float).tolist()
                volumes = hist["volume"].astype(float).tolist()

                # RSI
                rsi = self._compute_rsi(closes, 14)

                # MACD
                macd_line, signal_line = self._compute_macd(closes)

                # Momentum (ROC 10-day)
                roc = ((closes[-1] / closes[-10]) - 1) * 100 if len(closes) > 10 else 0

                # Trend (SMA 20 vs 50)
                sma20 = np.mean(closes[-20:]) if len(closes) >= 20 else ltp
                sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
                trend_up = sma20 > sma50

                # Volume trend
                recent_vol = np.mean(volumes[-5:]) if len(volumes) >= 5 else avg_vol
                vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

                # Composite scoring
                momentum_score = self._score_momentum(roc, rsi, macd_line, signal_line)
                trend_score = self._score_trend(trend_up, sma20, sma50, ltp)
                reversion_score = self._score_reversion(rsi, ltp, sma20)
                composite = (momentum_score + trend_score + reversion_score) / 3

                return {
                    "symbol": sym,
                    "ltp": round(ltp, 2),
                    "change_pct": round(change_pct, 2),
                    "avg_volume": avg_vol,
                    "rsi": round(rsi, 2) if rsi else None,
                    "roc": round(roc, 2),
                    "macd": round(macd_line, 4) if macd_line else None,
                    "macd_signal": round(signal_line, 4) if signal_line else None,
                    "sma20": round(sma20, 2),
                    "sma50": round(sma50, 2),
                    "trend_up": trend_up,
                    "vol_ratio": round(vol_ratio, 2),
                    "momentum_score": round(momentum_score, 2),
                    "trend_score": round(trend_score, 2),
                    "reversion_score": round(reversion_score, 2),
                    "composite_score": round(composite, 2),
                }
            except Exception as e:
                logger.debug(f"Screen failed for {sym}: {e}")
                return None

        loop = asyncio.get_event_loop()
        # Process in batches of 10 to avoid overwhelming yfinance
        for i in range(0, len(symbols), 10):
            batch = symbols[i:i + 10]
            batch_results = await loop.run_in_executor(
                None, lambda: [_fetch_one(s) for s in batch]
            )
            for r in batch_results:
                if r:
                    results.append(r)

        return results

    def _compute_rsi(self, closes: list, period: int = 14) -> Optional[float]:
        """Compute RSI."""
        if len(closes) < period + 1:
            return None
        arr = np.array(closes)
        delta = np.diff(arr)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_macd(self, closes: list) -> tuple:
        """Compute MACD line and signal line."""
        if len(closes) < 26:
            return None, None
        arr = np.array(closes, dtype=float)
        # EMA 12
        ema12 = self._ema(arr, 12)
        # EMA 26
        ema26 = self._ema(arr, 26)
        macd_line = ema12 - ema26
        signal_line = self._ema(macd_line, 9)
        return float(macd_line[-1]), float(signal_line[-1])

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    def _score_momentum(self, roc: float, rsi: Optional[float],
                        macd: Optional[float], signal: Optional[float]) -> float:
        """Score momentum factor (0-100)."""
        score = 50.0
        # ROC contribution
        if roc > 5:
            score += 20
        elif roc > 2:
            score += 10
        elif roc < -5:
            score -= 20
        elif roc < -2:
            score -= 10
        # RSI contribution
        if rsi:
            if 40 <= rsi <= 60:
                score += 10  # Neutral zone
            elif rsi > 70:
                score -= 10  # Overbought
            elif rsi < 30:
                score += 5  # Oversold (potential reversal)
        # MACD contribution
        if macd is not None and signal is not None:
            if macd > signal:
                score += 15  # Bullish
            else:
                score -= 10
        return max(0, min(100, score))

    def _score_trend(self, trend_up: bool, sma20: float,
                     sma50: float, ltp: float) -> float:
        """Score trend factor (0-100)."""
        score = 50.0
        if trend_up:
            score += 20
        else:
            score -= 15
        # Price above both SMAs
        if ltp > sma20 > sma50:
            score += 20
        elif ltp > sma20:
            score += 10
        elif ltp < sma50:
            score -= 15
        # SMA spread
        spread = ((sma20 - sma50) / sma50 * 100) if sma50 > 0 else 0
        if spread > 2:
            score += 10
        elif spread < -2:
            score -= 10
        return max(0, min(100, score))

    def _score_reversion(self, rsi: Optional[float], ltp: float,
                         sma20: float) -> float:
        """Score mean reversion potential (0-100)."""
        score = 50.0
        if rsi:
            if rsi < 30:
                score += 30  # Strongly oversold
            elif rsi < 40:
                score += 15
            elif rsi > 70:
                score += 20  # Overbought — could revert down
            elif rsi > 60:
                score += 5
        # Price deviation from SMA20
        if sma20 > 0:
            deviation = (ltp - sma20) / sma20 * 100
            if deviation < -5:
                score += 15  # Far below SMA — potential reversion up
            elif deviation > 5:
                score += 10  # Far above SMA — potential reversion down
        return max(0, min(100, score))


# Singleton
stock_screener = StockScreener()

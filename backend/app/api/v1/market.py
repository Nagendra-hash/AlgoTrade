"""
Market data API — quotes, candles, search, indices.
Path: backend/app/api/v1/market.py

Data sources (in priority order):
  1. Angel One SmartAPI (when broker is connected)
  2. Zerodha Kite Connect (when broker is connected)
  3. Yahoo Finance v8 REST API (fallback, replaces deprecated yfinance)
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query, WebSocket

from app.core.redis import redis_get, redis_set
from app.websockets.market_ws import market_ws_endpoint
from app.api.v1.users import get_current_user
from app.models.user import User
from app.services.angel_one import get_session as get_angel_session, get_market_quote_angel, get_market_candles_angel
from app.services.zerodha import get_session as get_zerodha_session, get_market_quote_zerodha, get_market_candles_zerodha

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Yahoo Finance v8 API symbol mapping ─────────────────────
# Indian symbols need .NS suffix for NSE stocks; indices use ^ prefix
NSE_TO_YF = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "WIPRO": "WIPRO.NS", "BAJFINANCE": "BAJFINANCE.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "ADANIENT": "ADANIENT.NS", "HINDUNILVR": "HINDUNILVR.NS",
    "BHARTIARTL": "BHARTIARTL.NS", "ASIANPAINT": "ASIANPAINT.NS",
    "MARUTI": "MARUTI.NS", "SUNPHARMA": "SUNPHARMA.NS",
    "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
}

_INSTRUMENTS = [
    {"symbol": "RELIANCE",   "name": "Reliance Industries",      "exchange": "NSE", "sector": "Energy"},
    {"symbol": "TCS",        "name": "Tata Consultancy Services", "exchange": "NSE", "sector": "IT"},
    {"symbol": "INFY",       "name": "Infosys Limited",           "exchange": "NSE", "sector": "IT"},
    {"symbol": "HDFCBANK",   "name": "HDFC Bank",                 "exchange": "NSE", "sector": "Banking"},
    {"symbol": "ICICIBANK",  "name": "ICICI Bank",                "exchange": "NSE", "sector": "Banking"},
    {"symbol": "SBIN",       "name": "State Bank of India",       "exchange": "NSE", "sector": "Banking"},
    {"symbol": "WIPRO",      "name": "Wipro Limited",             "exchange": "NSE", "sector": "IT"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance",             "exchange": "NSE", "sector": "Finance"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors",              "exchange": "NSE", "sector": "Auto"},
    {"symbol": "ADANIENT",   "name": "Adani Enterprises",         "exchange": "NSE", "sector": "Conglomerate"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever",        "exchange": "NSE", "sector": "FMCG"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel",             "exchange": "NSE", "sector": "Telecom"},
    {"symbol": "ASIANPAINT", "name": "Asian Paints",              "exchange": "NSE", "sector": "Paint"},
    {"symbol": "MARUTI",     "name": "Maruti Suzuki",             "exchange": "NSE", "sector": "Auto"},
    {"symbol": "SUNPHARMA",  "name": "Sun Pharmaceutical",        "exchange": "NSE", "sector": "Pharma"},
    {"symbol": "NIFTY50",    "name": "NIFTY 50 Index",            "exchange": "NSE", "sector": "Index"},
    {"symbol": "BANKNIFTY",  "name": "BANK NIFTY Index",          "exchange": "NSE", "sector": "Index"},
    {"symbol": "SENSEX",     "name": "BSE SENSEX",                "exchange": "BSE", "sector": "Index"},
]

YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
YF_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def _fetch_quote_sync(yf_symbol: str) -> dict:
    """
    Fetch a single quote from the Yahoo Finance v8 REST API.
    Replaces the deprecated yfinance library which has reliability issues
    with Indian index symbols (^NSEI, ^BSESN, etc.).
    """
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{YF_BASE}/{yf_symbol}?interval=1d&range=1d",
                headers=YF_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        result = data["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]

        ltp = float(meta.get("regularMarketPrice", 0) or 0)
        prev = float(meta.get("chartPreviousClose", ltp) or ltp)

        # Extract last valid values from the quotes arrays
        opens = [v for v in (quotes.get("open") or []) if v is not None]
        highs = [v for v in (quotes.get("high") or []) if v is not None]
        lows = [v for v in (quotes.get("low") or []) if v is not None]
        volumes = [v for v in (quotes.get("volume") or []) if v is not None]

        open_val = float(opens[-1]) if opens else ltp
        high_val = float(highs[-1]) if highs else ltp
        low_val = float(lows[-1]) if lows else ltp
        volume = int(volumes[-1]) if volumes else 0

        change = ltp - prev
        chg_pct = (change / prev * 100) if prev else 0

        return {
            "ltp": round(ltp, 2),
            "open": round(open_val, 2),
            "high": round(high_val, 2),
            "low": round(low_val, 2),
            "prev_close": round(prev, 2),
            "change": round(change, 2),
            "change_pct": round(chg_pct, 2),
            "volume": volume,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Quote fetch failed for {yf_symbol}: {e}")
        return {
            "ltp": 0, "change_pct": 0, "change": 0, "volume": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def _get_quote(
    symbol: str, exchange: str = "NSE", user_id: Optional[str] = None
) -> dict:
    """
    Internal: fetch quote from broker (real-time) or Yahoo Finance (delayed).
    Priority: Angel One → Zerodha → Yahoo Finance v8 API
    Returns `source` field indicating data origin.
    """
    sym = symbol.upper()

    if user_id:
        # Try Angel One first (real-time)
        angel_session = await get_angel_session(user_id)
        if angel_session:
            angel_data = await get_market_quote_angel(user_id, sym, exchange)
            if angel_data:
                return {**angel_data, "symbol": sym, "exchange": exchange}

        # Try Zerodha second (real-time)
        zerodha_session = await get_zerodha_session(user_id)
        if zerodha_session:
            zerodha_data = await get_market_quote_zerodha(user_id, sym, exchange)
            if zerodha_data:
                return {**zerodha_data, "symbol": sym, "exchange": exchange}

    # Fallback: Yahoo Finance v8 API with Redis caching
    key = f"quote:{exchange}:{sym}"
    cached = await redis_get(key)
    if cached:
        return {**cached, "symbol": sym, "exchange": exchange, "source": "yahoo_finance"}
    yf_sym = NSE_TO_YF.get(sym, sym + ".NS")
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_quote_sync, yf_sym)
    await redis_set(key, data, ttl=3)
    return {**data, "symbol": sym, "exchange": exchange, "source": "yahoo_finance"}


@router.get("/quote/{symbol}")
async def get_quote_route(
    symbol: str,
    exchange: str = Query("NSE"),
    current_user: User = Depends(get_current_user),
):
    """Get real-time quote. Uses broker when connected, else Yahoo Finance."""
    return await _get_quote(symbol, exchange, str(current_user.id))


async def _get_quotes_bulk(symbols: str, exchange: str, user_id: str) -> list:
    """
    Internal helper: fetch quotes for multiple comma-separated symbols in parallel.
    No FastAPI Query() defaults — safe to call directly from other functions.
    """
    syms = [s.strip().upper() for s in symbols.split(",")]
    results = await asyncio.gather(
        *[_get_quote(s, exchange, user_id) for s in syms],
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, dict)]


@router.get("/quotes")
async def get_quotes(
    symbols: str = Query(..., description="Comma-separated symbols"),
    exchange: str = Query("NSE"),
    current_user: User = Depends(get_current_user),
):
    """Get quotes for multiple symbols in parallel."""
    return await _get_quotes_bulk(symbols, exchange, str(current_user.id))


# Interval and range mapping for Yahoo Finance v8 API
YF_INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "1d": "1d", "1w": "1wk",
}
YF_RANGE_MAP = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
    "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y",
    "10y": "10y", "ytd": "ytd", "max": "max",
}


def _fetch_candles_sync(yf_sym: str, interval: str, period: str) -> list:
    """
    Fetch historical candle data from Yahoo Finance v8 REST API.
    Replaces yfinance.download() which has reliability issues.
    """
    yf_iv = YF_INTERVAL_MAP.get(interval, "1d")
    yf_range = YF_RANGE_MAP.get(period, "1y")
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{YF_BASE}/{yf_sym}?interval={yf_iv}&range={yf_range}",
                headers=YF_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quotes = result["indicators"]["quote"][0]

        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        volumes = quotes.get("volume", [])

        candles = []
        for i, ts in enumerate(timestamps):
            if i >= len(opens) or opens[i] is None:
                continue
            candles.append({
                "time": int(ts),
                "open": round(float(opens[i]), 2),
                "high": round(float(highs[i]) if i < len(highs) and highs[i] is not None else opens[i], 2),
                "low": round(float(lows[i]) if i < len(lows) and lows[i] is not None else opens[i], 2),
                "close": round(float(closes[i]) if i < len(closes) and closes[i] is not None else opens[i], 2),
                "volume": int(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0,
            })

        return sorted(candles, key=lambda x: x["time"])
    except Exception as e:
        logger.error(f"Candles fetch failed for {yf_sym}: {e}")
        return []


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: str = Query("1d"),
    period: str = Query("1y"),
    exchange: str = Query("NSE"),
    current_user: User = Depends(get_current_user),
):
    """
    Get historical candle data.
    - Uses broker when connected (for intraday intervals)
    - Falls back to Yahoo Finance v8 API
    """
    sym = symbol.upper()

    # Try broker sources for intraday data when connected
    if interval in ("1m", "5m", "15m", "30m", "1h"):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        period_days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5y": 1825}
        days = period_days.get(period, 30)
        from_date = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
        to_date = now.strftime("%Y-%m-%d %H:%M")

        # Try Angel One first
        angel_session = await get_angel_session(str(current_user.id))
        if angel_session:
            angel_data = await get_market_candles_angel(
                str(current_user.id), sym, exchange, interval, from_date, to_date
            )
            if angel_data:
                return angel_data

        # Try Zerodha second
        zerodha_session = await get_zerodha_session(str(current_user.id))
        if zerodha_session:
            zerodha_data = await get_market_candles_zerodha(
                str(current_user.id), sym, exchange, interval, from_date, to_date
            )
            if zerodha_data:
                return zerodha_data

    # Fallback: Yahoo Finance v8 API
    key = f"candles:{exchange}:{sym}:{interval}:{period}"
    cached = await redis_get(key)
    if cached:
        return cached
    yf_sym = NSE_TO_YF.get(sym, sym + ".NS")
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_candles_sync, yf_sym, interval, period)
    ttl = 5 if interval in ("1m", "5m") else 60
    if data:
        await redis_set(key, data, ttl=ttl)
    return data


@router.get("/search")
async def search_symbols(q: str = Query(..., min_length=1), exchange: str = Query("NSE")):
    query = q.upper()
    return [i for i in _INSTRUMENTS if query in i["symbol"] or query in i["name"].upper()][:10]


@router.get("/status")
async def market_status():
    now = datetime.now()
    weekday = now.weekday()
    open_t = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open = weekday < 5 and open_t <= now <= close_t
    return {
        "is_open": is_open,
        "status": "Open" if is_open else "Closed",
        "exchange": "NSE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/indices")
async def get_indices(current_user: User = Depends(get_current_user)):
    """Get Nifty 50, Bank Nifty, and Sensex quotes."""
    return await _get_quotes_bulk("NIFTY50,BANKNIFTY,SENSEX", "NSE", str(current_user.id))


@router.websocket("/ws")
async def market_ws(websocket: WebSocket):
    await market_ws_endpoint(websocket)




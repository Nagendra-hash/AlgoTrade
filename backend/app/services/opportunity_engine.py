"""
Opportunity Engine — composes "Trading Opportunities" rows from real data:
  • Stock screener (technical scores: momentum, trend, mean reversion, RSI, MACD)
  • News sentiment (per-symbol news scoring)
  • Live quote (LTP, %change, volume, 52W H/L from Yahoo Finance v8)

Holdings data (promoter / FII / DII / market cap / sector) — TODO: wire to a real
fundamentals provider; until then, the API explicitly returns `null` for these
fields and the UI displays "—" rather than fake numbers.

Path: backend/app/services/opportunity_engine.py
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.services.stock_screener import stock_screener, NSE_TO_YF, SCREENING_UNIVERSE
from app.services.news_service import news_service, SECTOR_MAP
from app.services.sentiment_service import sentiment_service
from app.api.v1.market import _fetch_quote_sync, YF_BASE, YF_HEADERS  # reuse Yahoo helper

logger = logging.getLogger(__name__)


COMPANY_NAMES = {
    "RELIANCE":   "Reliance Industries",        "TCS":        "Tata Consultancy Services",
    "INFY":       "Infosys",                    "HDFCBANK":   "HDFC Bank",
    "ICICIBANK":  "ICICI Bank",                 "SBIN":       "State Bank of India",
    "WIPRO":      "Wipro",                      "BAJFINANCE": "Bajaj Finance",
    "TATAMOTORS": "Tata Motors",                "HINDUNILVR": "Hindustan Unilever",
    "MARUTI":     "Maruti Suzuki",              "SUNPHARMA":  "Sun Pharmaceutical",
    "BHARTIARTL": "Bharti Airtel",              "ASIANPAINT": "Asian Paints",
    "KOTAKBANK":  "Kotak Mahindra Bank",        "LT":         "Larsen & Toubro",
    "AXISBANK":   "Axis Bank",                  "ITC":        "ITC Ltd",
    "ADANIENT":   "Adani Enterprises",          "TITAN":      "Titan Company",
    "ULTRACEMCO": "UltraTech Cement",           "ONGC":       "Oil & Natural Gas",
    "NTPC":       "NTPC Ltd",                   "POWERGRID":  "Power Grid Corporation",
    "TATACONSUM": "Tata Consumer Products",     "TECHM":      "Tech Mahindra",
    "HCLTECH":    "HCL Technologies",           "JSWSTEEL":   "JSW Steel",
    "TATASTEEL":  "Tata Steel",                 "BAJAJFINSV": "Bajaj Finserv",
    "HDFCLIFE":   "HDFC Life Insurance",        "SBILIFE":    "SBI Life Insurance",
    "INDUSINDBK": "IndusInd Bank",              "GRASIM":     "Grasim Industries",
    "COALINDIA":  "Coal India",                 "BPCL":       "BPCL",
    "BRITANNIA":  "Britannia Industries",       "CIPLA":      "Cipla",
    "DRREDDY":    "Dr. Reddy's Laboratories",   "DIVISLAB":   "Divi's Laboratories",
    "EICHERMOT":  "Eicher Motors",              "HEROMOTOCO": "Hero MotoCorp",
    "M&M":        "Mahindra & Mahindra",        "NESTLEIND":  "Nestlé India",
    "APOLLOHOSP": "Apollo Hospitals",           "TRENT":      "Trent",
    "ADANIPORTS": "Adani Ports & SEZ",          "BEL":        "Bharat Electronics",
    "HAL":        "Hindustan Aeronautics",      "IRCTC":      "IRCTC",
}


def _fetch_52w_sync(yf_symbol: str) -> tuple[Optional[float], Optional[float]]:
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{YF_BASE}/{yf_symbol}?interval=1d&range=1y", headers=YF_HEADERS)
            r.raise_for_status()
            data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        return (
            float(meta.get("fiftyTwoWeekHigh") or 0) or None,
            float(meta.get("fiftyTwoWeekLow") or 0) or None,
        )
    except Exception:
        return None, None


def _risk_level(rsi: Optional[float], change_pct: float) -> str:
    if rsi is None:
        return "moderate"
    if rsi > 75 or abs(change_pct) > 6:
        return "high"
    if rsi < 25 or abs(change_pct) > 3:
        return "elevated"
    return "moderate" if 40 < rsi < 65 else "low"


def _recommended_action(composite: float, sentiment_score: int) -> str:
    blended = composite + (sentiment_score / 2)
    if blended >= 75:
        return "Buy"
    if blended >= 55:
        return "Watch"
    if blended <= 35:
        return "Avoid"
    return "Watch"


def _bullish_bearish_split(sent_score: int) -> tuple[int, int]:
    # convert [-100..100] → bullish/bearish 0..100 components
    if sent_score >= 0:
        return min(100, 50 + int(sent_score / 2)), max(0, 50 - int(sent_score / 2))
    return max(0, 50 + int(sent_score / 2)), min(100, 50 - int(sent_score / 2))


async def build_opportunities(limit: int = 25, db=None) -> dict:
    """
    Returns a dict { generated_at, total_universe, items: [...] } where items are
    Trading Opportunity rows in the exact order requested by the UI table.
    """
    # 1. Run screener — produces composite/momentum/trend/RSI/MACD for the whole universe.
    screened = await stock_screener.screen_stocks(criteria={"strategy_type": "momentum"}, limit=len(SCREENING_UNIVERSE))
    if not screened:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_universe": 0,
            "items": [],
            "no_live_data": True,
        }

    symbols = [s["symbol"] for s in screened][:limit * 2]  # over-fetch then trim by score

    # 2. Bulk sentiment via existing service (uses real news + Emergent LLM/rule fallback)
    sentiments = await sentiment_service.get_bulk(symbols, db=db)
    sentiment_map = {s["symbol"]: s for s in sentiments if "score" in s}

    # 3. 52W range — fetched in parallel via thread executor
    loop = asyncio.get_event_loop()
    yf_syms = [NSE_TO_YF.get(s, s + ".NS") for s in symbols]

    async def _fetch_52w(sym, yf_sym):
        hi, lo = await loop.run_in_executor(None, _fetch_52w_sync, yf_sym)
        return sym, hi, lo

    range_results = await asyncio.gather(*[_fetch_52w(s, y) for s, y in zip(symbols, yf_syms)])
    range_map = {sym: (hi, lo) for sym, hi, lo in range_results}

    items = []
    for s in screened:
        sym = s["symbol"]
        if sym not in symbols:
            continue
        sent = sentiment_map.get(sym, {})
        sent_score = int(sent.get("score", 0))
        bullish, bearish = _bullish_bearish_split(sent_score)
        composite = float(s.get("composite_score") or 0)

        confidence = round(min(100, max(5, composite * 0.6 + abs(sent_score) * 0.4)), 1)
        action = _recommended_action(composite, sent_score)
        hi52, lo52 = range_map.get(sym, (None, None))

        items.append({
            "symbol":         sym,
            "company":        COMPANY_NAMES.get(sym, sym),
            "ltp":            s.get("ltp"),
            "change_pct":     s.get("change_pct"),
            "volume":         s.get("avg_volume"),
            "news_sentiment": sent.get("label", "neutral"),
            "sentiment_score": sent_score,
            "bullish_score":  bullish,
            "bearish_score":  bearish,
            # Fundamentals not yet wired to a real data source — explicit null = "—" in UI
            "promoter_holding": None,
            "fii_holding":      None,
            "dii_holding":      None,
            "market_cap":       None,
            "sector":           SECTOR_MAP.get(sym, "Other"),
            "rsi":              s.get("rsi"),
            "macd":             s.get("macd"),
            "macd_signal":      s.get("macd_signal"),
            "macd_state":       "bullish" if (s.get("macd") or 0) > (s.get("macd_signal") or 0) else "bearish",
            "high_52w":         round(hi52, 2) if hi52 else None,
            "low_52w":          round(lo52, 2) if lo52 else None,
            "risk_level":       _risk_level(s.get("rsi"), s.get("change_pct") or 0),
            "confidence":       confidence,
            "recommended_action": action,
            "composite_score":  round(composite, 1),
            "ai_summary":       None,   # populated lazily below
        })

    # Rank by confidence desc, then composite
    items.sort(key=lambda x: (x["confidence"], x["composite_score"]), reverse=True)
    items = items[:limit]

    # Quick rule-based AI summary per row (one line) — keeps response fast
    for it in items:
        bias = "bullish" if it["bullish_score"] >= it["bearish_score"] else "bearish"
        macd_word = "MACD crossover up" if it["macd_state"] == "bullish" else "MACD pressure"
        rsi = it["rsi"]
        rsi_word = (
            f"RSI {rsi:.0f} (overbought)" if rsi and rsi > 70 else
            f"RSI {rsi:.0f} (oversold)" if rsi and rsi < 30 else
            f"RSI {rsi:.0f}" if rsi else "no RSI data"
        )
        it["ai_summary"] = (
            f"{it['sector']} · {bias} bias from news ({it['sentiment_score']:+d}). "
            f"{macd_word}, {rsi_word}. Action: {it['recommended_action'].lower()}."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_universe": len(screened),
        "items": items,
        "no_live_data": False,
    }

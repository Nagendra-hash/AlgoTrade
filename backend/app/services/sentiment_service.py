"""
AI Sentiment Analysis — Claude → OpenAI → Rule-based fallback.
Path: backend/app/services/sentiment_service.py
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_get, redis_set
from app.models.alert import SentimentCache
from app.services.news_service import news_service

logger = logging.getLogger(__name__)

CACHE_TTL = settings.SENTIMENT_CACHE_MINUTES * 60

SYSTEM_PROMPT = """You are an expert financial analyst specializing in Indian stock markets (NSE/BSE).

Analyze the provided news headlines and return ONLY a valid JSON object with no extra text:

{
  "score": <integer -100 to +100>,
  "label": "<bullish|bearish|neutral>",
  "confidence": <integer 0 to 100>,
  "explanation": "<2-3 sentences explaining the sentiment>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"]
}

Rules:
- score > 20 = bullish, score < -20 = bearish, else neutral
- confidence reflects signal strength
- explanation must be clear and actionable
- Return ONLY the JSON, no markdown, no preamble"""

BULLISH_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "beat", "profit", "growth", "record",
    "buyback", "dividend", "upgrade", "outperform", "strong", "robust", "positive",
}
BEARISH_WORDS = {
    "fall", "drop", "decline", "loss", "miss", "weak", "downgrade", "underperform",
    "fraud", "probe", "investigation", "lawsuit", "fine", "default", "crash", "plunge",
}


def _rule_based(symbol: str, headlines: List[str]) -> dict:
    if not headlines:
        return {
            "score": 0, "label": "neutral", "confidence": 25,
            "explanation": f"No recent news found for {symbol}.",
            "key_factors": [],
        }
    scores = []
    for h in headlines:
        words = set(h.lower().split())
        bull = len(words & BULLISH_WORDS)
        bear = len(words & BEARISH_WORDS)
        total = bull + bear
        scores.append((bull - bear) / total if total else 0)

    avg = sum(scores) / len(scores)
    final = int(avg * 100)
    conf = min(40 + len(headlines) * 4, 72)
    label = "bullish" if final > 20 else "bearish" if final < -20 else "neutral"
    return {
        "score": final,
        "label": label,
        "confidence": conf,
        "explanation": f"Rule-based analysis of {len(headlines)} headlines for {symbol} shows {label} sentiment.",
        "key_factors": headlines[:3],
    }


async def _emergent_llm(symbol: str, headlines: List[str]) -> Optional[dict]:
    """Run sentiment analysis via Emergent Universal LLM key (Claude Sonnet)."""
    emergent_key = settings.EMERGENT_LLM_KEY or os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        prompt = f"Stock: {symbol}\n\nHeadlines:\n" + "\n".join(f"- {h}" for h in headlines[:10])
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"sentiment-{symbol}-{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-haiku-4-5-20251001")
        response = await chat.send_message(UserMessage(text=prompt))
        raw = (response or "").strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Emergent LLM sentiment {symbol}: {e}")
        return None


async def _openai_direct(symbol: str, headlines: List[str]) -> Optional[dict]:
    """Sentiment via direct OpenAI Chat Completions (fallback when no Emergent key)."""
    api_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        prompt = f"Stock: {symbol}\n\nHeadlines:\n" + "\n".join(f"- {h}" for h in headlines[:10])
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=400,
        )
        raw = (resp.choices[0].message.content or "").strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"OpenAI direct sentiment {symbol}: {e}")
        return None


class SentimentService:
    async def get_sentiment(
        self,
        symbol: str,
        exchange: str = "NSE",
        db: Optional[AsyncSession] = None,
        force_refresh: bool = False,
    ) -> dict:
        symbol = symbol.upper()
        cache_key = f"sentiment:{exchange}:{symbol}"

        if not force_refresh:
            cached = await redis_get(cache_key)
            if cached:
                return cached

        if db and not force_refresh:
            result = await db.execute(
                select(SentimentCache).where(SentimentCache.symbol == symbol)
            )
            sc = result.scalar_one_or_none()
            if sc and not sc.is_stale and sc.expires_at > datetime.now(timezone.utc):
                data = self._to_dict(sc)
                await redis_set(cache_key, data, ttl=CACHE_TTL)
                return data

        news_data = await news_service.get_news(symbols=[symbol], per_page=15)
        headlines = [a["title"] for a in news_data.get("articles", []) if a.get("title")]

        analysis = (
            await _emergent_llm(symbol, headlines)
            or await _openai_direct(symbol, headlines)
            or _rule_based(symbol, headlines)
        )

        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=settings.SENTIMENT_CACHE_MINUTES)

        data = {
            "symbol": symbol,
            "exchange": exchange,
            "score": int(analysis.get("score", 0)),
            "label": analysis.get("label", "neutral"),
            "confidence": int(analysis.get("confidence", 50)),
            "explanation": analysis.get("explanation", ""),
            "headlines": headlines[:5],
            "news_count": len(headlines),
            "cached_at": now.isoformat(),
            "is_stale": False,
        }

        await redis_set(cache_key, data, ttl=CACHE_TTL)

        if db:
            result = await db.execute(
                select(SentimentCache).where(SentimentCache.symbol == symbol)
            )
            sc = result.scalar_one_or_none()
            if sc:
                sc.score = data["score"]
                sc.label = data["label"]
                sc.confidence = data["confidence"]
                sc.explanation = data["explanation"]
                sc.headlines = headlines[:5]
                sc.news_count = len(headlines)
                sc.cached_at = now
                sc.expires_at = expires
                sc.is_stale = False
            else:
                db.add(SentimentCache(
                    symbol=symbol, exchange=exchange,
                    score=data["score"], label=data["label"],
                    confidence=data["confidence"], explanation=data["explanation"],
                    headlines=headlines[:5], news_count=len(headlines),
                    cached_at=now, expires_at=expires,
                ))
            await db.flush()

        return data

    async def get_bulk(
        self, symbols: List[str], exchange: str = "NSE", db: Optional[AsyncSession] = None
    ) -> List[dict]:
        import asyncio
        tasks = [self.get_sentiment(s, exchange, db) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            r if isinstance(r, dict) else {"symbol": symbols[i], "error": str(r), "score": 0, "label": "neutral"}
            for i, r in enumerate(results)
        ]

    async def get_market_summary(
        self, symbols: List[str], db: Optional[AsyncSession] = None
    ) -> dict:
        sentiments = await self.get_bulk(symbols, db=db)
        valid = [s for s in sentiments if "score" in s and "error" not in s]

        if not valid:
            return {
                "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
                "total": 0, "avg_score": 0.0,
                "top_bullish": None, "top_bearish": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        bullish = [s for s in valid if s["label"] == "bullish"]
        bearish = [s for s in valid if s["label"] == "bearish"]
        neutral = [s for s in valid if s["label"] == "neutral"]
        avg_score = round(sum(s["score"] for s in valid) / len(valid), 1)

        return {
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "total": len(valid),
            "avg_score": avg_score,
            "top_bullish": max(bullish, key=lambda x: x["score"]) if bullish else None,
            "top_bearish": min(bearish, key=lambda x: x["score"]) if bearish else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _to_dict(self, sc: SentimentCache) -> dict:
        return {
            "symbol": sc.symbol, "exchange": sc.exchange,
            "score": sc.score, "label": sc.label,
            "confidence": sc.confidence, "explanation": sc.explanation,
            "headlines": sc.headlines or [], "news_count": sc.news_count,
            "cached_at": sc.cached_at.isoformat() if sc.cached_at else None,
            "is_stale": sc.is_stale,
        }


sentiment_service = SentimentService()

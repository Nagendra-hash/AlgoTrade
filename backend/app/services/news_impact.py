"""
News Impact Analyzer (Phase 5 + P1 AI upgrade)

For every recent news article, returns:
  • affected_stocks      : symbols extracted from headline + summary
  • affected_sectors     : sectors derived from SECTOR_MAP
  • impact_direction     : "positive" | "negative" | "neutral"
  • confidence           : 0..100 (AI confidence when available, else rule-based)
  • opportunity_summary  : one-line trade hypothesis (AI when available)
  • ai_powered           : True when the AI router produced this row, False for rule-based

AI flow:
  1. Run the cheap rule-based analyzer on every article (always present).
  2. For the top `ai_top_n` articles (by absolute sentiment), call the user's
     primary AI provider via `ai_router.chat` asking for a strict JSON envelope.
  3. Cache the AI envelope per article id in Redis for 30 minutes — so repeat
     calls don't re-pay the LLM bill.

Path: backend/app/services/news_impact.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_get, redis_set
from app.services.news_service import (
    news_service,
    _detect_symbols,
    _classify,
    _score,
    SECTOR_MAP,
)
from app.services.ai_router import chat as ai_chat

logger = logging.getLogger(__name__)


AI_CACHE_TTL = 30 * 60  # 30 min per article
AI_DEFAULT_TOP_N = 8

AI_SYSTEM_PROMPT = (
    "You are a senior Indian-market analyst. For each news article you are given, "
    "respond with ONLY a single JSON object (no prose, no markdown fences) using "
    "this exact schema:\n"
    "{\n"
    '  "impact_direction": "positive" | "negative" | "neutral",\n'
    '  "confidence": <integer 0-100>,\n'
    '  "affected_stocks": ["<NSE_TICKER>", ...]   // tickers only, no .NS suffix\n'
    '  "affected_sectors": ["<sector>", ...]      // e.g. "Banking & Finance", "IT", "Pharma"\n'
    '  "opportunity_summary": "<one tight sentence on the trade hypothesis>"\n'
    "}\n"
    "If the article is irrelevant to Indian listed equities, set impact_direction to "
    '"neutral", confidence to a low number, and leave affected_stocks empty.'
)


def _impact_direction(score: float) -> str:
    if score > 0.15:
        return "positive"
    if score < -0.15:
        return "negative"
    return "neutral"


def _rule_based(a: dict) -> dict:
    title = a.get("title", "") or ""
    summary = a.get("summary", "") or ""
    symbols = a.get("symbols") or _detect_symbols(title + " " + summary)
    sectors = sorted({SECTOR_MAP.get(s, "Other") for s in symbols})
    score = a.get("sentiment_score")
    conf = a.get("confidence")
    if score is None or conf is None:
        score, conf = _score(title, summary)
    direction = _impact_direction(score)
    confidence_pct = int(round(conf * 100))

    if symbols:
        verb = (
            "could benefit" if direction == "positive"
            else "may face pressure on" if direction == "negative"
            else "are watching"
        )
        opp = f"{', '.join(symbols[:4])} {verb} this development."
    elif sectors:
        opp = f"{', '.join(sectors[:3])} sector exposure to this story."
    else:
        opp = "No clear single-stock exposure identified."

    return {
        "id":                  a.get("id"),
        "headline":            title,
        "source":              a.get("source"),
        "url":                 a.get("url"),
        "published_at":        a.get("published_at"),
        "category":            a.get("category") or _classify(title, summary),
        "impact_direction":    direction,
        "confidence":          confidence_pct,
        "sentiment_score":     round(score, 3),
        "affected_stocks":     symbols[:8],
        "affected_sectors":    sectors[:5],
        "opportunity_summary": opp,
        "ai_powered":          False,
    }


def _coerce_ai_json(raw: str) -> Optional[dict]:
    """Strip markdown fences / preambles and parse a JSON object from an LLM response."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        # ```json … ``` or ``` … ```
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Find first {...} block
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def _ai_one(db: AsyncSession, user_id: str, article: dict, base: dict) -> dict:
    """
    Ask the user's primary AI for a structured impact envelope.
    Caches by article id. On any failure, return the rule-based base unchanged.
    """
    aid = article.get("id")
    cache_key = f"news-impact-ai:{aid}"
    cached = await redis_get(cache_key)
    if cached:
        return {**base, **cached, "ai_powered": True}

    prompt = (
        f"Article source: {article.get('source')}\n"
        f"Headline: {article.get('title')}\n"
        f"Summary: {article.get('summary')}\n\n"
        f"NSE-listed names already detected by a simple rule scanner: "
        f"{base['affected_stocks'] or 'none'}.\n"
        f"Return the JSON envelope now."
    )
    try:
        result = await ai_chat(db, user_id, prompt, system_prompt=AI_SYSTEM_PROMPT)
        parsed = _coerce_ai_json(result.get("response", ""))
        if not parsed:
            return base
        # Sanitise & merge
        dir_val = str(parsed.get("impact_direction", base["impact_direction"])).lower()
        if dir_val not in ("positive", "negative", "neutral"):
            dir_val = base["impact_direction"]
        conf = parsed.get("confidence")
        try:
            conf = max(0, min(100, int(conf)))
        except Exception:
            conf = base["confidence"]
        stocks = parsed.get("affected_stocks") or []
        sectors = parsed.get("affected_sectors") or []
        opp = (parsed.get("opportunity_summary") or base["opportunity_summary"]).strip()

        envelope = {
            "impact_direction":    dir_val,
            "confidence":          conf,
            "affected_stocks":     [str(s).upper().replace(".NS", "")[:20] for s in stocks][:8] or base["affected_stocks"],
            "affected_sectors":    [str(s)[:48] for s in sectors][:5] or base["affected_sectors"],
            "opportunity_summary": opp[:280],
            "ai_provider":         result.get("provider"),
            "ai_model":            result.get("model"),
        }
        await redis_set(cache_key, envelope, ttl=AI_CACHE_TTL)
        return {**base, **envelope, "ai_powered": True}
    except Exception as e:
        logger.info(f"AI impact analysis fell back to rule-based for {aid}: {e}")
        return base


async def analyze_recent(
    limit: int = 30,
    sources: Optional[List[str]] = None,
    *,
    db: Optional[AsyncSession] = None,
    user_id: Optional[str] = None,
    ai_top_n: int = AI_DEFAULT_TOP_N,
) -> dict:
    """
    Run impact analysis on the most recent news.
    When (db, user_id) are supplied, the top `ai_top_n` articles by absolute sentiment
    are upgraded with an AI-driven envelope through the user's primary AI provider.
    """
    feed = await news_service.get_news(sources=sources, per_page=limit)
    articles = feed.get("articles", [])
    base_items = [_rule_based(a) for a in articles]

    # Decide which articles to send to the LLM
    if db is not None and user_id and ai_top_n > 0 and base_items:
        # Sort by |sentiment_score| desc to spend AI budget on the most-charged news
        ranked_indexes = sorted(
            range(len(base_items)),
            key=lambda i: abs(base_items[i]["sentiment_score"]),
            reverse=True,
        )[:ai_top_n]
        chosen_articles = [articles[i] for i in ranked_indexes]
        chosen_bases = [base_items[i] for i in ranked_indexes]
        ai_results = await asyncio.gather(
            *[_ai_one(db, user_id, art, base) for art, base in zip(chosen_articles, chosen_bases)],
            return_exceptions=True,
        )
        for i, r in zip(ranked_indexes, ai_results):
            if isinstance(r, dict):
                base_items[i] = r

    # Rollup — most-mentioned stocks/sectors
    stock_counter: dict[str, int] = {}
    sector_counter: dict[str, int] = {}
    for it in base_items:
        for s in it["affected_stocks"]:
            stock_counter[s] = stock_counter.get(s, 0) + 1
        for sec in it["affected_sectors"]:
            sector_counter[sec] = sector_counter.get(sec, 0) + 1

    top_stocks = sorted(stock_counter.items(), key=lambda x: -x[1])[:10]
    top_sectors = sorted(sector_counter.items(), key=lambda x: -x[1])[:6]

    ai_count = sum(1 for it in base_items if it.get("ai_powered"))

    return {
        "articles_analyzed":   len(base_items),
        "ai_analyzed":         ai_count,
        "items":               base_items,
        "top_stocks":          [{"symbol": s, "mentions": c} for s, c in top_stocks],
        "top_sectors":         [{"sector": s, "mentions": c} for s, c in top_sectors],
        "no_live_data":        len(base_items) == 0,
    }

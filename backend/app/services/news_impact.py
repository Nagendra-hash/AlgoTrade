"""
News Impact Analyzer (Phase 5)
Takes any recent news article (or the latest feed) and returns:
  • affected_stocks      : symbols extracted from headline + summary
  • affected_sectors     : sectors derived from SECTOR_MAP
  • impact_direction     : "positive" | "negative" | "neutral"
  • confidence           : 0..100 (derived from sentiment confidence × source strength)
  • opportunity_summary  : one-line trade hypothesis

Re-uses the existing rule-based scorer in news_service.

Path: backend/app/services/news_impact.py
"""
from typing import List, Optional

from app.services.news_service import (
    news_service,
    _detect_symbols,
    _classify,
    _score,
    SECTOR_MAP,
)


def _impact_direction(score: float) -> str:
    if score > 0.15:
        return "positive"
    if score < -0.15:
        return "negative"
    return "neutral"


def _analyze_article(a: dict) -> dict:
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
        "id":                a.get("id"),
        "headline":          title,
        "source":            a.get("source"),
        "url":               a.get("url"),
        "published_at":      a.get("published_at"),
        "category":          a.get("category") or _classify(title, summary),
        "impact_direction":  direction,
        "confidence":        confidence_pct,
        "sentiment_score":   round(score, 3),
        "affected_stocks":   symbols[:8],
        "affected_sectors":  sectors[:5],
        "opportunity_summary": opp,
    }


async def analyze_recent(limit: int = 30, sources: Optional[List[str]] = None) -> dict:
    """Run impact analysis on the most recent news (already fetched & cached by news_service)."""
    feed = await news_service.get_news(sources=sources, per_page=limit)
    items = [_analyze_article(a) for a in feed.get("articles", [])]

    # Group rollup — most-mentioned stocks/sectors across the batch
    stock_counter: dict[str, int] = {}
    sector_counter: dict[str, int] = {}
    for it in items:
        for s in it["affected_stocks"]:
            stock_counter[s] = stock_counter.get(s, 0) + 1
        for sec in it["affected_sectors"]:
            sector_counter[sec] = sector_counter.get(sec, 0) + 1

    top_stocks = sorted(stock_counter.items(), key=lambda x: -x[1])[:10]
    top_sectors = sorted(sector_counter.items(), key=lambda x: -x[1])[:6]

    return {
        "articles_analyzed": len(items),
        "items":             items,
        "top_stocks":        [{"symbol": s, "mentions": c} for s, c in top_stocks],
        "top_sectors":       [{"sector": s, "mentions": c} for s, c in top_sectors],
        "no_live_data":      len(items) == 0,
    }

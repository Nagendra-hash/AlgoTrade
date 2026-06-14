"""
Tests for news-driven stock screener — sector grouping logic.
Path: backend/tests/test_news_screener.py

Tests the get_news_screener_recommendations() method on the NewsService
singleton, mocking get_news and stock_screener.screen_stocks to control
inputs and verify sector grouping, aggregation, sorting, and edge cases.

Requires app.services.news_service.news_service (singleton, no auth/DB needed).
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.news_service import news_service


# ── Fixtures ─────────────────────────────────────────────────────────

_MOCK_ARTICLES = [
    # Energy sector articles
    {
        "id": "a1", "title": "Reliance Q2 profit surges 18%",
        "summary": "Record revenue from retail and telecom arms",
        "source": "Moneycontrol", "symbols": ["RELIANCE"],
        "category": "bullish", "sentiment_score": 0.8, "confidence": 0.9,
        "published_at": "2025-06-14T10:00:00+00:00",
        "url": "https://example.com/1", "ai_summary": None, "image_url": None,
    },
    {
        "id": "a2", "title": "ONGC discovers new oil field",
        "summary": "Expected to boost domestic production by 15%",
        "source": "Economic Times", "symbols": ["ONGC"],
        "category": "bullish", "sentiment_score": 0.6, "confidence": 0.85,
        "published_at": "2025-06-14T09:30:00+00:00",
        "url": "https://example.com/2", "ai_summary": None, "image_url": None,
    },
    {
        "id": "a3", "title": "BPCL rating upgraded to buy",
        "summary": "Strong refining margins driving profitability",
        "source": "Moneycontrol", "symbols": ["BPCL"],
        "category": "bullish", "sentiment_score": 0.5, "confidence": 0.8,
        "published_at": "2025-06-14T08:00:00+00:00",
        "url": "https://example.com/3", "ai_summary": None, "image_url": None,
    },
    # Banking & Finance sector articles
    {
        "id": "a4", "title": "HDFC Bank net profit rises 20%",
        "summary": "Strong loan growth across retail and corporate",
        "source": "Economic Times", "symbols": ["HDFCBANK"],
        "category": "bullish", "sentiment_score": 0.7, "confidence": 0.88,
        "published_at": "2025-06-14T07:00:00+00:00",
        "url": "https://example.com/4", "ai_summary": None, "image_url": None,
    },
    {
        "id": "a5", "title": "ICICI Bank expands branch network",
        "summary": "Adding 200 new branches in Tier-2 cities",
        "source": "Moneycontrol", "symbols": ["ICICIBANK"],
        "category": "bullish", "sentiment_score": 0.4, "confidence": 0.75,
        "published_at": "2025-06-13T14:00:00+00:00",
        "url": "https://example.com/5", "ai_summary": None, "image_url": None,
    },
    # IT sector articles
    {
        "id": "a6", "title": "TCS wins $500M contract",
        "summary": "Multi-year deal with European banking giant",
        "source": "Moneycontrol", "symbols": ["TCS"],
        "category": "bullish", "sentiment_score": 0.9, "confidence": 0.95,
        "published_at": "2025-06-14T06:00:00+00:00",
        "url": "https://example.com/6", "ai_summary": None, "image_url": None,
    },
    {
        "id": "a7", "title": "Infosys shares fall on guidance miss",
        "summary": "Revenue guidance cut due to global slowdown",
        "source": "Economic Times", "symbols": ["INFY"],
        "category": "bearish", "sentiment_score": -0.5, "confidence": 0.82,
        "published_at": "2025-06-14T05:00:00+00:00",
        "url": "https://example.com/7", "ai_summary": None, "image_url": None,
    },
    # Defense sector article
    {
        "id": "a8", "title": "BEL bags ₹10,000 crore order",
        "summary": "Largest ever order from Ministry of Defence",
        "source": "Economic Times", "symbols": ["BEL"],
        "category": "bullish", "sentiment_score": 0.85, "confidence": 0.92,
        "published_at": "2025-06-14T04:00:00+00:00",
        "url": "https://example.com/8", "ai_summary": None, "image_url": None,
    },
    # Unknown symbol (not in SECTOR_MAP → "Other")
    {
        "id": "a9", "title": "XYZ Corp announces buyback",
        "summary": "Share buyback of ₹500 crore",
        "source": "Moneycontrol", "symbols": ["XYZCORP"],
        "category": "bullish", "sentiment_score": 0.3, "confidence": 0.7,
        "published_at": "2025-06-14T03:00:00+00:00",
        "url": "https://example.com/9", "ai_summary": None, "image_url": None,
    },
]

_MOCK_SCREENER_RESULTS = [
    {"symbol": "RELIANCE", "composite_score": 85, "ltp": 2510.0, "change_pct": 1.2,
     "rsi": 62, "trend_up": True, "momentum_score": 78, "vol_ratio": 1.5},
    {"symbol": "ONGC", "composite_score": 72, "ltp": 180.0, "change_pct": 0.8,
     "rsi": 55, "trend_up": True, "momentum_score": 68, "vol_ratio": 1.2},
    {"symbol": "BPCL", "composite_score": 45, "ltp": 320.0, "change_pct": -0.5,
     "rsi": 42, "trend_up": False, "momentum_score": 35, "vol_ratio": 0.8},
    {"symbol": "HDFCBANK", "composite_score": 91, "ltp": 1620.0, "change_pct": 2.1,
     "rsi": 68, "trend_up": True, "momentum_score": 82, "vol_ratio": 1.8},
    {"symbol": "ICICIBANK", "composite_score": 78, "ltp": 1080.0, "change_pct": 1.5,
     "rsi": 60, "trend_up": True, "momentum_score": 72, "vol_ratio": 1.3},
    {"symbol": "TCS", "composite_score": 95, "ltp": 3300.0, "change_pct": 2.5,
     "rsi": 70, "trend_up": True, "momentum_score": 90, "vol_ratio": 2.1},
    {"symbol": "INFY", "composite_score": 30, "ltp": 1480.0, "change_pct": -1.8,
     "rsi": 35, "trend_up": False, "momentum_score": 22, "vol_ratio": 0.6},
    {"symbol": "BEL", "composite_score": 88, "ltp": 480.0, "change_pct": 3.2,
     "rsi": 72, "trend_up": True, "momentum_score": 85, "vol_ratio": 2.5},
]


async def _mock_get_news(symbols=None, **kwargs):
    """Return controlled news data. Filters by symbol if provided."""
    articles = _MOCK_ARTICLES[:]
    if symbols:
        syms_upper = [s.upper() for s in symbols]
        articles = [a for a in articles if any(s in syms_upper for s in a.get("symbols", []))]
    return {"total": len(articles), "page": 1, "per_page": 50, "articles": articles}


async def _mock_screen_stocks(criteria=None, limit=10):
    """Return controlled screener data."""
    return _MOCK_SCREENER_RESULTS[:limit]


# ── Tests ───────────────────────────────────────────────────────────

class TestSectorGrouping:
    """Tests for the sector grouping logic in get_news_screener_recommendations."""

    @pytest.mark.asyncio
    async def test_sector_grouping_basic(self):
        """Symbols from 4 sectors (Energy, Banking, IT, Defense) should be grouped correctly."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        assert result["symbols_analyzed"] == 9
        assert result["news_count"] == 9

        sectors = result["sectors"]
        sector_names = {s["sector"] for s in sectors}
        assert "Energy" in sector_names
        assert "Banking & Finance" in sector_names
        assert "IT" in sector_names
        assert "Defense & Aerospace" in sector_names
        assert "Other" in sector_names

        # Verify specific sector contents
        energy = next(s for s in sectors if s["sector"] == "Energy")
        assert energy["count"] == 3       # RELIANCE, ONGC, BPCL
        assert energy["total_news"] == 3  # a1, a2, a3
        assert set(energy["symbols"]) == {"RELIANCE", "ONGC", "BPCL"}

        banking = next(s for s in sectors if s["sector"] == "Banking & Finance")
        assert banking["count"] == 2       # HDFCBANK, ICICIBANK
        assert banking["total_news"] == 2  # a4, a5

        it_sector = next(s for s in sectors if s["sector"] == "IT")
        assert it_sector["count"] == 2       # TCS, INFY
        assert it_sector["total_news"] == 2  # a6, a7

        defense = next(s for s in sectors if s["sector"] == "Defense & Aerospace")
        assert defense["count"] == 1       # BEL
        assert defense["total_news"] == 1  # a8

        other = next(s for s in sectors if s["sector"] == "Other")
        assert other["count"] == 1         # XYZCORP
        assert other["total_news"] == 1    # a9

    @pytest.mark.asyncio
    async def test_sector_avg_sentiment(self):
        """Sector avg_sentiment should be the mean of all recommendations' sentiment in that sector."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        sectors = {s["sector"]: s for s in result["sectors"]}

        # Energy: RELIANCE(0.8) + ONGC(0.6) + BPCL(0.5) = 1.9 / 3 = 0.633
        energy = sectors["Energy"]
        expected_avg = round((0.8 + 0.6 + 0.5) / 3, 3)
        assert energy["avg_sentiment"] == expected_avg, \
            f"Expected {expected_avg}, got {energy['avg_sentiment']}"

        # Banking: HDFCBANK(0.7) + ICICIBANK(0.4) = 1.1 / 2 = 0.55
        banking = sectors["Banking & Finance"]
        assert banking["avg_sentiment"] == 0.55

        # IT: TCS(0.9) + INFY(-0.5) = 0.4 / 2 = 0.2
        it_sector = sectors["IT"]
        assert it_sector["avg_sentiment"] == 0.2

    @pytest.mark.asyncio
    async def test_sector_sorting_by_total_news(self):
        """Sectors should be sorted by total_news descending."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        sectors = result["sectors"]
        for i in range(len(sectors) - 1):
            assert sectors[i]["total_news"] >= sectors[i + 1]["total_news"], \
                f"Sectors not sorted: {sectors[i]['sector']}({sectors[i]['total_news']}) < {sectors[i+1]['sector']}({sectors[i+1]['total_news']})"

    @pytest.mark.asyncio
    async def test_recommendations_sorted_by_combined_score(self):
        """Recommendations should be sorted by combined score descending."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        recs = result["recommendations"]
        assert len(recs) > 1

        for i in range(len(recs) - 1):
            # Combined score = min(news_count*10, 50) + max(avg_sentiment*100, 0) + screener_score
            def combined(r):
                news_score = min(r["news_count"] * 10, 50)
                sent_score = max(0, r["avg_sentiment"] * 100)
                scr = r.get("screener_score") or 0
                return news_score + sent_score + scr
            assert combined(recs[i]) >= combined(recs[i + 1]), \
                f"Recs not sorted: {recs[i]['symbol']}({combined(recs[i])}) < {recs[i+1]['symbol']}({combined(recs[i+1])})"

    @pytest.mark.asyncio
    async def test_top_stock_assignment(self):
        """Each sector's top_stock should be the first (highest-scored) recommendation in that sector."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        sectors = {s["sector"]: s for s in result["sectors"]}
        recs = result["recommendations"]

        for sector_name, sector_data in sectors.items():
            top_stock = sector_data["top_stock"]
            assert top_stock is not None, f"{sector_name} has no top_stock"

            # Find the first recommendation in this sector
            first_in_sector = next(
                (r for r in recs if r["sector"] == sector_name),
                None,
            )
            assert first_in_sector is not None, f"{sector_name} has no recommendations"
            assert first_in_sector["symbol"] == top_stock, \
                f"{sector_name}: expected top_stock {first_in_sector['symbol']}, got {top_stock}"

    @pytest.mark.asyncio
    async def test_recommendation_fields(self):
        """Each recommendation should have all expected fields populated."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        expected_fields = {
            "symbol", "sector", "news_count", "headlines",
            "avg_sentiment", "sources", "screener_score", "ltp",
            "change_pct", "rsi", "trend_up", "momentum_score", "volume_ratio",
        }

        for rec in result["recommendations"]:
            missing = expected_fields - set(rec.keys())
            assert not missing, f"{rec['symbol']} missing fields: {missing}"
            # Unknown symbols should have "Other" sector
            if rec["symbol"] == "XYZCORP":
                assert rec["sector"] == "Other", f"XYZCORP sector should be 'Other', got {rec['sector']}"
            else:
                assert rec["sector"] != "Other", f"{rec['symbol']} should not be 'Other' sector"

    @pytest.mark.asyncio
    async def test_headlines_truncated(self):
        """Each recommendation should have at most 3 headlines."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=10)

        for rec in result["recommendations"]:
            assert len(rec["headlines"]) <= 3, \
                f"{rec['symbol']} has {len(rec['headlines'])} headlines (max 3)"


class TestEmptyAndEdgeCases:
    """Tests for empty and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_empty_news(self):
        """When no news articles exist, return empty recommendations and sectors."""
        async def _empty_news(**kwargs):
            return {"total": 0, "page": 1, "per_page": 50, "articles": []}

        with patch.object(news_service, "get_news", side_effect=_empty_news):
            result = await news_service.get_news_screener_recommendations(limit=10)

        assert result["symbols_analyzed"] == 0
        assert result["news_count"] == 0
        assert result["sectors"] == {}
        assert result["recommendations"] == []

    @pytest.mark.asyncio
    async def test_no_mentioned_symbols(self):
        """Articles that mention no known symbols should result in empty recommendations."""
        articles = [{
            "id": "no-sym", "title": "Market rallies for fifth day",
            "summary": "Broad-based buying seen across sectors",
            "source": "Moneycontrol", "symbols": [],
            "category": "bullish", "sentiment_score": 0.5, "confidence": 0.8,
            "published_at": "2025-06-14T10:00:00+00:00",
            "url": "https://example.com/", "ai_summary": None, "image_url": None,
        }]

        async def _no_symbol_news(**kwargs):
            return {"total": 1, "page": 1, "per_page": 50, "articles": articles}

        with patch.object(news_service, "get_news", side_effect=_no_symbol_news):
            result = await news_service.get_news_screener_recommendations(limit=10)

        assert result["symbols_analyzed"] == 0
        assert result["news_count"] == 1
        assert result["recommendations"] == []

    @pytest.mark.asyncio
    async def test_screener_failure_graceful(self):
        """When stock screener fails, recommendations should still include news data without screener scores."""
        async def _screener_failure(**kwargs):
            raise Exception("API unavailable")

        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_screener_failure):
            result = await news_service.get_news_screener_recommendations(limit=10)

        # Should still have recommendations from news data
        assert result["symbols_analyzed"] > 0
        for rec in result["recommendations"]:
            assert rec["screener_score"] is None
            assert rec["ltp"] is None

    @pytest.mark.asyncio
    async def test_limit_truncates_recommendations(self):
        """limit parameter should cap the number of recommendations returned."""
        with patch.object(news_service, "get_news", side_effect=_mock_get_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks", side_effect=_mock_screen_stocks):
            result = await news_service.get_news_screener_recommendations(limit=3)

        assert len(result["recommendations"]) <= 3
        # Sectors should still contain all sectors (limit only affects recommendations)
        assert len(result["sectors"]) >= 4

    @pytest.mark.asyncio
    async def test_sector_aggregation_with_multiple_articles_same_symbol(self):
        """When a symbol appears in multiple articles, news_count aggregates correctly."""
        articles = [
            {
                "id": "m1", "title": "RELIANCE surges 5%",
                "summary": "Record high", "source": "Moneycontrol",
                "symbols": ["RELIANCE"], "category": "bullish",
                "sentiment_score": 0.8, "confidence": 0.9,
                "published_at": "2025-06-14T10:00:00+00:00",
                "url": "https://example.com/m1", "ai_summary": None, "image_url": None,
            },
            {
                "id": "m2", "title": "RELIANCE buyback approved",
                "summary": "Board approves ₹10,000 cr buyback",
                "source": "Economic Times", "symbols": ["RELIANCE"],
                "category": "bullish", "sentiment_score": 0.6, "confidence": 0.85,
                "published_at": "2025-06-14T09:00:00+00:00",
                "url": "https://example.com/m2", "ai_summary": None, "image_url": None,
            },
            {
                "id": "m3", "title": "RELIANCE retail expansion",
                "summary": "100 new stores planned",
                "source": "Moneycontrol", "symbols": ["RELIANCE"],
                "category": "bullish", "sentiment_score": 0.4, "confidence": 0.7,
                "published_at": "2025-06-14T08:00:00+00:00",
                "url": "https://example.com/m3", "ai_summary": None, "image_url": None,
            },
        ]

        async def _multi_article_news(**kwargs):
            return {"total": 3, "page": 1, "per_page": 50, "articles": articles}

        screener_data = [{
            "symbol": "RELIANCE", "composite_score": 85, "ltp": 2510.0,
            "change_pct": 1.2, "rsi": 62, "trend_up": True,
            "momentum_score": 78, "vol_ratio": 1.5,
        }]

        with patch.object(news_service, "get_news", side_effect=_multi_article_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks",
                   AsyncMock(return_value=screener_data)):
            result = await news_service.get_news_screener_recommendations(limit=10)

        # RELIANCE should have news_count=3
        reliance_rec = next(r for r in result["recommendations"] if r["symbol"] == "RELIANCE")
        assert reliance_rec["news_count"] == 3
        assert len(reliance_rec["headlines"]) == 3  # All 3 headlines, truncated to 3

        # Energy sector total_news should be 3
        sectors = {s["sector"]: s for s in result["sectors"]}
        assert sectors["Energy"]["total_news"] == 3

    @pytest.mark.asyncio
    async def test_multiple_articles_same_symbol_different_sentiment(self):
        """avg_sentiment should be the mean of all article sentiments for that symbol."""
        articles = [
            {
                "id": "s1", "title": "TCS positive news 1",
                "summary": "Good news", "source": "Moneycontrol",
                "symbols": ["TCS"], "category": "bullish",
                "sentiment_score": 0.9, "confidence": 0.9,
                "published_at": "2025-06-14T10:00:00+00:00",
                "url": "https://example.com/s1", "ai_summary": None, "image_url": None,
            },
            {
                "id": "s2", "title": "TCS negative news 1",
                "summary": "Bad news", "source": "Economic Times",
                "symbols": ["TCS"], "category": "bearish",
                "sentiment_score": -0.3, "confidence": 0.8,
                "published_at": "2025-06-14T09:00:00+00:00",
                "url": "https://example.com/s2", "ai_summary": None, "image_url": None,
            },
        ]

        async def _sentiment_news(**kwargs):
            return {"total": 2, "page": 1, "per_page": 50, "articles": articles}

        screener_data = [{
            "symbol": "TCS", "composite_score": 90, "ltp": 3300.0,
            "change_pct": 1.5, "rsi": 65, "trend_up": True,
            "momentum_score": 85, "vol_ratio": 1.8,
        }]

        with patch.object(news_service, "get_news", side_effect=_sentiment_news), \
             patch("app.services.stock_screener.stock_screener.screen_stocks",
                   AsyncMock(return_value=screener_data)):
            result = await news_service.get_news_screener_recommendations(limit=10)

        tcs_rec = next(r for r in result["recommendations"] if r["symbol"] == "TCS")
        expected_sentiment = round((0.9 + -0.3) / 2, 3)
        assert tcs_rec["avg_sentiment"] == expected_sentiment, \
            f"Expected {expected_sentiment}, got {tcs_rec['avg_sentiment']}"

        # IT sector avg_sentiment should match
        sectors = {s["sector"]: s for s in result["sectors"]}
        assert sectors["IT"]["avg_sentiment"] == expected_sentiment

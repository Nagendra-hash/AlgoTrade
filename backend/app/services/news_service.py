"""
News aggregation from RSS + external APIs with Redis caching.
Path: backend/app/services/news_service.py
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
import feedparser

from app.core.config import settings
from app.core.redis import redis_get, redis_set

logger = logging.getLogger(__name__)

NEWS_CACHE_TTL = settings.NEWS_CACHE_MINUTES * 60

BULLISH_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "beat", "profit", "growth", "record",
    "buyback", "dividend", "upgrade", "outperform", "strong", "robust", "positive",
    "soar", "climb", "advance", "breakthrough", "award", "contract", "partnership",
    "sanction", "export", "import", "supply", "shortage", "boon", "stimulus",
}
BEARISH_WORDS = {
    "fall", "drop", "decline", "loss", "miss", "weak", "downgrade", "underperform",
    "fraud", "probe", "investigation", "lawsuit", "fine", "penalty", "default",
    "crash", "plunge", "tumble", "slump", "resign", "debt", "recall", "ban", "warning",
    "sanctions", "tariff", "war", "conflict", "crisis", "tension", "disruption",
}
EARNINGS_WORDS = {"earnings", "results", "quarterly", "revenue", "profit", "eps", "guidance"}
MACRO_WORDS = {"rbi", "fed", "rate", "inflation", "gdp", "policy", "budget", "fiscal", "interest"}
BREAKING_WORDS = {"breaking", "urgent", "alert", "flash", "just in"}

GEOPOLITICAL_WORDS = {
    "geopolitical", "sanctions", "tariff", "trade war", "defense", "military",
    "conflict", "tension", "diplomatic", "foreign policy", "strategy", "alliance",
    "nuclear", "cyber", "intelligence", "espionage", "border", "territorial",
    "indo-pacific", "supply chain", "critical minerals", "rare earth", "energy security",
    "oil embargo", "OPEC", "geopolitical risk", "geopolitical tension",
    "global south", "multipolar", "great power", "hegemony", "deterrence",
    "China", "Russia", "Ukraine", "Middle East", "Iran", "North Korea",
    "Taiwan", "South China Sea", "Arctic", "NATO", "BRI", "Quad", "AUKUS",
}

RSS_FEEDS = {
    "Moneycontrol": "https://www.moneycontrol.com/rss/buzzingstocks.xml",
    "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Foreign Policy": "https://foreignpolicy.com/feed/",
}

# News sources that require dedicated NewsAPI queries (no RSS feed)
NEWSAPI_SOURCE_FEEDS = {
    "The Economist": {
        "sources": "the-economist",
        "domains": "economist.com",
    },
    "Geopolitical Monitor": {
        "domains": "geopoliticalmonitor.com",
    },
}

# ── Sector Mapping for news-driven stock recommendations ─────
# Each NSE symbol is mapped to its sector for grouped display.
SECTOR_MAP: dict[str, str] = {
    # Energy
    "RELIANCE":    "Energy",
    "ONGC":        "Energy",
    "BPCL":        "Energy",
    "COALINDIA":   "Energy",
    "POWERGRID":   "Energy",
    "NTPC":        "Energy",
    "ADANIENT":    "Energy",
    # Banking & Finance
    "HDFCBANK":    "Banking & Finance",
    "ICICIBANK":   "Banking & Finance",
    "SBIN":        "Banking & Finance",
    "KOTAKBANK":   "Banking & Finance",
    "AXISBANK":    "Banking & Finance",
    "INDUSINDBK":  "Banking & Finance",
    "BAJFINANCE":  "Banking & Finance",
    "BAJAJFINSV":  "Banking & Finance",
    "HDFCLIFE":    "Banking & Finance",
    "SBILIFE":     "Banking & Finance",
    # IT
    "TCS":         "IT",
    "INFY":        "IT",
    "WIPRO":       "IT",
    "HCLTECH":     "IT",
    "TECHM":       "IT",
    # Defense & Aerospace
    "HAL":         "Defense & Aerospace",
    "BEL":         "Defense & Aerospace",
    # Auto
    "TATAMOTORS":  "Auto",
    "MARUTI":      "Auto",
    "M&M":         "Auto",
    "EICHERMOT":   "Auto",
    "HEROMOTOCO":  "Auto",
    # Pharma
    "SUNPHARMA":   "Pharma",
    "CIPLA":       "Pharma",
    "DRREDDY":     "Pharma",
    "DIVISLAB":    "Pharma",
    "APOLLOHOSP":  "Pharma",
    # FMCG
    "HINDUNILVR":  "FMCG",
    "ITC":         "FMCG",
    "BRITANNIA":   "FMCG",
    "NESTLEIND":   "FMCG",
    "TATACONSUM":  "FMCG",
    # Metals & Mining
    "TATASTEEL":   "Metals & Mining",
    "JSWSTEEL":    "Metals & Mining",
    "GRASIM":      "Metals & Mining",
    "HINDALCO":    "Metals & Mining",
    # Infrastructure & Engineering
    "LT":          "Infrastructure",
    "ADANIPORTS":  "Infrastructure",
    "ULTRACEMCO":  "Infrastructure",
    # Telecom
    "BHARTIARTL":  "Telecom",
    # Consumer
    "TITAN":       "Consumer",
    "TRENT":       "Consumer",
    # Others
    "IRCTC":       "Services",
    "ASIANPAINT":  "Consumer",
}

SYMBOL_ALIASES = {
    "RELIANCE": ["reliance", "mukesh ambani", "jio", "ril"],
    "TCS": ["tcs", "tata consultancy"],
    "INFY": ["infosys", "infy"],
    "HDFCBANK": ["hdfc bank", "hdfc"],
    "ICICIBANK": ["icici bank", "icici"],
    "SBIN": ["sbi", "state bank of india"],
    "WIPRO": ["wipro"],
    "BAJFINANCE": ["bajaj finance"],
    "TATAMOTORS": ["tata motors", "jaguar land rover"],
    "NIFTY50": ["nifty", "nse", "nifty 50"],
    "BANKNIFTY": ["bank nifty", "banking"],
    "SENSEX": ["sensex", "bse"],
    "HINDUNILVR": ["hindustan unilever", "hul"],
    "BHARTIARTL": ["bharti airtel", "airtel"],
    "MARUTI": ["maruti suzuki", "maruti"],
    "SUNPHARMA": ["sun pharma", "sun pharmaceutical"],
    "ITC": ["itc", "itc limited"],
    "LT": ["larsen & toubro", "l&t"],
    "AXISBANK": ["axis bank"],
    "KOTAKBANK": ["kotak mahindra", "kotak bank"],
    "HCLTECH": ["hcl technologies", "hcl"],
    "TATASTEEL": ["tata steel"],
    "JSWSTEEL": ["jsw steel"],
    "HAL": ["hindustan aeronautics", "hal"],
    "BEL": ["bharat electronics", "bel"],
    "COALINDIA": ["coal india"],
    "ONGC": ["oil and natural gas corporation", "ongc"],
    "POWERGRID": ["power grid corporation", "powergrid"],
    "NTPC": ["ntpc", "national thermal power"],
    "ADANIENT": ["adani enterprises", "adani"],
    "ADANIPORTS": ["adani ports"],
    "IRCTC": ["irctc", "indian railway catering"],
    "M&M": ["mahindra & mahindra", "mahindra"],
}

# ── Geopolitical Monitor region classification ────────────────
GEO_REGION_KEYWORDS: dict[str, list[str]] = {
    "Indo-Pacific": ["china", "taiwan", "south china sea", "japan", "india",
                     "australia", "quad", "aukus", "indo-pacific", "southeast asia"],
    "Middle East": ["middle east", "iran", "israel", "saudi", "opec", "gulf",
                    "iraq", "syria", "red sea", "yemen", "hezbollah", "hamas"],
    "Eastern Europe": ["ukraine", "russia", "nato", "belarus", "poland",
                       "baltic", "black sea", "crimea", "moldova"],
    "Africa": ["africa", "sahel", "nigeria", "ethiopia", "somalia", "sudan",
               "mali", "niger", "congo"],
    "Latin America": ["brazil", "venezuela", "argentina", "colombia", "chile",
                      "latin america", "amazon", "andean"],
    "Arctic": ["arctic", "north pole", "greenland", "iceland", "northern sea route"],
    "Europe": ["eu", "european union", "europe", "germany", "france", "uk",
               "britain", "brexit", "italy", "spain", "netherlands"],
}

GEO_REGION_METADATA: dict[str, dict[str, str]] = {
    "Indo-Pacific": {
        "color": "from-orange-500 to-red-500", "border": "border-orange-500/30",
        "bg": "bg-orange-500/10", "text": "text-orange-400", "icon": "🌏",
        "description": "Trade routes, territorial disputes, military buildup"
    },
    "Middle East": {
        "color": "from-red-500 to-rose-600", "border": "border-red-500/30",
        "bg": "bg-red-500/10", "text": "text-red-400", "icon": "🕌",
        "description": "Energy supply, regional conflicts, diplomatic shifts"
    },
    "Eastern Europe": {
        "color": "from-blue-500 to-indigo-600", "border": "border-blue-500/30",
        "bg": "bg-blue-500/10", "text": "text-blue-400", "icon": "🏰",
        "description": "NATO expansion, energy dependency, military conflict"
    },
    "Africa": {
        "color": "from-amber-500 to-yellow-600", "border": "border-amber-500/30",
        "bg": "bg-amber-500/10", "text": "text-amber-400", "icon": "🌍",
        "description": "Resource extraction, infrastructure investment, debt"
    },
    "Latin America": {
        "color": "from-emerald-500 to-teal-600", "border": "border-emerald-500/30",
        "bg": "bg-emerald-500/10", "text": "text-emerald-400", "icon": "🌎",
        "description": "Commodity exports, political shifts, trade agreements"
    },
    "Arctic": {
        "color": "from-cyan-500 to-sky-600", "border": "border-cyan-500/30",
        "bg": "bg-cyan-500/10", "text": "text-cyan-400", "icon": "❄️",
        "description": "Melting ice caps, new shipping routes, resource race"
    },
    "Europe": {
        "color": "from-violet-500 to-purple-600", "border": "border-violet-500/30",
        "bg": "bg-violet-500/10", "text": "text-violet-400", "icon": "🇪🇺",
        "description": "Regulatory changes, economic policy, trade deals"
    },
    "Other": {
        "color": "from-gray-500 to-gray-600", "border": "border-gray-500/30",
        "bg": "bg-gray-500/10", "text": "text-gray-400", "icon": "🌐",
        "description": "Global developments"
    },
}


def _compute_risk_index(
    regions: list[dict],
    sectors: list[dict],
    total_articles: int,
    mentioned_stocks: int,
) -> dict:
    """
    Compute a composite Geopolitical Risk Index (0-100) from:
    - News volume (0-35): article count relative to 50-article max
    - Negative sentiment weight (0-30): bearish-weighted sentiment across regions
    - Sector breadth (0-20): number of sectors and stocks affected
    - Region spread (0-15): how many active regions out of 7
    """
    # 1. News volume factor (0-35)
    vol_capacity = max(total_articles, 50)
    vol_score = min(total_articles / vol_capacity * 35, 35)

    # 2. Negative sentiment weight (0-30)
    bearish_weight = 0
    for r in regions:
        if r.get("avg_sentiment", 0) < 0:
            # More negative = more risk, scaled by article count
            neg_intensity = abs(r["avg_sentiment"]) * 30
            article_weight = r.get("article_count", 1) / max(total_articles, 1)
            bearish_weight += neg_intensity * article_weight
        elif r.get("avg_sentiment", 0) == 0:
            # Neutral regions contribute baseline risk (uncertainty)
            article_weight = r.get("article_count", 1) / max(total_articles, 1)
            bearish_weight += 10 * article_weight
    sent_score = min(bearish_weight, 30)

    # 3. Sector breadth (0-20)
    sector_count = len(sectors)
    stock_count = mentioned_stocks
    sector_score = min(
        (sector_count / 12) * 10 +  # 12 possible sectors → 10 points
        min(stock_count / 15, 1) * 10,  # 15+ stocks → 10 points
        20,
    )

    # 4. Region spread (0-15)
    active = len(regions)
    region_score = min(active / 7 * 15, 15)

    total = round(vol_score + sent_score + sector_score + region_score, 1)
    total = max(0, min(total, 100))

    # Risk level label
    if total >= 75:
        level = "critical"
    elif total >= 50:
        level = "high"
    elif total >= 25:
        level = "moderate"
    else:
        level = "low"

    return {
        "score": total,
        "level": level,
        "components": {
            "news_volume": round(vol_score, 1),
            "sentiment_risk": round(sent_score, 1),
            "sector_breadth": round(sector_score, 1),
            "region_spread": round(region_score, 1),
        },
        "details": {
            "total_articles": total_articles,
            "active_regions": len(regions),
            "affected_sectors": len(sectors),
            "mentioned_stocks": mentioned_stocks,
        },
    }


def _classify_geo_region(text: str) -> str:
    tl = text.lower()
    for region, keywords in GEO_REGION_KEYWORDS.items():
        if any(k in tl for k in keywords):
            return region
    return "Other"


def _detect_symbols(text: str) -> List[str]:
    tl = text.lower()
    return [sym for sym, aliases in SYMBOL_ALIASES.items() if any(a in tl for a in aliases)]


def _classify(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    words = set(text.split())
    if any(k in text for k in BREAKING_WORDS):
        return "breaking"
    if any(k in text for k in GEOPOLITICAL_WORDS):
        return "geopolitical"
    if words & EARNINGS_WORDS:
        return "earnings"
    if words & MACRO_WORDS:
        return "macro"
    bull = len(words & BULLISH_WORDS)
    bear = len(words & BEARISH_WORDS)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def _score(title: str, summary: str) -> tuple[float, float]:
    text = (title + " " + summary).lower()
    words = set(text.split())
    bull = len(words & BULLISH_WORDS)
    bear = len(words & BEARISH_WORDS)
    total = bull + bear
    if total == 0:
        return 0.0, 0.3
    score = (bull - bear) / total
    confidence = min(0.5 + total / 10, 0.95)
    return round(score, 3), round(confidence, 3)


async def _fetch_rss(client: httpx.AsyncClient, source: str, url: str) -> List[dict]:
    try:
        resp = await client.get(url, timeout=10)
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:25]:
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            link = getattr(entry, "link", "") or ""
            pub = getattr(entry, "published", "") or ""
            try:
                import email.utils
                parsed = email.utils.parsedate(pub)
                pub_dt = datetime(*parsed[:6], tzinfo=timezone.utc) if parsed else datetime.now(timezone.utc)
            except Exception:
                pub_dt = datetime.now(timezone.utc)
            score, conf = _score(title, summary)
            articles.append({
                "id": hashlib.md5(link.encode()).hexdigest(),
                "title": title,
                "summary": summary[:400],
                "url": link,
                "source": source,
                "published_at": pub_dt.isoformat(),
                "symbols": _detect_symbols(title + " " + summary),
                "category": _classify(title, summary),
                "sentiment_score": score,
                "confidence": conf,
                "ai_summary": None,
                "image_url": None,
            })
        return articles
    except Exception as e:
        logger.warning(f"RSS {source}: {e}")
        return []


async def _fetch_newsapi(symbols: Optional[List[str]] = None) -> List[dict]:
    if not settings.NEWSAPI_KEY:
        return []
    try:
        q = " OR ".join(symbols[:5]) if symbols else "Indian stock market NSE NIFTY"
        url = (f"https://newsapi.org/v2/everything?q={q}&language=en"
               f"&sortBy=publishedAt&pageSize=20&apiKey={settings.NEWSAPI_KEY}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            data = resp.json()
        articles = []
        for item in data.get("articles", []):
            title = item.get("title", "") or ""
            summary = item.get("description", "") or ""
            score, conf = _score(title, summary)
            source_name = item.get("source", {}).get("name", "NewsAPI")
            articles.append({
                "id": hashlib.md5(item.get("url", "").encode()).hexdigest(),
                "title": title,
                "summary": summary[:400],
                "url": item.get("url", ""),
                "source": source_name,
                "published_at": item.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                "symbols": _detect_symbols(title + " " + summary),
                "category": _classify(title, summary),
                "sentiment_score": score,
                "confidence": conf,
                "ai_summary": None,
                "image_url": item.get("urlToImage"),
            })
        return articles
    except Exception as e:
        logger.error(f"NewsAPI: {e}")
        return []


async def _fetch_newsapi_by_source(
    source_name: str,
    source_config: dict,
    symbols: Optional[List[str]] = None,
) -> List[dict]:
    """
    Fetch news from a specific source via NewsAPI.
    Used for sources that don't have RSS feeds (e.g., The Economist, Geopolitical Monitor).
    """
    if not settings.NEWSAPI_KEY:
        return []
    try:
        params = {
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": settings.NEWSAPI_KEY,
        }
        if "sources" in source_config:
            params["sources"] = source_config["sources"]
        if "domains" in source_config:
            params["domains"] = source_config["domains"]
        q = " ".join(symbols[:5]) if symbols else ""
        if q:
            params["q"] = q
        else:
            # If no symbols provided, use geopolitical keywords to get relevant articles
            params["q"] = "geopolitics OR foreign policy OR international affairs OR global economy"

        url = "https://newsapi.org/v2/everything"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10)
            data = resp.json()

        articles = []
        for item in data.get("articles", []):
            title = item.get("title", "") or ""
            summary = item.get("description", "") or ""
            score, conf = _score(title, summary)
            articles.append({
                "id": hashlib.md5(item.get("url", "").encode()).hexdigest(),
                "title": title,
                "summary": summary[:400],
                "url": item.get("url", ""),
                "source": source_name,
                "published_at": item.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                "symbols": _detect_symbols(title + " " + summary),
                "category": _classify(title, summary),
                "sentiment_score": score,
                "confidence": conf,
                "ai_summary": None,
                "image_url": item.get("urlToImage"),
            })
        return articles
    except Exception as e:
        logger.error(f"NewsAPI source {source_name}: {e}")
        return []


async def _fetch_finnhub(symbols: Optional[List[str]] = None) -> List[dict]:
    if not settings.FINNHUB_KEY:
        return []
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={settings.FINNHUB_KEY}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            items = resp.json()
        articles = []
        for item in items[:20]:
            title = item.get("headline", "") or ""
            summary = item.get("summary", "") or ""
            score, conf = _score(title, summary)
            articles.append({
                "id": str(item.get("id", hashlib.md5(title.encode()).hexdigest())),
                "title": title,
                "summary": summary[:400],
                "url": item.get("url", ""),
                "source": item.get("source", "Finnhub"),
                "published_at": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ).isoformat(),
                "symbols": _detect_symbols(title + " " + summary),
                "category": _classify(title, summary),
                "sentiment_score": score,
                "confidence": conf,
                "ai_summary": None,
                "image_url": item.get("image"),
            })
        return articles
    except Exception as e:
        logger.error(f"Finnhub: {e}")
        return []


def _dedupe_sort(articles: List[dict]) -> List[dict]:
    seen = set()
    unique = []
    for a in articles:
        if a["id"] not in seen:
            seen.add(a["id"])
            unique.append(a)

    def parse_dt(a):
        try:
            return datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(unique, key=parse_dt, reverse=True)


class NewsService:
    async def get_news(
        self,
        symbols: Optional[List[str]] = None,
        category: Optional[str] = None,
        sources: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        cache_key = f"news:{','.join(sorted(symbols or []))}:{category}:{','.join(sorted(sources or []))}"
        cached = await redis_get(cache_key)
        if cached:
            articles = cached
        else:
            articles = await self._aggregate(symbols, sources)
            await redis_set(cache_key, articles, ttl=NEWS_CACHE_TTL)

        if category and category != "all":
            articles = [a for a in articles if a.get("category") == category]

        if symbols:
            syms_upper = [s.upper() for s in symbols]
            articles = [
                a for a in articles
                if not a.get("symbols") or any(s in syms_upper for s in a.get("symbols", []))
            ]

        if sources:
            articles = [a for a in articles if a.get("source", "") in sources]

        total = len(articles)
        start = (page - 1) * per_page
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "articles": articles[start: start + per_page],
        }

    async def check_symbol_news_mention(
        self,
        symbol: str,
        sources: List[str],
        max_age_minutes: int = 60,
    ) -> dict:
        """
        Check if a symbol was mentioned in recent news from specified sources.
        Used by the alert engine for news_mention alerts.
        Returns dict with mentioned, articles, and latest_headline.
        """
        news_data = await self.get_news(symbols=[symbol], sources=sources, per_page=20)
        articles = news_data.get("articles", [])

        # Filter to recent articles within the max_age window
        now = datetime.now(timezone.utc)
        recent = []
        for a in articles:
            try:
                pub = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
                if (now - pub).total_seconds() / 60 <= max_age_minutes:
                    recent.append(a)
            except Exception:
                recent.append(a)

        mentioned = len(recent) > 0
        return {
            "mentioned": mentioned,
            "article_count": len(recent),
            "latest_headline": recent[0]["title"] if recent else None,
            "latest_source": recent[0]["source"] if recent else None,
            "articles": recent[:3],
        }

    async def _aggregate(self, symbols: Optional[List[str]] = None, sources: Optional[List[str]] = None) -> List[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            rss_tasks = [_fetch_rss(client, src, url) for src, url in RSS_FEEDS.items()]
            rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)

        all_articles: List[dict] = []
        for r in rss_results:
            if isinstance(r, list):
                all_articles.extend(r)

        # Fetch from NewsAPI source feeds (The Economist, Geopolitical Monitor)
        source_tasks = [
            _fetch_newsapi_by_source(name, config, symbols)
            for name, config in NEWSAPI_SOURCE_FEEDS.items()
        ]

        extra = await asyncio.gather(
            _fetch_newsapi(symbols),
            _fetch_finnhub(symbols),
            *source_tasks,
            return_exceptions=True,
        )
        for r in extra:
            if isinstance(r, list):
                all_articles.extend(r)

        return _dedupe_sort(all_articles)

    async def get_geo_monitor_data(self, limit: int = 30) -> dict:
        """
        Aggregated data for the Geopolitical Monitor dashboard.
        Groups geopolitical news by region, builds a timeline,
        and analyzes sector impact.
        """
        from app.services.stock_screener import stock_screener

        # Get geopolitical news from all relevant sources
        geo_sources = ["Foreign Policy", "The Economist", "Geopolitical Monitor"]
        news_data = await self.get_news(
            category="geopolitical",
            sources=geo_sources,
            per_page=limit,
        )
        all_articles = news_data.get("articles", [])

        # Also fetch general news with geopolitical category across all sources
        general_geo = await self.get_news(category="geopolitical", per_page=limit)
        for a in general_geo.get("articles", []):
            if not any(x["id"] == a["id"] for x in all_articles):
                all_articles.append(a)

        # ── Region classification (using module-level constants) ──
        # Group articles by region
        region_groups: dict[str, dict] = {}
        timeline: list[dict] = []
        for article in all_articles:
            region = _classify_geo_region((article.get("title", "") or "") + " " + (article.get("summary", "") or ""))
            if region not in region_groups:
                region_groups[region] = {
                    "region": region,
                    "metadata": GEO_REGION_METADATA.get(region, GEO_REGION_METADATA["Other"]),
                    "article_count": 0,
                    "stocks_mentioned": set(),
                    "sectors_affected": set(),
                    "avg_sentiment": 0,
                    "total_sentiment": 0,
                    "sources": set(),
                    "latest_headline": None,
                }
            rg = region_groups[region]
            rg["article_count"] += 1
            for sym in article.get("symbols", []):
                rg["stocks_mentioned"].add(sym)
                sector = SECTOR_MAP.get(sym, "Other")
                rg["sectors_affected"].add(sector)
            rg["total_sentiment"] += article.get("sentiment_score", 0)
            src = article.get("source", "")
            if src:
                rg["sources"].add(src)
            if not rg["latest_headline"]:
                rg["latest_headline"] = article.get("title", "")

            # Timeline entry
            timeline.append({
                "id": article["id"],
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "region": region,
                "published_at": article.get("published_at", ""),
                "symbols": article.get("symbols", [])[:3],
                "sentiment_score": article.get("sentiment_score", 0),
                "url": article.get("url", ""),
                "category": article.get("category", ""),
            })

        # Finalize region groups
        for rg in region_groups.values():
            rg["avg_sentiment"] = round(rg["total_sentiment"] / rg["article_count"], 3) if rg["article_count"] > 0 else 0
            rg["stocks_mentioned"] = list(rg["stocks_mentioned"])[:10]
            rg["sectors_affected"] = list(rg["sectors_affected"])[:8]
            rg["sources"] = list(rg["sources"])
            del rg["total_sentiment"]

        # Sort regions by article count
        sorted_regions = sorted(
            region_groups.values(),
            key=lambda r: r["article_count"],
            reverse=True,
        )

        # Sort timeline by date (newest first)
        def _parse_dt(a):
            try:
                return datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)
        timeline.sort(key=_parse_dt, reverse=True)

        # Get screener data for mentioned stocks
        all_stocks = set()
        for rg in region_groups.values():
            all_stocks.update(rg.get("stocks_mentioned", []))
        sector_impact_map: dict[str, dict] = {}
        try:
            screened = await stock_screener.screen_stocks(
                criteria={"strategy_type": "momentum"},
                limit=50,
            )
            screened_map = {s["symbol"]: s for s in screened}
            for sym in all_stocks:
                sector = SECTOR_MAP.get(sym, "Other")
                if sector not in sector_impact_map:
                    sector_impact_map[sector] = {
                        "sector": sector,
                        "stock_count": 0,
                        "symbols": [],
                        "avg_momentum": 0,
                        "total_momentum": 0,
                        "status": "neutral",
                    }
                sim = sector_impact_map[sector]
                sim["stock_count"] += 1
                sim["symbols"].append(sym)
                if sym in screened_map:
                    scr = screened_map[sym]
                    ms = scr.get("momentum_score", 50)
                    sim["total_momentum"] += ms
                    if ms > 60:
                        sim["status"] = "bullish" if sim["status"] != "bearish" else sim["status"]
                    elif ms < 40:
                        sim["status"] = "bearish" if sim["status"] != "bullish" else sim["status"]

            for sim in sector_impact_map.values():
                sim["avg_momentum"] = round(sim["total_momentum"] / sim["stock_count"], 1) if sim["stock_count"] > 0 else 0
                del sim["total_momentum"]
        except Exception as e:
            logger.warning(f"Screener failed for geo monitor: {e}")

        sorted_sectors = sorted(
            sector_impact_map.values(),
            key=lambda s: s["stock_count"],
            reverse=True,
        )

        # ── Geopolitical Risk Index (0-100) ────────────────────────
        # Composite of: news volume, negative sentiment weight, sector breadth, region spread
        risk_index = _compute_risk_index(
            regions=sorted_regions,
            sectors=sorted_sectors,
            total_articles=len(all_articles),
            mentioned_stocks=len(all_stocks),
        )

        return {
            "total_articles": len(all_articles),
            "active_regions": len(sorted_regions),
            "mentioned_stocks": len(all_stocks),
            "regions": sorted_regions,
            "timeline": timeline[:50],
            "sector_impact": sorted_sectors,
            "risk_index": risk_index,
        }

    async def get_geo_monitor_history(self, days: int = 7) -> dict:
        """
        Build a 7-day historical snapshot of geopolitical news coverage and sector impact.
        Groups articles by day, computes volume, sentiment, region/sector activity per day,
        and calculates week-over-week change.
        """
        # Fetch enough articles to have coverage across multiple days
        news_data = await self.get_news(
            category="geopolitical",
            per_page=200,
        )
        articles = news_data.get("articles", [])

        now = datetime.now(timezone.utc)
        daily: dict[str, dict] = {}
        for d in range(days - 1, -1, -1):
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=d)
            day_key = day_start.strftime("%Y-%m-%d")
            daily[day_key] = {
                "date": day_key,
                "article_count": 0,
                "avg_sentiment": 0.0,
                "total_sentiment": 0.0,
                "active_regions": set(),
                "mentioned_stocks": set(),
                "sectors_affected": set(),
                "top_region": None,
            }

        for article in articles:
            try:
                pub = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            day_key = pub.strftime("%Y-%m-%d")
            if day_key not in daily:
                continue

            day = daily[day_key]
            day["article_count"] += 1
            region = _classify_geo_region((article.get("title", "") or "") + " " + (article.get("summary", "") or ""))
            day["active_regions"].add(region)
            for sym in article.get("symbols", []):
                day["mentioned_stocks"].add(sym)
                sector = SECTOR_MAP.get(sym, "Other")
                day["sectors_affected"].add(sector)
            day["total_sentiment"] += article.get("sentiment_score", 0)

        # Finalize daily snapshots
        daily_sorted = []
        for day_key in sorted(daily.keys()):
            day = daily[day_key]
            day["avg_sentiment"] = round(day["total_sentiment"] / max(day["article_count"], 1), 3)
            day["active_regions"] = len(day["active_regions"])
            day["mentioned_stocks"] = len(day["mentioned_stocks"])
            day["sectors_affected"] = len(day["sectors_affected"])
            del day["total_sentiment"]
            daily_sorted.append(day)

        # ── Week-over-week deltas ──
        def _calc_delta(key: str) -> dict:
            vals = [d[key] for d in daily_sorted if d[key] is not None]
            if len(vals) < 2:
                return {"current": vals[-1] if vals else 0, "previous": 0, "change_pct": 0}
            current = vals[-1]
            previous = sum(vals[:-1]) / (len(vals) - 1)
            change_pct = round(((current - previous) / max(previous, 1)) * 100, 1)
            return {"current": current, "previous": round(previous, 1), "change_pct": change_pct}

        deltas = {
            "articles": _calc_delta("article_count"),
            "sentiment": _calc_delta("avg_sentiment"),
            "regions": _calc_delta("active_regions"),
            "sectors": _calc_delta("sectors_affected"),
            "stocks": _calc_delta("mentioned_stocks"),
        }

        return {
            "days": daily_sorted,
            "deltas": deltas,
            "total_articles_7d": sum(d["article_count"] for d in daily_sorted),
        }

    async def get_news_screener_recommendations(
        self,
        limit: int = 10,
        sources: Optional[List[str]] = None,
    ) -> dict:
        """
        Get stock screener recommendations driven by recent news.
        Analyzes latest news, extracts mentioned symbols, and returns screener scores
        grouped by sector (defense, energy, banking, IT, etc.).
        """
        from app.services.stock_screener import stock_screener

        # Get latest news (uses cached version; cache TTL is 5 minutes so it's fresh enough)
        news_data = await self.get_news(sources=sources, per_page=50)
        articles = news_data.get("articles", [])

        # Collect all mentioned symbols with their article counts
        symbol_news_map: dict[str, dict] = {}
        for article in articles:
            for sym in article.get("symbols", []):
                if sym not in symbol_news_map:
                    symbol_news_map[sym] = {
                        "symbol": sym,
                        "news_count": 0,
                        "headlines": [],
                        "avg_sentiment": 0,
                        "sources": set(),
                    }
                symbol_news_map[sym]["news_count"] += 1
                symbol_news_map[sym]["headlines"].append(article.get("title", ""))
                symbol_news_map[sym]["avg_sentiment"] += article.get("sentiment_score", 0)
                symbol_news_map[sym]["sources"].add(article.get("source", ""))

        if not symbol_news_map:
            return {
                "symbols_analyzed": 0,
                "news_count": len(articles),
                "sectors": {},
                "recommendations": [],
            }

        # Average sentiment scores
        for sym_data in symbol_news_map.values():
            count = sym_data["news_count"]
            if count > 0:
                sym_data["avg_sentiment"] = round(sym_data["avg_sentiment"] / count, 3)
            sym_data["sources"] = list(sym_data["sources"])
            sym_data["headlines"] = sym_data["headlines"][:3]

        # Run stock screener on the mentioned symbols
        mentioned_symbols = list(symbol_news_map.keys())
        try:
            screened = await stock_screener.screen_stocks(
                criteria={"strategy_type": "momentum"},
                limit=limit,
            )
            # Filter screener results to only symbols mentioned in news
            screened_map = {s["symbol"]: s for s in screened}
        except Exception as e:
            logger.warning(f"Screener failed for news recommendations: {e}")
            screened_map = {}

        # Build recommendations merging news data with screener data
        recommendations = []
        sectors: dict[str, dict] = {}
        for sym, news_data in symbol_news_map.items():
            screener_data = screened_map.get(sym, None)
            sector = SECTOR_MAP.get(sym, "Other")
            recommendation = {
                "symbol": sym,
                "sector": sector,
                "news_count": news_data["news_count"],
                "headlines": news_data["headlines"],
                "avg_sentiment": news_data["avg_sentiment"],
                "sources": news_data["sources"],
                "screener_score": screener_data.get("composite_score", 0) if screener_data else None,
                "ltp": screener_data.get("ltp", 0) if screener_data else None,
                "change_pct": screener_data.get("change_pct", 0) if screener_data else None,
                "rsi": screener_data.get("rsi", 0) if screener_data else None,
                "trend_up": screener_data.get("trend_up", False) if screener_data else None,
                "momentum_score": screener_data.get("momentum_score", 0) if screener_data else None,
                "volume_ratio": screener_data.get("vol_ratio", 0) if screener_data else None,
            }
            recommendations.append(recommendation)

            # Group by sector
            if sector not in sectors:
                sectors[sector] = {
                    "sector": sector,
                    "count": 0,
                    "avg_sentiment": 0,
                    "total_news": 0,
                    "symbols": [],
                    "top_stock": None,
                }
            sectors[sector]["count"] += 1
            sectors[sector]["total_news"] += recommendation["news_count"]
            sectors[sector]["avg_sentiment"] += recommendation.get("avg_sentiment", 0)
            sectors[sector]["symbols"].append(recommendation["symbol"])

        # Finalize sector aggregates and sort recommendations within each sector
        for sector_data in sectors.values():
            c = sector_data["count"]
            if c > 0:
                sector_data["avg_sentiment"] = round(sector_data["avg_sentiment"] / c, 3)

        def _combined_score(r: dict) -> float:
            news_score = min(r["news_count"] * 10, 50)
            sentiment_score = max(0, r["avg_sentiment"] * 100)
            screener = r.get("screener_score") or 0
            return news_score + sentiment_score + screener

        recommendations.sort(key=_combined_score, reverse=True)

        # Assign top stock per sector after sorting
        for rec in recommendations:
            sec = rec["sector"]
            if sec in sectors and sectors[sec]["top_stock"] is None:
                sectors[sec]["top_stock"] = rec["symbol"]

        # Sort sectors by total news coverage (most active first)
        sorted_sectors = sorted(
            sectors.values(),
            key=lambda s: s["total_news"],
            reverse=True,
        )

        return {
            "symbols_analyzed": len(recommendations),
            "news_count": len(articles),
            "sectors": sorted_sectors,
            "recommendations": recommendations[:limit],
        }


news_service = NewsService()

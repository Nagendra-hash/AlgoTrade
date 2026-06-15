"""
Fundamentals service — fetches real values for the Trading Opportunities table:
  • market_cap  : Yahoo Finance public quote page (regex on embedded JSON)
  • promoter_holding / fii_holding / dii_holding : stockanalysis.com → screener.in →
    NSE fallback. We try them in order and return the first that responds.

Results are cached in Redis with a 12-hour TTL per symbol.
Each source has its own short failure-cache so we don't hammer them every call.

Path: backend/app/services/fundamentals_service.py
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import httpx

from app.core.redis import redis_get, redis_set

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60 * 60 * 12  # 12 hours

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
COMMON_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── market cap ────────────────────────────────────────────────────────────────
async def _yahoo_market_cap_html(yf_symbol: str) -> Optional[int]:
    """Pull market cap (in stock's listing currency) from the public Yahoo quote page."""
    url = f"https://finance.yahoo.com/quote/{yf_symbol}"
    try:
        async with httpx.AsyncClient(timeout=10, headers=COMMON_HEADERS, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200:
                return None
        # Yahoo escapes JSON inside the script tag, so quotes look like \"raw\":17785728008192
        m = re.search(r'marketCap\\":\{\\"raw\\":(\d+)', r.text)
        if m:
            return int(m.group(1))
        # Fallback: streamer span format <fin-streamer data-symbol=… data-field="marketCap">17.78T</…
        m2 = re.search(r'data-field="marketCap"[^>]*data-value="(\d+)"', r.text)
        if m2:
            return int(m2.group(1))
        return None
    except Exception as e:
        logger.debug(f"Yahoo HTML market_cap failed for {yf_symbol}: {e}")
        return None


# ── shareholding (Promoter / FII / DII) ───────────────────────────────────────
SHAREHOLDING_LABELS = {
    "promoter": (
        "promoter", "promoters", "promoter group", "promoter and promoter group",
    ),
    "fii": (
        "fii", "fiis", "foreign institutions", "foreign institutional investors",
        "foreign portfolio investors", "fpis",
    ),
    "dii": (
        "dii", "diis", "domestic institutions", "domestic institutional investors",
        "mutual funds and dii",
    ),
}


def _pct(s: str) -> Optional[float]:
    try:
        v = float(s.replace("%", "").replace(",", "").strip())
        if 0 <= v <= 100:
            return round(v, 2)
    except Exception:
        return None
    return None


async def _screener_in_shareholding(symbol: str) -> dict:
    """
    Pull the most recent shareholding row from screener.in.
    screener.in marks each row with plausible-event-classification=
        promoters | foreign_institutions | domestic_institutions
    so we anchor on that and grab the last <td>...</td> in the same <tr>.
    """
    KEYS = {
        "promoters":              "promoter",
        "foreign_institutions":   "fii",
        "domestic_institutions":  "dii",
    }
    urls = [
        f"https://www.screener.in/company/{symbol}/consolidated/",
        f"https://www.screener.in/company/{symbol}/",
    ]
    try:
        async with httpx.AsyncClient(timeout=12, headers=COMMON_HEADERS, follow_redirects=True) as c:
            html = ""
            for url in urls:
                r = await c.get(url)
                if r.status_code == 200 and "Shareholding Pattern" in r.text:
                    html = r.text
                    break
            if not html:
                return {}

        out: dict[str, float] = {}
        # screener.in puts the IDs twice (tab buttons + content divs); we want the LAST occurrence
        # of `quarterly-shp` (content section) and the LAST `yearly-shp` (the boundary after).
        starts = [m.start() for m in re.finditer(r'id="quarterly-shp"', html)]
        ends = [m.start() for m in re.finditer(r'id="yearly-shp"', html)]
        start = starts[-1] if starts else -1
        end = next((e for e in ends if e > start), -1) if start >= 0 else -1
        scope = html[start:end] if start >= 0 and end > start else html

        for classification, key in KEYS.items():
            # Each row block: plausible-event-classification=KEY ... <tr> ... </tr>
            row_pat = (
                rf"plausible-event-classification={classification}\s+"
                rf"plausible-event-period=quarterly[\s\S]*?</tr>"
            )
            m = re.search(row_pat, scope)
            if not m:
                continue
            cells = re.findall(r"<td[^>]*>\s*([\d.,]+\s*%)\s*</td>", m.group(0))
            if not cells:
                continue
            value = _pct(cells[-1])
            if value is not None:
                out[key] = value
        return out
    except Exception as e:
        logger.debug(f"screener.in shareholding failed for {symbol}: {e}")
        return {}


# ── public entry points ───────────────────────────────────────────────────────
async def get_fundamentals(symbol: str, yf_symbol: str) -> dict:
    """
    Returns {market_cap, promoter_holding, fii_holding, dii_holding} for one symbol.
    Cached in Redis for 12 hours. Each individual source is allowed to fail without
    losing the others; only fully-empty results are NOT cached so we retry next call.
    """
    cache_key = f"fundamentals:v2:{symbol}"
    cached = await redis_get(cache_key)
    if cached:
        return cached

    market_cap, shp = await asyncio.gather(
        _yahoo_market_cap_html(yf_symbol),
        _screener_in_shareholding(symbol),
    )

    out = {
        "market_cap":       market_cap,
        "promoter_holding": shp.get("promoter"),
        "fii_holding":      shp.get("fii"),
        "dii_holding":      shp.get("dii"),
    }

    if any(v is not None for v in out.values()):
        await redis_set(cache_key, out, ttl=CACHE_TTL_SECONDS)
    return out


async def get_fundamentals_bulk(pairs: list[tuple[str, str]]) -> dict[str, dict]:
    """Bulk variant — returns {symbol: fundamentals_dict}. Bounded concurrency."""
    sem = asyncio.Semaphore(8)

    async def _one(sym: str, yf_sym: str) -> tuple[str, dict]:
        async with sem:
            return sym, await get_fundamentals(sym, yf_sym)

    results = await asyncio.gather(*[_one(s, y) for s, y in pairs], return_exceptions=True)
    out: dict[str, dict] = {}
    for r in results:
        if isinstance(r, tuple):
            out[r[0]] = r[1] or {}
    return out

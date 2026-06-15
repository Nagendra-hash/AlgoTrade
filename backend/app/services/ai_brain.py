"""
AI Brain — the LLM-driven trade decision engine for the auto-trade engine.

The brain is invoked per (strategy, symbol) tick when strategy_type == "ai_brain".
It collects technicals + sentiment + recent news, asks the user's primary LLM
for a structured decision, validates the JSON, and returns it.

Decisions are cached in Redis for 5 minutes to keep LLM cost / latency under control.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import List, Optional, Sequence

import numpy as np
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai_router import chat as ai_chat
from app.services.news_service import NewsService

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

DECISION_CACHE_TTL_SECONDS = 300        # 5-minute decision lifetime
RSI_PERIOD                = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MIN_CONFIDENCE_TO_TRADE   = 60          # below this the brain says HOLD


SYSTEM_PROMPT = """You are an Indian-equity intraday/swing trading brain.
Given a market-context payload, return ONE JSON object with these keys EXACTLY:
{
  "decision":   "BUY" | "SELL" | "HOLD",
  "confidence": integer 0-100,
  "sl_pct":     float 0.5-5.0       // stop-loss percentage from entry
  "tp_pct":     float 1.0-15.0      // take-profit percentage from entry
  "qty_pct":    float 0.5-25.0      // % of capital to allocate
  "reasoning":  string <= 240 chars // why the decision was taken
}

Rules:
- Default to "HOLD" if signals are mixed or confidence < 60.
- Risk-reward must be at least 1:1.5 (tp_pct >= sl_pct * 1.5).
- Honor: bullish sentiment + strong volume + RSI 40-65 + MACD>0 → BUY candidate.
- Honor: bearish sentiment + RSI > 75 + price extended → SELL/HOLD (no shorting in delivery).
- For news-heavy events with negative impact, return HOLD even if technicals look ok.
- Return ONLY the JSON. No prose, no markdown fences.
"""


# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass
class BrainDecision:
    decision:   str         # BUY | SELL | HOLD
    confidence: int
    sl_pct:     float
    tp_pct:     float
    qty_pct:    float
    reasoning:  str
    provider:   str = "rule_fallback"
    model:      str = ""
    cached:     bool = False
    context_hash: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# ── Technicals ─────────────────────────────────────────────────────────────────

def _rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    diffs = np.diff(closes[-(period + 1):])
    gains = np.where(diffs > 0, diffs, 0).sum() / period
    losses = np.where(diffs < 0, -diffs, 0).sum() / period
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100 - 100 / (1 + rs), 1)


def _ema(series: Sequence[float], period: int) -> float:
    k = 2 / (period + 1)
    ema = series[0]
    for v in series[1:]:
        ema = v * k + ema * (1 - k)
    return ema


def _macd(closes: Sequence[float]) -> Optional[dict]:
    if len(closes) < MACD_SLOW + MACD_SIGNAL:
        return None
    fast = _ema(closes, MACD_FAST)
    slow = _ema(closes, MACD_SLOW)
    line = fast - slow
    signal_series = []
    for i in range(len(closes) - MACD_SLOW + 1):
        window = closes[: MACD_SLOW + i]
        signal_series.append(_ema(window, MACD_FAST) - _ema(window, MACD_SLOW))
    signal = _ema(signal_series[-MACD_SIGNAL:], MACD_SIGNAL) if len(signal_series) >= MACD_SIGNAL else line
    hist = line - signal
    return {"line": round(line, 3), "signal": round(signal, 3), "hist": round(hist, 3)}


# ── Context gathering ──────────────────────────────────────────────────────────

async def _recent_news_titles(db: AsyncSession, symbol: str, limit: int = 5) -> List[str]:
    """Best-effort fetch of recent news titles mentioning the symbol via news_service."""
    try:
        svc = NewsService()
        result = await svc.get_news(symbols=[symbol], limit=limit)
        articles = result.get("articles", []) if isinstance(result, dict) else (result or [])
        return [a.get("title", "") for a in articles[:limit] if a.get("title")]
    except Exception as e:
        logger.debug(f"news fetch failed for {symbol}: {e}")
        return []


def _build_context(symbol: str, closes: Sequence[float], headlines: List[str]) -> dict:
    closes = list(closes)
    last = closes[-1] if closes else 0.0
    rsi  = _rsi(closes)
    macd = _macd(closes)

    sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else None
    sma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else None

    change_1d  = round((closes[-1] / closes[-2] - 1) * 100, 2)  if len(closes) >= 2  else 0.0
    change_5d  = round((closes[-1] / closes[-6] - 1) * 100, 2)  if len(closes) >= 6  else 0.0
    change_20d = round((closes[-1] / closes[-21] - 1) * 100, 2) if len(closes) >= 21 else 0.0

    return {
        "symbol":      symbol,
        "ltp":         round(last, 2),
        "rsi":         rsi,
        "macd":        macd,
        "sma20":       round(sma20, 2) if sma20 else None,
        "sma50":       round(sma50, 2) if sma50 else None,
        "above_sma20": (last > sma20) if sma20 else None,
        "above_sma50": (last > sma50) if sma50 else None,
        "change_pct": {"d1": change_1d, "d5": change_5d, "d20": change_20d},
        "recent_news": headlines[:5],
    }


# ── Rule-based fallback (when no LLM available / LLM fails) ────────────────────

def _rule_based_decision(ctx: dict) -> BrainDecision:
    rsi = ctx.get("rsi") or 50
    macd_hist = (ctx.get("macd") or {}).get("hist", 0)
    above_sma20 = ctx.get("above_sma20")
    change_5d = ctx.get("change_pct", {}).get("d5", 0)

    confidence = 50
    decision = "HOLD"
    reasoning = "Signals mixed — staying out."

    if rsi < 35 and macd_hist > 0 and above_sma20:
        decision, confidence, reasoning = "BUY", 65, f"Oversold RSI {rsi}, MACD turning positive, above 20-SMA."
    elif rsi < 60 and macd_hist > 0.5 and above_sma20 and change_5d > 1:
        decision, confidence, reasoning = "BUY", 62, f"Healthy uptrend (RSI {rsi}, MACD+, +{change_5d}% 5d)."
    elif rsi > 75:
        decision, confidence, reasoning = "HOLD", 55, f"Overbought RSI {rsi} — wait for cool-off."

    sl_pct = 2.0
    tp_pct = 4.0
    qty_pct = 8.0 if decision == "BUY" else 0
    return BrainDecision(
        decision=decision, confidence=confidence,
        sl_pct=sl_pct, tp_pct=tp_pct, qty_pct=qty_pct,
        reasoning=reasoning, provider="rule_fallback",
    )


# ── LLM call ────────────────────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> Optional[dict]:
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if "```" in s[3:] else s.lstrip("`")
        if s.startswith("json"):
            s = s[4:]
        s = s.split("```", 1)[0]
    try:
        return json.loads(s.strip())
    except Exception:
        # Last-ditch: find first {...} block
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(s[i : j + 1])
            except Exception:
                return None
        return None


def _validate_decision(d: dict) -> BrainDecision:
    decision = str(d.get("decision", "HOLD")).upper()
    if decision not in {"BUY", "SELL", "HOLD"}:
        decision = "HOLD"

    confidence = int(max(0, min(100, d.get("confidence", 50))))
    sl_pct  = float(max(0.5, min(5.0,  d.get("sl_pct",  2.0))))
    tp_pct  = float(max(1.0, min(15.0, d.get("tp_pct",  sl_pct * 2))))
    qty_pct = float(max(0.5, min(25.0, d.get("qty_pct", 8.0))))
    reasoning = str(d.get("reasoning", ""))[:240]

    # Enforce 1:1.5 RR
    if tp_pct < sl_pct * 1.5:
        tp_pct = round(sl_pct * 1.5, 2)

    # Below confidence threshold → force HOLD
    if confidence < MIN_CONFIDENCE_TO_TRADE:
        decision = "HOLD"

    return BrainDecision(
        decision=decision, confidence=confidence,
        sl_pct=sl_pct, tp_pct=tp_pct, qty_pct=qty_pct,
        reasoning=reasoning,
    )


# ── Public API ──────────────────────────────────────────────────────────────────

_redis_pool: Optional[aioredis.Redis] = None


async def _redis() -> Optional[aioredis.Redis]:
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    try:
        url = settings.REDIS_URL or os.environ.get("REDIS_URL")
        if not url:
            return None
        _redis_pool = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
        await _redis_pool.ping()
        return _redis_pool
    except Exception as e:
        logger.debug(f"AI-brain redis unavailable, decisions will not be cached: {e}")
        return None


async def make_decision(
    db: AsyncSession,
    user_id: str,
    symbol: str,
    closes: Sequence[float],
) -> BrainDecision:
    """Return a BrainDecision for (user_id, symbol) using the user's primary LLM.

    Falls back to a rule-based decision when no AI is configured or all providers fail.
    Caches successful decisions in Redis for `DECISION_CACHE_TTL_SECONDS`.
    """
    if not closes or len(closes) < 30:
        return BrainDecision(
            decision="HOLD", confidence=0, sl_pct=2.0, tp_pct=4.0, qty_pct=0,
            reasoning="Insufficient price history.", provider="rule_fallback",
        )

    headlines = await _recent_news_titles(db, symbol)
    ctx = _build_context(symbol, closes, headlines)
    ctx_hash = f"{symbol}:{round(closes[-1], 2)}:{int(time.time() // DECISION_CACHE_TTL_SECONDS)}"

    # Cache lookup
    r = await _redis()
    if r:
        try:
            raw = await r.get(f"ai_brain:{user_id}:{ctx_hash}")
            if raw:
                cached = json.loads(raw)
                d = BrainDecision(**cached)
                d.cached = True
                return d
        except Exception as e:
            logger.debug(f"ai-brain cache read failed: {e}")

    # Build prompt
    prompt = (
        "Market context (JSON):\n"
        + json.dumps(ctx, ensure_ascii=False)
        + "\n\nReturn the JSON decision now."
    )

    decision: BrainDecision
    try:
        result = await ai_chat(db=db, user_id=user_id, prompt=prompt, system_prompt=SYSTEM_PROMPT)
        parsed = _parse_llm_response(result.get("response", ""))
        if not parsed:
            logger.info(f"ai-brain {symbol}: invalid JSON from LLM, using rule fallback")
            decision = _rule_based_decision(ctx)
        else:
            decision = _validate_decision(parsed)
            decision.provider = result.get("provider", "unknown")
            decision.model    = result.get("model", "")
    except Exception as e:
        logger.warning(f"ai-brain LLM failed for {symbol}: {e}")
        decision = _rule_based_decision(ctx)

    decision.context_hash = ctx_hash

    # Cache successful decisions only
    if r and decision.provider != "rule_fallback":
        try:
            await r.setex(
                f"ai_brain:{user_id}:{ctx_hash}",
                DECISION_CACHE_TTL_SECONDS,
                json.dumps(decision.as_dict()),
            )
        except Exception as e:
            logger.debug(f"ai-brain cache write failed: {e}")

    return decision

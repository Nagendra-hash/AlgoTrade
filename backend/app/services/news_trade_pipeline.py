"""
News-Driven Trade Pipeline — Phase 4.

Pulls fresh news impact → extracts affected stocks → pushes high-confidence,
positive-impact candidates into the AI Brain for evaluation. When AI Brain
returns a BUY decision, the candidate is sent into the auto-trade engine's
execution path the same way an ai_brain strategy would.

Designed to run inside `auto_trade_engine._tick()` once every N ticks
(default: every 10 ticks ≈ 5 min) so we don't burn LLM credits.

Path: backend/app/services/news_trade_pipeline.py
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.strategy import Strategy
from app.services.news_impact import analyze_recent

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────
NEWS_POLL_INTERVAL_SECONDS = 300   # 5 minutes between news scans
MIN_CONFIDENCE_FOR_CANDIDATE = 65  # impact confidence ≥ 65 to consider
MAX_CANDIDATES_PER_SCAN = 8        # cap so we don't flood AI Brain
DEFAULT_TIMEFRAME = "1d"


@dataclass
class NewsCandidate:
    """A single news-driven trade candidate awaiting AI Brain evaluation."""
    symbol: str
    headline: str
    source: str
    article_id: str
    impact_direction: str          # positive | negative | neutral
    confidence: int                # 0-100
    affected_sectors: List[str] = field(default_factory=list)
    opportunity_summary: str = ""
    created_at: float = field(default_factory=time.time)
    user_id: str = ""              # the user who'll evaluate this via their LLM
    status: str = "pending"        # pending | evaluated | executed | rejected
    ai_decision: Optional[dict] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class NewsTradePipeline:
    """Singleton that converts news-impact rows into AI-Brain-ready candidates."""

    def __init__(self):
        self._last_run_ts: float = 0.0
        self._candidates: Dict[str, NewsCandidate] = {}  # keyed by "user_id:symbol:article_id"
        # Track which (user_id, article_id) pairs we've already processed.
        # Prevents re-pushing the same article into the AI Brain on every scan.
        self._processed: set[str] = set()
        self._last_error: Optional[str] = None
        self._enabled: bool = True

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        logger.info(f"📰 News-trade pipeline {'enabled' if enabled else 'disabled'}")

    def should_run_now(self) -> bool:
        """True if it's been at least NEWS_POLL_INTERVAL_SECONDS since the last scan."""
        if not self._enabled:
            return False
        return (time.time() - self._last_run_ts) >= NEWS_POLL_INTERVAL_SECONDS

    def get_candidates(self, user_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Return recent candidates (optionally filtered by user)."""
        items = list(self._candidates.values())
        if user_id:
            items = [c for c in items if c.user_id == user_id]
        items.sort(key=lambda c: c.created_at, reverse=True)
        return [c.to_dict() for c in items[:limit]]

    def get_summary(self) -> dict:
        """Pipeline status snapshot for the UI."""
        items = list(self._candidates.values())
        return {
            "enabled":           self._enabled,
            "last_run_ts":       self._last_run_ts,
            "last_run_iso":      _iso(self._last_run_ts),
            "next_run_in_sec":   max(0, int(NEWS_POLL_INTERVAL_SECONDS - (time.time() - self._last_run_ts))),
            "candidates_total":  len(items),
            "pending":           sum(1 for c in items if c.status == "pending"),
            "executed":          sum(1 for c in items if c.status == "executed"),
            "rejected":          sum(1 for c in items if c.status == "rejected"),
            "last_error":        self._last_error,
        }

    async def _users_with_active_ai_brain(self) -> List[str]:
        """Return user_ids that have at least one active ai_brain strategy."""
        try:
            async with AsyncSessionLocal() as db:
                r = await db.execute(
                    select(Strategy.user_id).where(
                        Strategy.status == "active",
                        Strategy.strategy_type == "ai_brain",
                        Strategy.is_paper_active.is_(True) | Strategy.is_live_active.is_(True),
                    ).distinct()
                )
                rows = r.scalars().all()
                return [str(uid) for uid in rows]
        except Exception as e:
            logger.warning(f"news-pipeline: could not list ai_brain users: {e}")
            return []

    async def scan_and_push(self) -> dict:
        """One scan cycle. Reads news → builds candidates → enqueues for each AI-Brain user.

        Returns a small dict with stats for logging.
        """
        if not self._enabled:
            return {"skipped": "disabled"}

        self._last_run_ts = time.time()
        self._last_error = None

        users = await self._users_with_active_ai_brain()
        if not users:
            return {"users": 0, "candidates_added": 0, "reason": "no active ai_brain users"}

        added = 0
        for user_id in users:
            try:
                async with AsyncSessionLocal() as db:
                    impact = await analyze_recent(
                        limit=30, db=db, user_id=user_id, ai_top_n=4,
                    )
                items = impact.get("items", []) or []

                # Pick high-confidence positive-impact items with at least one stock
                ranked = [
                    it for it in items
                    if it.get("impact_direction") == "positive"
                    and (it.get("confidence", 0) or 0) >= MIN_CONFIDENCE_FOR_CANDIDATE
                    and it.get("affected_stocks")
                ]
                ranked.sort(key=lambda it: it.get("confidence", 0), reverse=True)
                ranked = ranked[:MAX_CANDIDATES_PER_SCAN]

                for it in ranked:
                    article_id = it.get("id") or ""
                    article_key = f"{user_id}:{article_id}"
                    if article_key in self._processed:
                        continue
                    self._processed.add(article_key)
                    for sym in (it.get("affected_stocks") or [])[:3]:
                        sym = str(sym).upper().strip()
                        if not sym:
                            continue
                        key = f"{user_id}:{sym}:{article_id}"
                        if key in self._candidates:
                            continue
                        cand = NewsCandidate(
                            symbol=sym,
                            headline=it.get("headline", "")[:240],
                            source=it.get("source", ""),
                            article_id=article_id,
                            impact_direction=it.get("impact_direction", "neutral"),
                            confidence=int(it.get("confidence", 0) or 0),
                            affected_sectors=list(it.get("affected_sectors", []) or [])[:5],
                            opportunity_summary=(it.get("opportunity_summary") or "")[:240],
                            user_id=user_id,
                        )
                        self._candidates[key] = cand
                        added += 1
            except Exception as e:
                self._last_error = f"{e.__class__.__name__}: {e}"
                logger.warning(f"news-pipeline scan failed for user {user_id[:8]}: {e}")

        # Trim memory if dict grows too large (keep newest 500)
        if len(self._candidates) > 500:
            keep = sorted(self._candidates.items(), key=lambda kv: kv[1].created_at, reverse=True)[:500]
            self._candidates = dict(keep)

        logger.info(f"📰 News-pipeline scan: users={len(users)} candidates_added={added}")
        return {"users": len(users), "candidates_added": added}

    def pop_pending_for_user(self, user_id: str, limit: int = 5) -> List[NewsCandidate]:
        """Return up-to `limit` pending candidates for a user and mark them in-flight."""
        out: List[NewsCandidate] = []
        for c in self._candidates.values():
            if c.user_id == user_id and c.status == "pending":
                out.append(c)
                if len(out) >= limit:
                    break
        return out

    def mark_executed(self, candidate: NewsCandidate, decision: dict) -> None:
        candidate.status = "executed"
        candidate.ai_decision = decision

    def mark_rejected(self, candidate: NewsCandidate, reason: str, decision: Optional[dict] = None) -> None:
        candidate.status = "rejected"
        candidate.rejection_reason = reason
        candidate.ai_decision = decision

    def reset(self) -> None:
        """Clear all candidates (admin action)."""
        self._candidates.clear()
        self._processed.clear()
        self._last_error = None
        logger.info("📰 News-pipeline reset")


def _iso(ts: float) -> Optional[str]:
    if not ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# Singleton instance
news_trade_pipeline = NewsTradePipeline()

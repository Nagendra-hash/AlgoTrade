"""
Alert Engine — background task that polls market prices every 15s and fires alerts.
Path: backend/app/services/alert_engine.py

Data sources (in priority order):
  1. Yahoo Finance v8 REST API (replaces deprecated yfinance)
"""
import asyncio
import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
from sqlalchemy import select, update, cast, String, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.redis import redis_publish
from app.models.alert import Alert, AlertStatus, AlertCondition, Notification
from app.models.user import User
from app.websockets.notification_ws import notification_manager
from app.services.telegram_service import notify_alert_triggered
from app.services.news_service import news_service
from app.services.sentiment_service import sentiment_service

logger = logging.getLogger(__name__)

NSE_TO_YF = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "WIPRO": "WIPRO.NS", "BAJFINANCE": "BAJFINANCE.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "ADANIENT": "ADANIENT.NS", "HINDUNILVR": "HINDUNILVR.NS", "MARUTI": "MARUTI.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK",
}

_price_cache: dict = {}
_cache_time: dict = {}


def _fetch_price_sync(yf_symbol: str) -> Optional[dict]:
    """
    Fetch price data from Yahoo Finance v8 REST API.
    Replaces deprecated yfinance library.
    """
    yf_base = "https://query1.finance.yahoo.com/v8/finance/chart"
    yf_headers = {"User-Agent": "Mozilla/5.0"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{yf_base}/{yf_symbol}?interval=1d&range=5d",
                headers=yf_headers,
            )
            resp.raise_for_status()
            data = resp.json()

        result = data["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]

        ltp = float(meta.get("regularMarketPrice", 0) or 0)
        prev = float(meta.get("chartPreviousClose", ltp) or ltp)

        # Extract OHLCV data for RSI calculation
        closes = [c for c in (quotes.get("close") or []) if c is not None]
        volumes = [v for v in (quotes.get("volume") or []) if v is not None]
        volume = int(volumes[-1]) if volumes else 0

        change_pct = ((ltp - prev) / prev * 100) if prev else 0

        # Calculate RSI from close prices
        rsi = None
        if len(closes) >= 14:
            import pandas as pd
            s = pd.Series(closes, dtype=float)
            delta = s.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi_series = 100 - (100 / (1 + rs))
            if not rsi_series.empty:
                rsi = float(rsi_series.iloc[-1])

        return {
            "ltp": ltp,
            "prev_close": prev,
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "rsi": rsi,
        }
    except Exception as e:
        logger.error(f"Price fetch error {yf_symbol}: {e}")
        return None


async def fetch_market_data(symbol: str) -> Optional[dict]:
    now = datetime.now()
    cached_at = _cache_time.get(symbol)
    if cached_at and (now - cached_at).seconds < 20:
        return _price_cache.get(symbol)

    yf_sym = NSE_TO_YF.get(symbol.upper(), symbol.upper() + ".NS")
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_price_sync, yf_sym)
    if data:
        _price_cache[symbol] = data
        _cache_time[symbol] = now
    return data


def _check_condition(alert: Alert, market: dict) -> tuple[bool, str]:
    ltp = market.get("ltp", 0)
    change_pct = market.get("change_pct", 0)
    volume = market.get("volume", 0)
    rsi = market.get("rsi")
    target = alert.target_value
    condition = alert.condition if isinstance(alert.condition, str) else alert.condition.value

    if condition == AlertCondition.ABOVE.value:
        if ltp >= target:
            return True, f"{alert.symbol} is ABOVE ₹{target:,.2f} — Current: ₹{ltp:,.2f}"

    elif condition == AlertCondition.BELOW.value:
        if ltp <= target:
            return True, f"{alert.symbol} is BELOW ₹{target:,.2f} — Current: ₹{ltp:,.2f}"

    elif condition == AlertCondition.PERCENT_CHANGE.value:
        if abs(change_pct) >= abs(target):
            direction = "up" if change_pct > 0 else "down"
            return True, f"{alert.symbol} moved {direction} {abs(change_pct):.2f}% (threshold: {target}%)"

    elif condition == AlertCondition.VOLUME_SPIKE.value:
        avg_vol = market.get("avg_volume", volume)
        if avg_vol > 0 and volume >= avg_vol * target:
            return True, f"{alert.symbol} volume spike: {volume:,} ({target}× average)"

    elif condition == AlertCondition.RSI_OVERBOUGHT.value:
        if rsi is not None and rsi >= target:
            return True, f"{alert.symbol} RSI overbought: {rsi:.1f} ≥ {target}"

    elif condition == AlertCondition.RSI_OVERSOLD.value:
        if rsi is not None and rsi <= target:
            return True, f"{alert.symbol} RSI oversold: {rsi:.1f} ≤ {target}"

    elif condition == AlertCondition.NEWS_MENTION.value:
        # Handled separately in run_alert_cycle via news service
        pass

    elif condition == AlertCondition.SENTIMENT_ABOVE.value:
        sent = market.get("sentiment_score", 0)
        if sent >= target:
            return True, f"{alert.symbol} sentiment BULLISH ({sent}) — threshold: {target}"

    elif condition == AlertCondition.SENTIMENT_BELOW.value:
        sent = market.get("sentiment_score", 0)
        if sent <= target:
            return True, f"{alert.symbol} sentiment BEARISH ({sent}) — threshold: {target}"

    return False, ""


async def _fire_alert(db: AsyncSession, alert: Alert, message: str, market: dict) -> None:
    now = datetime.now(timezone.utc)

    if alert.triggered_at and not alert.is_repeating:
        return
    if alert.triggered_at and alert.is_repeating:
        if (now - alert.triggered_at) < timedelta(minutes=alert.repeat_interval_minutes):
            return

    notif = Notification(
        user_id=alert.user_id,
        alert_id=alert.id,
        title=f"🔔 Alert: {alert.symbol}",
        message=message,
        symbol=alert.symbol,
        notification_type="alert",
        data={
            "ltp": market.get("ltp"),
            "change_pct": market.get("change_pct"),
            "condition": str(alert.condition),
            "target": alert.target_value,
        },
    )
    db.add(notif)

    new_status = AlertStatus.ACTIVE.value if alert.is_repeating else AlertStatus.TRIGGERED.value
    await db.execute(
        update(Alert)
        .where(Alert.id == alert.id)
        .values(
            status=new_status,
            triggered_at=now,
            trigger_count=alert.trigger_count + 1,
            current_value=market.get("ltp"),
        )
    )
    await db.flush()

    payload = {
        "type": "alert_triggered",
        "data": {
            "id": str(notif.id),
            "title": notif.title,
            "message": message,
            "symbol": alert.symbol,
            "ltp": market.get("ltp"),
            "change_pct": market.get("change_pct"),
            "created_at": now.isoformat(),
        },
    }
    await notification_manager.send_to_user(str(alert.user_id), payload)
    await redis_publish(f"notifications:{alert.user_id}", payload)

    # Send Telegram notification if channel is configured
    channels = alert.channels if isinstance(alert.channels, list) else []
    if "telegram" in channels:
        try:
            r = await db.execute(
                select(User).where(User.id == alert.user_id)
            )
            user = r.scalar_one_or_none()
            if user and user.telegram_bot_token and user.telegram_chat_id:
                await notify_alert_triggered(
                    bot_token=user.telegram_bot_token,
                    chat_id=user.telegram_chat_id,
                    symbol=alert.symbol,
                    message=message,
                    ltp=market.get("ltp"),
                )
        except Exception as e:
            logger.warning(f"Telegram alert send failed for user {alert.user_id}: {e}")

    logger.info(f"Alert fired: {message}")


async def run_alert_cycle() -> None:
    async with AsyncSessionLocal() as db:
        try:
            # Use cast(Alert.status, String) to avoid asyncpg type cast issues
            result = await db.execute(
                select(Alert).filter(
                    text("alerts.status = 'active'")
                )
            )
            alerts: List[Alert] = result.scalars().all()
            if not alerts:
                return

            symbols = list({a.symbol for a in alerts})
            tasks = [fetch_market_data(s) for s in symbols]
            prices_list = await asyncio.gather(*tasks, return_exceptions=True)
            price_map = {
                sym: p for sym, p in zip(symbols, prices_list)
                if isinstance(p, dict) and p
            }

            for alert in alerts:
                if alert.condition in (AlertCondition.NEWS_MENTION.value, AlertCondition.SENTIMENT_ABOVE.value, AlertCondition.SENTIMENT_BELOW.value):
                    # News mention alerts don't use price data
                    await db.execute(
                        update(Alert).where(Alert.id == alert.id)
                        .values(last_checked_at=datetime.now(timezone.utc))
                    )
                    news_sources = alert.news_sources if isinstance(alert.news_sources, list) else []
                    if not news_sources:
                        continue
                    if alert.condition == AlertCondition.NEWS_MENTION.value:
                        news_check = await news_service.check_symbol_news_mention(
                            symbol=alert.symbol,
                            sources=news_sources,
                            max_age_minutes=60,
                        )
                        if news_check.get("mentioned"):
                            headline = news_check.get("latest_headline", "")
                            source = news_check.get("latest_source", "")
                            message = f"{alert.symbol} mentioned in {source}: \"{headline}\""
                            mock_market = {"ltp": 0, "change_pct": 0}
                            await _fire_alert(db, alert, message, mock_market)
                    elif alert.condition in (AlertCondition.SENTIMENT_ABOVE.value, AlertCondition.SENTIMENT_BELOW.value):
                        sentiment_data = await sentiment_service.get_sentiment(
                            symbol=alert.symbol,
                            exchange=alert.exchange,
                            force_refresh=True,
                        )
                        sent_score = sentiment_data.get("score", 0)
                        sent_label = sentiment_data.get("label", "neutral")
                        sent_market = {"ltp": 0, "change_pct": 0, "sentiment_score": sent_score}
                        triggered, message = _check_condition(alert, sent_market)
                        if triggered:
                            await _fire_alert(db, alert, message, sent_market)
                    continue

                market = price_map.get(alert.symbol)
                if not market:
                    continue
                if alert.expires_at and datetime.now(timezone.utc) > alert.expires_at:
                    await db.execute(
                        update(Alert).where(Alert.id == alert.id)
                        .values(status=AlertStatus.EXPIRED.value)
                    )
                    continue
                await db.execute(
                    update(Alert).where(Alert.id == alert.id)
                    .values(last_checked_at=datetime.now(timezone.utc), current_value=market.get("ltp"))
                )
                triggered, message = _check_condition(alert, market)
                if triggered:
                    await _fire_alert(db, alert, message, market)

            await db.commit()
        except Exception as e:
            logger.error(f"Alert cycle error: {e}", exc_info=True)
            await db.rollback()


class AlertEngine:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Alert engine started (interval={settings.ALERT_CHECK_INTERVAL_SECONDS}s)")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Alert engine stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _loop(self) -> None:
        while self._running:
            try:
                await run_alert_cycle()
            except Exception as e:
                logger.error(f"Alert engine loop: {e}")
            await asyncio.sleep(settings.ALERT_CHECK_INTERVAL_SECONDS)


alert_engine = AlertEngine()

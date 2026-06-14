"""
Telegram notification service — sends trade alerts and execution notifications
to a user's Telegram chat via the Bot API.

Path: backend/app/services/telegram_service.py
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot"


async def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send a message to a Telegram chat using the Bot API.

    Args:
        bot_token: Telegram Bot API token (from @BotFather)
        chat_id: Chat ID to send the message to
        text: Message text (HTML formatting supported)
        parse_mode: 'HTML' or 'MarkdownV2'

    Returns:
        True if sent successfully, False otherwise
    """
    if not bot_token or not chat_id:
        logger.debug("Telegram not configured — skipping message")
        return False

    url = f"{TELEGRAM_API}{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()

            if data.get("ok"):
                logger.debug(f"Telegram message sent to chat {chat_id}")
                return True
            else:
                logger.warning(
                    f"Telegram API error: {data.get('description', 'unknown')} "
                    f"(code: {data.get('error_code', '?')})"
                )
                return False
    except httpx.TimeoutException:
        logger.warning("Telegram API timeout")
        return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


async def notify_alert_triggered(
    bot_token: str,
    chat_id: str,
    symbol: str,
    message: str,
    ltp: Optional[float] = None,
) -> bool:
    """Send a formatted alert notification."""
    text = (
        f"🔔 <b>Alert: {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{message}\n"
    )
    if ltp:
        text += f"\nLTP: ₹{ltp:,.2f}"
    text += "\n\nTradeAI — Market Alerts"

    return await send_telegram_message(bot_token, chat_id, text)

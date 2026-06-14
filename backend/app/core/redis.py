"""
Redis connection and helpers using modern redis[asyncio].
Path: backend/app/core/redis.py
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def redis_get(key: str) -> Optional[Any]:
    try:
        r = await get_redis()
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        logger.error(f"Redis GET {key}: {e}")
        return None


async def redis_set(key: str, value: Any, ttl: int = 300) -> bool:
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.error(f"Redis SET {key}: {e}")
        return False


async def redis_delete(key: str) -> bool:
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis DELETE {key}: {e}")
        return False


async def redis_publish(channel: str, message: Any) -> None:
    try:
        r = await get_redis()
        await r.publish(channel, json.dumps(message, default=str))
    except Exception as e:
        logger.error(f"Redis PUBLISH {channel}: {e}")

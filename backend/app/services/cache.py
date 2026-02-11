"""
# cache.py - Redis Cache Service
# Version: 0.2.0
# Description: Redis 기반 캐시 (검색 결과, 타임라인 데이터)
# - 연결 실패 시 graceful degradation (캐시 없이 동작)
"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: Optional[aioredis.Redis] = None
_redis_available: bool = True


async def get_redis() -> aioredis.Redis:
    """Redis 클라이언트 싱글톤"""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
    return _redis


async def cache_get(key: str) -> Optional[Any]:
    """캐시 조회 (Redis 실패 시 None 반환)"""
    global _redis_available
    if not _redis_available:
        return None
    try:
        r = await get_redis()
        value = await r.get(key)
        if value:
            _redis_available = True
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning(f"Cache get failed for {key}: {e}")
        _redis_available = False
        return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    """캐시 저장 (Redis 실패 시 무시)"""
    global _redis_available
    if not _redis_available:
        return
    try:
        r = await get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
        _redis_available = True
    except Exception as e:
        logger.warning(f"Cache set failed for {key}: {e}")
        _redis_available = False


async def cache_delete(key: str) -> None:
    """캐시 삭제 (Redis 실패 시 무시)"""
    global _redis_available
    if not _redis_available:
        return
    try:
        r = await get_redis()
        await r.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")
        _redis_available = False

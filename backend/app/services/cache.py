"""
# cache.py - Redis Cache Service
# Version: 0.5.0
# Description: Redis 기반 캐시 (검색 결과, 타임라인 데이터)
# - 연결 실패 시 graceful degradation (캐시 없이 동작)
# - Celery 워커 이벤트 루프 변경 시 자동 재연결
# Changes:
#   - 0.5.0: is_redis_available() 헬스 체크 추가
#   - 0.4.0: invalidate_all_trend_caches(), distributed lock 추가
"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: Optional[aioredis.Redis] = None
_redis_available: bool = True  # Redis 가용성 플래그


def _reset_redis() -> None:
    """Redis 연결 리셋 (이벤트 루프 변경 시 호출)"""
    global _redis
    _redis = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Redis 클라이언트 (이벤트 루프 변경 시 자동 재연결, 실패 시 None)"""
    global _redis, _redis_available
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
            )
            _redis_available = True
        except Exception as e:
            logger.warning(f"Redis 연결 실패: {e}")
            _redis_available = False
            return None
    return _redis


async def is_redis_available() -> bool:
    """Redis 헬스 체크"""
    try:
        client = await get_redis()
        if client is None:
            return False
        await client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis 헬스 체크 실패: {e}")
        return False


async def _exec_redis(op_name: str, fn):
    """Redis 작업 실행 + 이벤트 루프 변경 시 자동 재연결 (graceful degradation)"""
    global _redis
    try:
        redis_client = await get_redis()
        if redis_client is None:
            return None
        return await fn(redis_client)
    except RuntimeError as e:
        if "Event loop is closed" in str(e) or "attached to a different loop" in str(e):
            logger.info(f"Redis reconnecting ({op_name}): {e}")
            _reset_redis()
            try:
                redis_client = await get_redis()
                if redis_client is None:
                    return None
                return await fn(redis_client)
            except Exception as retry_e:
                logger.warning(f"Redis retry failed ({op_name}): {retry_e}")
                return None
        raise
    except Exception as e:
        logger.warning(f"Redis {op_name} failed: {e}")
        return None


async def cache_get(key: str) -> Optional[Any]:
    """캐시 조회 (Redis 실패 시 None 반환)"""
    result = await _exec_redis(
        f"get:{key}",
        lambda r: r.get(key),
    )
    if result:
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    """캐시 저장 (Redis 실패 시 무시)"""
    await _exec_redis(
        f"set:{key}",
        lambda r: r.set(key, json.dumps(value, default=str), ex=ttl),
    )


async def publish_event(channel: str, data: Any) -> None:
    """Redis Pub/Sub 이벤트 발행"""
    await _exec_redis(
        f"publish:{channel}",
        lambda r: r.publish(channel, json.dumps(data, default=str)),
    )


async def cache_delete(key: str) -> None:
    """캐시 삭제 (Redis 실패 시 무시)"""
    await _exec_redis(
        f"delete:{key}",
        lambda r: r.delete(key),
    )


CRAWL_STATUS_KEY = "crawl:status"
CRAWL_STATUS_TTL = 2100  # 35분 (Beat 주기 30분 + 여유)


async def set_crawl_status(phase: str, detail: str | None = None) -> None:
    """크롤링 파이프라인 상태 기록 + SSE 이벤트 발행"""
    from datetime import datetime, timezone

    status = {
        "phase": phase,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    }
    await cache_set(CRAWL_STATUS_KEY, status, ttl=CRAWL_STATUS_TTL)
    await publish_event("stats_updated", {"type": "crawl_status", **status})


async def get_crawl_status() -> dict:
    """현재 크롤링 상태 조회"""
    status = await cache_get(CRAWL_STATUS_KEY)
    if status:
        return status
    return {"phase": "idle", "started_at": None, "detail": None}


async def invalidate_all_trend_caches() -> None:
    """트렌드 관련 모든 캐시 무효화 (크롤링 완료 후 호출)"""
    cache_keys = [
        "trends:stats",
        "trends:hot:24h",
        "trends:hot:7d",
        "trends:hot:30d",
        "trends:popular",
        "trends:article-clusters:24h:1",
        "trends:article-clusters:24h:2",
        "trends:article-clusters:7d:1",
        "trends:article-clusters:7d:2",
        "trends:article-clusters:30d:1",
        "trends:article-clusters:30d:2",
        "trends:recent-articles:30:all",
        "trends:compare:24h:7d",
        "trends:compare:24h:30d",
        "trends:compare:7d:24h",
        "trends:compare:7d:30d",
        "trends:compare:30d:24h",
        "trends:compare:30d:7d",
    ]
    for key in cache_keys:
        await cache_delete(key)


async def acquire_task_lock(task_name: str, timeout: int) -> bool:
    """
    분산 태스크 락 획득 (Redis SET NX EX)

    Args:
        task_name: 태스크 식별자
        timeout: 락 타임아웃 (초)

    Returns:
        True if lock acquired, False if already locked
    """
    lock_key = f"task:lock:{task_name}"
    result = await _exec_redis(
        f"set_nx:{lock_key}",
        lambda r: r.set(lock_key, "1", nx=True, ex=timeout),
    )
    return bool(result)


async def release_task_lock(task_name: str) -> None:
    """분산 태스크 락 해제"""
    lock_key = f"task:lock:{task_name}"
    await cache_delete(lock_key)

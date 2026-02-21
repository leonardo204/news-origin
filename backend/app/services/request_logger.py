"""
# request_logger.py - Async Batch Request Log Writer
# Version: 0.1.0
# Description: HTTP 요청 로그를 비동기 배치로 DB에 저장
"""

import asyncio
import ipaddress
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# 로깅 제외 경로 (정확 일치)
_EXCLUDED_PATHS = frozenset({
    "/favicon.ico",
})

# 제외 접두사 — 관리자/내부 트래픽은 수집 불필요
_EXCLUDED_PREFIXES = ("/api/health", "/api/admin/", "/assets/")


def _is_private_ip(ip_str: str | None) -> bool:
    """사설/내부 IP 여부 확인 (Docker 네트워크, 로컬호스트 등)"""
    if not ip_str:
        return True
    try:
        addr = ipaddress.ip_address(ip_str)
        return addr.is_private or addr.is_loopback or addr.is_reserved
    except (ValueError, TypeError):
        return False


class RequestLogWriter:
    """인메모리 큐 → 5초/50건마다 DB 일괄 INSERT"""

    def __init__(self, flush_interval: float = 5.0, flush_size: int = 50):
        self._queue: deque[dict[str, Any]] = deque(maxlen=10_000)
        self._flush_interval = flush_interval
        self._flush_size = flush_size
        self._task: asyncio.Task | None = None
        self._running = False

    def enqueue(self, entry: dict[str, Any]) -> None:
        """O(1) 비차단 적재. 경로/IP 필터링 포함."""
        path = entry.get("path", "")
        if path in _EXCLUDED_PATHS:
            return
        if any(path.startswith(p) for p in _EXCLUDED_PREFIXES):
            return
        # 사설 IP(Docker 내부, 로컬호스트) 제외 — 실 사용자만 수집
        if _is_private_ip(entry.get("client_ip")):
            return
        self._queue.append(entry)

    def start(self) -> None:
        """백그라운드 flush 루프 시작"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("RequestLogWriter started")

    async def stop(self) -> None:
        """남은 로그 flush 후 종료"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # 잔여 로그 최종 flush
        if self._queue:
            await self._flush()
        logger.info("RequestLogWriter stopped")

    async def _flush_loop(self) -> None:
        """주기적으로 큐를 drain하여 DB에 저장"""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._queue:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"RequestLogWriter flush error: {e}")

    async def _flush(self) -> None:
        """큐에서 drain → DB 일괄 INSERT"""
        batch: list[dict[str, Any]] = []
        while self._queue and len(batch) < self._flush_size * 2:
            batch.append(self._queue.popleft())

        if not batch:
            return

        try:
            from app.models.base import async_session_factory
            from app.models.request_log import RequestLog

            async with async_session_factory() as session:
                objects = [
                    RequestLog(
                        id=uuid.uuid4(),
                        method=entry["method"],
                        path=entry["path"],
                        status_code=entry["status_code"],
                        duration_ms=entry["duration_ms"],
                        client_ip=entry.get("client_ip"),
                        user_agent=entry.get("user_agent"),
                        created_at=entry.get("created_at", datetime.now(timezone.utc)),
                    )
                    for entry in batch
                ]
                session.add_all(objects)
                await session.commit()
        except Exception as e:
            logger.warning(f"RequestLogWriter DB insert failed ({len(batch)} entries): {e}")


# 모듈 레벨 싱글턴
request_log_writer = RequestLogWriter()

"""
# logging_config.py - Structured Logging Configuration
# Version: 0.1.0
# Description: JSON 형식 로깅, 요청 ID 트레이싱 (correlation_id)
"""

import logging
import sys
import uuid
from typing import Optional

from pythonjsonlogger import jsonlogger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# 요청 컨텍스트 저장 (thread-safe)
import contextvars

request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON 로그 포맷터 - request_id, timestamp, level, message 포함"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # 기본 필드
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["message"] = record.getMessage()

        # 요청 ID 추가 (미들웨어에서 설정됨)
        req_id = request_id_var.get()
        if req_id:
            log_record["request_id"] = req_id

        # 추가 컨텍스트 (extra로 전달된 필드)
        if hasattr(record, "method"):
            log_record["method"] = record.method
        if hasattr(record, "path"):
            log_record["path"] = record.path
        if hasattr(record, "status_code"):
            log_record["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms


def setup_logging(log_level: str = "INFO"):
    """구조화된 로깅 설정 (JSON 포맷)"""
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers = [handler]  # 기존 핸들러 제거

    # uvicorn 로거도 JSON 포맷 적용
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.propagate = False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """요청 ID 트레이싱 미들웨어 - 모든 로그에 request_id 자동 추가"""

    async def dispatch(self, request: Request, call_next):
        # X-Request-ID 헤더에서 가져오거나 신규 생성
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(request_id)

        import time
        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger = logging.getLogger("news-origin")
            logger.error(
                f"{request.method} {request.url.path} - unhandled exception",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 1),
                },
                exc_info=True,
            )
            raise

        duration_ms = (time.monotonic() - start) * 1000

        # 응답 로그
        logger = logging.getLogger("news-origin")
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            f"{request.method} {request.url.path} {response.status_code}",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )

        # 응답 헤더에 request_id 추가
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"

        return response

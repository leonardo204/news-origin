"""
# main.py - FastAPI Application Entrypoint
# Version: 0.2.0
# Description: 앱 초기화, 미들웨어, 에러 핸들링, DB 초기화
"""

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.limiter import limiter
from app.api.routes import articles, search, timeline, trends

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("news-origin")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """요청/응답 로깅 및 X-Request-ID 헤더 추가"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} 500 ({duration_ms:.0f}ms) - unhandled exception"
            )
            raise

        duration_ms = (time.monotonic() - start) * 1000
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            f"[{request_id}] {request.method} {request.url.path} {response.status_code} ({duration_ms:.0f}ms)"
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 초기화/정리"""
    settings = get_settings()
    logger.info(f"Starting News Origin API (env={settings.app_env})")

    # DB 테이블 자동 생성 (개발 환경)
    if settings.app_env == "development":
        try:
            from app.models.base import engine, Base
            from app.models import Article, TrackingRequest, TimelineEntry, SearchLog  # noqa: F401

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.warning(f"Could not auto-create DB tables: {e}")

    # Qdrant 컬렉션 초기화
    try:
        from app.services.vector_store import ensure_collection
        await ensure_collection()
        logger.info("Qdrant collection verified")
    except Exception as e:
        logger.warning(f"Could not initialize Qdrant: {e}")

    yield

    logger.info("Shutting down News Origin API")


settings = get_settings()

tags_metadata = [
    {"name": "health", "description": "서비스 상태 확인"},
    {"name": "articles", "description": "기사 추적 및 조회"},
    {"name": "search", "description": "뉴스 검색"},
    {"name": "timeline", "description": "타임라인 및 추적 상태"},
    {"name": "trends", "description": "트렌드 및 통계"},
]

app = FastAPI(
    title="News Origin API",
    description="뉴스 기사 출처 추적 및 전파 타임라인 분석 서비스",
    version="0.2.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request logging (outermost → runs first)
app.add_middleware(RequestLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"[{request_id}] Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다.", "request_id": request_id},
    )


# Routers - /api prefix (v1 제거하여 프론트엔드 프록시와 일치)
app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(timeline.router, prefix="/api/timeline", tags=["timeline"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])


@app.get("/api/health", tags=["health"])
async def health_check():
    """서비스 상태 확인 (DB, Redis, Qdrant)"""
    checks = {}

    # Database
    try:
        from app.models.base import async_session_factory
        async with async_session_factory() as session:
            await session.execute(sa.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"

    # Redis
    try:
        from app.services.cache import get_redis
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"

    # Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {str(e)[:100]}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"

    return {
        "status": overall,
        "service": "news-origin",
        "version": "0.2.0",
        "checks": checks,
    }

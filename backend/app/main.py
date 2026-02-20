"""
# main.py - FastAPI Application Entrypoint
# Version: 0.5.0
# Description: 앱 초기화, 미들웨어, 에러 핸들링, DB 초기화
# Changes:
#   - 0.3.0: 구조화된 JSON 로깅 적용, 요청 ID 트레이싱
#   - 0.4.0: RFC 7807 Problem Details 에러 응답 표준화
#   - 0.5.0: /api/health/embeddings 임베딩 품질 모니터링 엔드포인트 추가
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
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.limiter import limiter
from app.core.logging_config import setup_logging, RequestContextMiddleware
from app.api.routes import admin, articles, search, timeline, trends
from app.api.errors import (
    APIError,
    api_error_handler,
    validation_error_handler,
    generic_error_handler,
)

# Structured logging setup
settings = get_settings()
setup_logging(log_level="INFO")
admin.init_log_handler()  # setup_logging 이후 메모리 로그 핸들러 설치
logger = logging.getLogger("news-origin")


# RequestLoggingMiddleware는 core.logging_config.RequestContextMiddleware로 대체됨


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 초기화/정리"""
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

    # Clean up stuck "processing" trackings from previous crashes
    try:
        from datetime import datetime, timedelta, timezone
        from app.models.timeline import TrackingRequest as TR

        async with engine.begin() as conn:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            await conn.execute(
                sa.update(TR.__table__)
                .where(TR.status == "processing", TR.created_at < stale_cutoff)
                .values(status="error", error_message="서버 재시작으로 중단되었습니다.")
            )
        logger.info("Cleaned up stale processing trackings")
    except Exception as e:
        logger.warning(f"Could not clean up stale trackings: {e}")

    # Qdrant 컬렉션 초기화
    try:
        from app.services.vector_store import ensure_collection
        await ensure_collection()
        logger.info("Qdrant collection verified")
    except Exception as e:
        logger.warning(f"Could not initialize Qdrant: {e}")

    yield

    logger.info("Shutting down News Origin API")


tags_metadata = [
    {"name": "health", "description": "서비스 상태 확인"},
    {"name": "articles", "description": "기사 추적 및 조회"},
    {"name": "search", "description": "뉴스 검색"},
    {"name": "timeline", "description": "타임라인 및 추적 상태"},
    {"name": "trends", "description": "트렌드 및 통계"},
    {"name": "admin", "description": "관리자 대시보드 API"},
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

# Error handlers - RFC 7807 Problem Details
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Request logging with context (outermost → runs first)
app.add_middleware(RequestContextMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers - /api prefix (v1 제거하여 프론트엔드 프록시와 일치)
app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(timeline.router, prefix="/api/timeline", tags=["timeline"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/api/health/embeddings", tags=["health"])
async def health_embeddings():
    """임베딩 품질 통계 (DB vs Qdrant 정합성 확인, 5분 캐시)"""
    cache_key = "health:embeddings"

    try:
        from app.services.cache import cache_get, cache_set
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    result: dict = {}

    # DB 통계
    try:
        from app.models.base import async_session_factory
        from app.models.article import Article as ArticleModel
        from sqlalchemy import select, func

        async with async_session_factory() as session:
            row = await session.execute(
                select(
                    func.count(ArticleModel.id).label("total"),
                    func.count(ArticleModel.qdrant_point_id).label("embedded"),
                )
            )
            stats = row.one()
            total_articles = stats.total or 0
            embedded_articles = stats.embedded or 0
    except Exception as e:
        logger.warning(f"Embedding health DB query failed: {e}")
        total_articles = -1
        embedded_articles = -1

    embedding_rate = (
        round(embedded_articles / total_articles * 100, 1)
        if total_articles > 0 else 0.0
    )

    # Qdrant 컬렉션 벡터 수
    qdrant_count = -1
    try:
        from app.services.vector_store import get_qdrant_client
        from app.config import get_settings as _get_settings
        client = get_qdrant_client()
        if client is not None:
            _settings = _get_settings()
            info = client.get_collection(_settings.qdrant_collection)
            qdrant_count = info.vectors_count if info.vectors_count is not None else 0
    except Exception as e:
        logger.warning(f"Embedding health Qdrant query failed: {e}")

    mismatch = (
        qdrant_count != embedded_articles
        if qdrant_count >= 0 and embedded_articles >= 0
        else None
    )

    result = {
        "total_articles": total_articles,
        "embedded_articles": embedded_articles,
        "embedding_rate": embedding_rate,
        "qdrant_collection_count": qdrant_count,
        "mismatch": mismatch,
    }

    try:
        from app.services.cache import cache_set
        await cache_set(cache_key, result, ttl=300)  # 5 minutes
    except Exception:
        pass

    return result


@app.get("/api/health", tags=["health"])
async def health_check():
    """서비스 상태 확인 (DB, Redis, Qdrant) - graceful degradation 지원"""
    services = {}

    # Database (필수 서비스)
    try:
        from app.models.base import async_session_factory
        async with async_session_factory() as session:
            await session.execute(sa.text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        services["database"] = "degraded"
        logger.error(f"Database health check failed: {e}")

    # Redis (선택적 서비스 - 캐시)
    try:
        from app.services.cache import is_redis_available
        redis_ok = await is_redis_available()
        services["redis"] = "ok" if redis_ok else "degraded"
    except Exception as e:
        services["redis"] = "degraded"
        logger.warning(f"Redis health check failed: {e}")

    # Qdrant (선택적 서비스 - 벡터 검색)
    try:
        from app.services.vector_store import is_qdrant_available
        qdrant_ok = await is_qdrant_available()
        services["qdrant"] = "ok" if qdrant_ok else "degraded"
    except Exception as e:
        services["qdrant"] = "degraded"
        logger.warning(f"Qdrant health check failed: {e}")

    # 전체 상태: DB가 OK면 healthy, 아니면 unhealthy
    overall = "healthy" if services["database"] == "ok" else "unhealthy"

    return {
        "status": overall,
        "service": "news-origin",
        "version": "0.3.0",
        "services": services,
    }

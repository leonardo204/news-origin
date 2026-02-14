"""
# articles.py - Article API Routes
# Version: 0.3.0
# Description: 기사 추적 요청, 확인, 상세 조회 API
# Changes:
#   - 0.3.0: 메타데이터 기반 빠른 기사 생성 + 검색 결과 Redis 캐싱
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.limiter import limiter
from app.models.article import Article
from app.models.timeline import TrackingRequest
from app.models.search_log import SearchLog
from app.schemas.article import ArticleResponse
from app.schemas.timeline import (
    TrackInput,
    TrackResponse,
    TrackCandidate,
    ConfirmInput,
    ConfirmResponse,
)
from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

router = APIRouter()

_celery_app_cache = None


def _get_celery_app():
    """Celery app을 지연 로딩 (첫 호출 시 1회만 import, 이후 캐시)"""
    global _celery_app_cache
    if _celery_app_cache is None:
        from app.workers.celery_app import celery_app
        _celery_app_cache = celery_app
    return _celery_app_cache

URL_PATTERN = re.compile(r"^https?://")


def _is_poor_metadata(value: str | None) -> bool:
    """메타데이터가 유효하지 않은지 확인"""
    if not value:
        return True
    lower = str(value).lower().strip()
    return lower in ("", "google news", "news.google.com") or "google.com" in lower


def _parse_date_str(date_str: str | None) -> datetime | None:
    """날짜 문자열을 datetime으로 변환 (UTC-aware로 통일)"""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        pass
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


@router.post(
    "/track",
    response_model=TrackResponse,
    summary="기사 추적 요청",
    description="URL 또는 제목으로 기사를 검색하여 추적을 시작합니다. URL 입력 시 바로 크롤링하여 기사 정보를 반환하고, 제목 입력 시 검색하여 후보 기사 목록을 반환합니다.",
    responses={
        404: {"description": "기사를 크롤링할 수 없음"},
        502: {"description": "기사 크롤링 또는 뉴스 검색 서비스 오류"},
    },
)
@limiter.limit("10/minute")
async def track_article(
    request: Request,
    body: TrackInput,
    db: AsyncSession = Depends(get_session),
):
    """
    기사 추적 시작

    - URL 입력 시: 바로 크롤링하여 기사 정보 반환
    - 제목 입력 시: 검색하여 후보 기사 목록 반환
    """
    input_text = body.text.strip()
    is_url = bool(URL_PATTERN.match(input_text))

    if is_url:
        # URL + 메타데이터가 함께 온 경우 (candidate 선택) → 크롤링 스킵, 즉시 생성
        if body.title and not _is_poor_metadata(body.title):
            logger.info(f"Fast article creation (metadata): {input_text[:100]}")
            domain = urlparse(input_text).netloc.replace("www.", "")
            article_data = {
                "url": input_text,
                "title": body.title,
                "publisher": body.publisher if body.publisher and not _is_poor_metadata(body.publisher) else domain,
                "publisher_domain": domain,
                "published_at": _parse_date_str(body.published_at),
            }
            article = await _upsert_article(db, article_data)
            await db.refresh(article)

            log = SearchLog(query=input_text, input_type="url", result_count=1)
            db.add(log)

            return TrackResponse(
                input_type="url",
                article=ArticleResponse.model_validate(article),
            )

        # URL만 온 경우 (직접 URL 입력) → 크롤링 필요
        from app.core.crawler import crawl_article

        logger.info(f"Crawling article from URL: {input_text[:100]}")
        try:
            article_data = await crawl_article(input_text)
        except Exception as e:
            logger.error(f"Crawl failed for {input_text[:100]}: {e}")
            raise HTTPException(status_code=502, detail="기사를 크롤링하는 중 오류가 발생했습니다.")
        if not article_data:
            raise HTTPException(status_code=404, detail="기사를 크롤링할 수 없습니다.")

        # Google News 등 메타데이터 추출 실패 시 RSS 메타데이터로 폴백
        if _is_poor_metadata(article_data.get("title", "")) and body.title:
            article_data["title"] = body.title
        if _is_poor_metadata(article_data.get("publisher", "")) and body.publisher:
            article_data["publisher"] = body.publisher
            article_data["publisher_domain"] = body.publisher
        if not article_data.get("published_at") and body.published_at:
            article_data["published_at"] = _parse_date_str(body.published_at)

        article = await _upsert_article(db, article_data)
        # Refresh to load server-default values (created_at)
        await db.refresh(article)

        log = SearchLog(query=input_text, input_type="url", result_count=1)
        db.add(log)

        return TrackResponse(
            input_type="url",
            article=ArticleResponse.model_validate(article),
        )
    else:
        # 키워드 검색 - Redis 캐시 확인 (TTL 5분)
        cache_key = f"search:{hashlib.md5(input_text.encode()).hexdigest()}"
        cached = await cache_get(cache_key)
        if cached:
            logger.info(f"Search cache hit: {input_text[:80]}")
            log = SearchLog(
                query=input_text, input_type="title", result_count=len(cached)
            )
            db.add(log)
            candidates = [
                TrackCandidate(**c) for c in cached
            ]
            return TrackResponse(input_type="title", candidates=candidates)

        from app.services.news_search import search_news

        logger.info(f"Searching news for: {input_text[:100]}")
        try:
            results = await search_news(input_text)
        except Exception as e:
            logger.error(f"News search failed for {input_text[:80]!r}: {e}")
            raise HTTPException(status_code=502, detail="뉴스 검색 서비스에 연결할 수 없습니다.")

        log = SearchLog(
            query=input_text, input_type="title", result_count=len(results)
        )
        db.add(log)

        candidates = [
            TrackCandidate(
                title=r.get("title", ""),
                url=r.get("url", ""),
                publisher=r.get("publisher"),
                published_at=r.get("published_at"),
            )
            for r in results[:10]
        ]

        # 검색 결과 캐싱 (TTL 5분)
        if candidates:
            await cache_set(
                cache_key,
                [c.model_dump(mode="json") for c in candidates],
                ttl=300,
            )

        return TrackResponse(input_type="title", candidates=candidates)


@router.post(
    "/confirm",
    response_model=ConfirmResponse,
    summary="기사 추적 확인",
    description="기사를 확인한 후 전체 추적을 시작합니다. Celery 비동기 태스크로 유사 기사 수집 및 분석을 시작합니다.",
    responses={
        404: {"description": "기사를 찾을 수 없음"},
    },
)
@limiter.limit("10/minute")
async def confirm_article(
    request: Request,
    body: ConfirmInput,
    db: AsyncSession = Depends(get_session),
):
    """
    기사 확인 후 전체 추적 시작

    Celery 비동기 태스크로 유사 기사 수집/분석 시작
    """
    result = await db.execute(
        select(Article).where(Article.id == body.article_id)
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")

    tracking = TrackingRequest(
        input_text=article.title,
        input_type="url",
        origin_article_id=article.id,
        status="processing",
    )
    db.add(tracking)
    await db.flush()

    logger.info(f"Starting propagation analysis: tracking_id={tracking.id}")

    _get_celery_app().send_task(
        "app.workers.tasks.analyze_article_propagation",
        args=[str(tracking.id), str(article.id)],
    )

    return ConfirmResponse(
        tracking_id=tracking.id,
        status="processing",
        message="기사 전파 분석을 시작합니다.",
    )


@router.get(
    "/{article_id}",
    response_model=ArticleResponse,
    summary="기사 상세 조회",
    description="기사 ID로 기사의 상세 정보를 조회합니다.",
    responses={
        404: {"description": "기사를 찾을 수 없음"},
    },
)
async def get_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """기사 상세 조회"""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return ArticleResponse.model_validate(article)


async def _upsert_article(db: AsyncSession, article_data: dict) -> Article:
    """기사 upsert (URL 기준 중복 방지)"""
    url = article_data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="기사 URL이 없습니다.")

    # Article 모델에 존재하는 컬럼만 필터링 (크롤러가 _original_url 등 추가 필드를 포함할 수 있음)
    valid_columns = {c.key for c in Article.__table__.columns}
    filtered_data = {k: v for k, v in article_data.items() if k in valid_columns}

    result = await db.execute(select(Article).where(Article.url == url))
    article = result.scalar_one_or_none()

    if article:
        for key, value in filtered_data.items():
            if value is not None and hasattr(article, key):
                setattr(article, key, value)
    else:
        article = Article(**filtered_data)
        db.add(article)

    await db.flush()
    return article

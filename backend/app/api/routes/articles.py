"""
# articles.py - Article API Routes
# Version: 0.2.1
# Description: 기사 추적 요청, 확인, 상세 조회 API
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
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

logger = logging.getLogger(__name__)

router = APIRouter()

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

    from app.workers.tasks import analyze_article_propagation
    analyze_article_propagation.delay(str(tracking.id), str(article.id))

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

    result = await db.execute(select(Article).where(Article.url == url))
    article = result.scalar_one_or_none()

    if article:
        for key, value in article_data.items():
            if value is not None and hasattr(article, key):
                setattr(article, key, value)
    else:
        article = Article(**article_data)
        db.add(article)

    await db.flush()
    return article

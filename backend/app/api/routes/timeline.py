"""
# timeline.py - Timeline API Routes
# Version: 0.2.0
# Description: 타임라인 조회, 진행 상태 API (프론트엔드 타입 일치)
"""

import logging
from collections import Counter
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.article import Article
from app.models.timeline import TrackingRequest, TimelineEntry
from app.schemas.article import ArticleResponse
from app.schemas.timeline import (
    TrackingStatus,
    TimelineResponse,
    GraphNode,
    GraphEdge,
    GraphData,
    TimelineItem,
    DensityPoint,
    ExplosionPoint,
    LifecycleSummary,
)
from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

router = APIRouter()

STATUS_MESSAGES = {
    "pending": "대기 중입니다...",
    "processing": "기사를 분석하고 있습니다...",
    "completed": "분석이 완료되었습니다.",
    "failed": "분석에 실패했습니다.",
}


@router.get(
    "/{tracking_id}/status",
    response_model=TrackingStatus,
    summary="추적 상태 조회",
    description="추적 요청의 진행 상태를 조회합니다.",
    responses={
        404: {"description": "추적 요청을 찾을 수 없음"},
    },
)
async def get_tracking_status(
    tracking_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """추적 진행 상태 조회"""
    result = await db.execute(
        select(TrackingRequest).where(TrackingRequest.id == tracking_id)
    )
    tracking = result.scalar_one_or_none()
    if not tracking:
        raise HTTPException(status_code=404, detail="추적 요청을 찾을 수 없습니다.")

    message = tracking.error_message or STATUS_MESSAGES.get(tracking.status, "")

    return TrackingStatus(
        tracking_id=tracking.id,
        status=tracking.status,
        progress=tracking.progress,
        total_articles=tracking.total_articles,
        message=message,
    )


@router.get(
    "/{tracking_id}",
    response_model=TimelineResponse,
    summary="타임라인 조회",
    description="추적 요청의 전체 타임라인 데이터를 조회합니다. 그래프, 타임라인, 밀도, 폭발 시점, 라이프사이클 요약 정보를 포함합니다.",
    responses={
        202: {"description": "아직 분석 중입니다"},
        404: {"description": "추적 요청을 찾을 수 없음 또는 분석된 기사가 없음"},
    },
)
async def get_timeline(
    tracking_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """타임라인 전체 데이터 조회"""
    result = await db.execute(
        select(TrackingRequest).where(TrackingRequest.id == tracking_id)
    )
    tracking = result.scalar_one_or_none()
    if not tracking:
        raise HTTPException(status_code=404, detail="추적 요청을 찾을 수 없습니다.")

    if tracking.status == "processing":
        raise HTTPException(status_code=202, detail="아직 분석 중입니다.")

    # Check cache for completed tracking
    cache_key = f"timeline:{tracking_id}"
    try:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    # 타임라인 엔트리 + 기사 조인
    entries_result = await db.execute(
        select(TimelineEntry, Article)
        .join(Article, TimelineEntry.article_id == Article.id)
        .where(TimelineEntry.tracking_id == tracking_id)
        .order_by(Article.published_at.asc().nullslast())
    )
    entries = entries_result.all()

    if not entries:
        raise HTTPException(status_code=404, detail="분석된 기사가 없습니다.")

    # 원본 기사 찾기
    origin_article = None
    for entry, article in entries:
        if entry.is_origin:
            origin_article = ArticleResponse.model_validate(article)
            break

    if not origin_article:
        origin_article = ArticleResponse.model_validate(entries[0][1])

    # Graph, Timeline 구성
    nodes = []
    edges = []
    timeline_items = []
    stage_counts: Counter = Counter()

    for entry, article in entries:
        # Skip isolated articles (similarity < 50%)
        if entry.lifecycle_stage == "isolated":
            continue

        # Node
        nodes.append(GraphNode(
            id=str(article.id),
            title=article.title,
            publisher=article.publisher,
            published_at=article.published_at,
            similarity_score=entry.similarity_score,
            similarity_category=entry.similarity_category,
            lifecycle_stage=entry.lifecycle_stage,
            is_origin=entry.is_origin,
            url=article.url,
        ))

        # Edge
        if entry.parent_article_id:
            edges.append(GraphEdge(
                source=str(entry.parent_article_id),
                target=str(article.id),
                similarity_score=entry.similarity_score,
                similarity_category=entry.similarity_category,
            ))

        # Timeline item
        published = article.published_at or article.created_at
        timeline_items.append(TimelineItem(
            article_id=str(article.id),
            title=article.title,
            publisher=article.publisher,
            published_at=published,
            similarity_score=entry.similarity_score,
            lifecycle_stage=entry.lifecycle_stage,
            url=article.url,
            is_origin=entry.is_origin,
        ))

        # Stage count (skip isolated)
        if entry.lifecycle_stage and entry.lifecycle_stage != "isolated":
            stage_counts[entry.lifecycle_stage] += 1

    # Density
    density = _calculate_density(entries)

    # Explosions
    explosions = _detect_explosions(entries, density)

    # Lifecycle summary
    lifecycle = _build_lifecycle_summary(entries, density, stage_counts)

    response = TimelineResponse(
        tracking_id=tracking_id,
        origin_article=origin_article,
        graph=GraphData(nodes=nodes, edges=edges),
        timeline=timeline_items,
        density=density,
        explosions=explosions,
        lifecycle=lifecycle,
    )

    # Cache the result
    try:
        response_dict = response.model_dump()
        await cache_set(cache_key, response_dict, ttl=3600)  # 1 hour
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return response


def _calculate_density(entries: list) -> list[DensityPoint]:
    """시간별 기사 수 밀도 계산 (1시간 단위)"""
    hour_counts: Counter = Counter()
    for entry, article in entries:
        if article.published_at:
            hour = article.published_at.replace(minute=0, second=0, microsecond=0)
            hour_counts[hour] += 1

    return [
        DensityPoint(time=hour, count=count)
        for hour, count in sorted(hour_counts.items())
    ]


def _detect_explosions(
    entries: list, density: list[DensityPoint]
) -> list[ExplosionPoint]:
    """폭발 시점 감지 (동적 임계값)"""
    total = len(entries)
    threshold = max(5, int(total * 0.2))

    explosions = []
    for point in density:
        if point.count >= threshold:
            explosions.append(ExplosionPoint(
                start_time=point.time,
                end_time=point.time + timedelta(hours=1),
                peak_count=point.count,
                article_count=point.count,
            ))

    return explosions


def _build_lifecycle_summary(
    entries: list,
    density: list[DensityPoint],
    stage_counts: Counter,
) -> LifecycleSummary:
    """Lifecycle 요약 생성"""
    if not entries:
        return LifecycleSummary()

    published_times = [a.published_at for _, a in entries if a.published_at]
    if not published_times:
        return LifecycleSummary(
            total_articles=len(entries),
            stage_counts=dict(stage_counts),
        )

    origin_time = min(published_times)
    fadeout_time = max(published_times)
    duration = (fadeout_time - origin_time).total_seconds() / 3600

    peak = max(density, key=lambda d: d.count) if density else None

    return LifecycleSummary(
        origin_time=origin_time,
        fadeout_time=fadeout_time,
        peak_hour=peak.time if peak else None,
        total_duration_hours=round(duration, 2),
        total_articles=len(entries),
        stage_counts=dict(stage_counts),
    )

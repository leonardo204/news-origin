"""
# trends.py - Trends & Stats API Routes
# Version: 0.2.0
# Description: Hot Trends, 인기 검색어, 서비스 통계 (프론트엔드 타입 일치)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import sqlalchemy as sa
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.article import Article
from app.models.timeline import TrackingRequest
from app.models.search_log import SearchLog
from app.schemas.search import (
    TrendItem, PopularSearch, StatsOverview,
    ArticleTrendsResponse, RecentArticleItem,
)
from app.services.cache import cache_get, cache_set, cache_delete, get_redis

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/hot",
    response_model=list[TrendItem],
    summary="인기 트렌드 조회",
    description="현재 인기 있는 트렌드를 조회합니다. 기간별로 필터링할 수 있습니다.",
)
async def get_hot_trends(
    period: Literal["24h", "7d", "30d"] = Query("24h", description="기간: 24h, 7d, 30d"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
):
    """현재 Hot Trends 조회"""
    cache_key = f"trends:hot:{period}"

    # Check cache first
    try:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    # Query database
    hours_map = {"24h": 24, "7d": 168, "30d": 720}
    hours = hours_map.get(period, 24)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(
            TrackingRequest.input_text,
            func.count(TrackingRequest.id).label("cnt"),
            func.max(func.cast(TrackingRequest.id, sa.Text)).label("latest_id"),
            func.max(TrackingRequest.created_at).label("latest"),
        )
        .where(TrackingRequest.created_at >= since)
        .group_by(TrackingRequest.input_text)
        .order_by(desc("cnt"))
        .limit(limit)
    )

    trends = [
        TrendItem(
            title=row.input_text,
            tracking_count=row.cnt,
            latest_tracking_id=row.latest_id,
            last_tracked_at=row.latest,
        )
        for row in result.all()
    ]

    # Cache the result
    try:
        trends_dict = [item.model_dump() for item in trends]
        await cache_set(cache_key, trends_dict, ttl=1800)  # 30 minutes
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return trends


@router.get(
    "/popular-searches",
    response_model=list[PopularSearch],
    summary="인기 검색어 조회",
    description="사용자들이 많이 검색한 인기 검색어 목록을 조회합니다.",
)
async def get_popular_searches(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """인기 검색어 조회"""
    cache_key = "trends:popular"

    # Check cache first
    try:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    # Query database
    result = await db.execute(
        select(
            SearchLog.query,
            func.count(SearchLog.id).label("cnt"),
        )
        .group_by(SearchLog.query)
        .order_by(desc("cnt"))
        .limit(limit)
    )

    popular = [
        PopularSearch(query=row.query, count=row.cnt)
        for row in result.all()
    ]

    # Cache the result
    try:
        popular_dict = [item.model_dump() for item in popular]
        await cache_set(cache_key, popular_dict, ttl=7200)  # 2 hours
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return popular


@router.get(
    "/stats",
    response_model=StatsOverview,
    summary="서비스 통계 조회",
    description="전체 추적 수, 전체 기사 수, 현재 처리 중인 추적 수 등 서비스 통계 개요를 조회합니다.",
)
async def get_stats_overview(
    db: AsyncSession = Depends(get_session),
):
    """서비스 통계 개요"""
    cache_key = "trends:stats"

    # Check cache first
    try:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    # Query database
    tracking_count = await db.execute(select(func.count(TrackingRequest.id)))
    article_count = await db.execute(select(func.count(Article.id)))

    # Only count trackings that started within last 15 minutes as active
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    active_count = await db.execute(
        select(func.count(TrackingRequest.id)).where(
            TrackingRequest.status == "processing",
            TrackingRequest.created_at >= stale_cutoff,
        )
    )

    # 임베딩 완료 기사 수
    embedded_count = await db.execute(
        select(func.count(Article.id)).where(Article.qdrant_point_id.isnot(None))
    )

    # 최근 24시간 수집 기사 수
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_count = await db.execute(
        select(func.count(Article.id)).where(Article.created_at >= since_24h)
    )

    # 마지막 수집 시각
    last_crawl = await db.execute(select(func.max(Article.created_at)))

    # 카테고리별 기사 수
    category_col = Article.metadata_["category"].astext
    category_result = await db.execute(
        select(category_col, func.count(Article.id))
        .where(category_col.isnot(None))
        .group_by(category_col)
    )
    category_counts = {row[0]: row[1] for row in category_result.all()}

    stats = StatsOverview(
        total_trackings=tracking_count.scalar() or 0,
        total_articles=article_count.scalar() or 0,
        active_trackings=active_count.scalar() or 0,
        embedded_articles=embedded_count.scalar() or 0,
        recent_articles_24h=recent_count.scalar() or 0,
        last_crawl_at=last_crawl.scalar(),
        category_counts=category_counts,
    )

    # Cache the result
    try:
        stats_dict = stats.model_dump()
        await cache_set(cache_key, stats_dict, ttl=1800)  # 30 minutes
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return stats


@router.get(
    "/article-trends",
    response_model=ArticleTrendsResponse,
    summary="기사 기반 트렌드 클러스터",
    description="수집된 기사를 벡터 유사도로 클러스터링하여 트렌딩 토픽을 반환합니다.",
)
async def get_article_trends(
    period: Literal["24h", "7d", "30d"] = Query("24h", description="기간: 24h, 7d, 30d"),
    min_cluster_size: int = Query(1, ge=1, le=10),
    db: AsyncSession = Depends(get_session),
):
    """기사 기반 트렌딩 토픽 조회"""
    cache_key = f"trends:article-clusters:{period}:{min_cluster_size}"

    try:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    from app.core.trend_clustering import build_article_clusters
    result = await build_article_clusters(db, period, min_cluster_size)

    try:
        await cache_set(cache_key, result.model_dump(), ttl=1800)  # 30 minutes
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return result


@router.get(
    "/recent-articles",
    response_model=list[RecentArticleItem],
    summary="최근 수집 기사 피드",
    description="최근 수집된 기사 목록을 반환합니다. 카테고리 필터 가능.",
)
async def get_recent_articles(
    limit: int = Query(30, ge=1, le=100),
    category: str | None = Query(None, description="카테고리 필터"),
    db: AsyncSession = Depends(get_session),
):
    """최근 수집 기사 피드"""
    cache_key = f"trends:recent-articles:{limit}:{category or 'all'}"

    try:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    category_col = Article.metadata_["category"].astext
    query = (
        select(
            Article.id,
            Article.url,
            Article.title,
            Article.publisher,
            Article.published_at,
            Article.created_at,
            category_col.label("feed_category"),
        )
        .order_by(Article.created_at.desc())
        .limit(limit)
    )

    if category:
        query = query.where(category_col == category)

    result = await db.execute(query)
    articles = [
        RecentArticleItem(
            id=str(row.id),
            title=row.title,
            publisher=row.publisher,
            published_at=row.published_at,
            created_at=row.created_at,
            url=row.url,
            category=row.feed_category,
        )
        for row in result.all()
    ]

    try:
        articles_dict = [item.model_dump() for item in articles]
        await cache_set(cache_key, articles_dict, ttl=600)  # 10 minutes
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return articles


@router.get(
    "/crawl-status",
    summary="크롤링 상태 조회",
    description="현재 크롤링 파이프라인 상태를 조회합니다 (idle/fetching/crawling/embedding).",
)
async def get_crawl_status_endpoint():
    """현재 크롤링 파이프라인 상태"""
    from app.services.cache import get_crawl_status
    return await get_crawl_status()


@router.get(
    "/events",
    summary="통계 업데이트 SSE 스트림",
    description="크롤링 완료 시 실시간 알림을 받는 Server-Sent Events 스트림입니다.",
)
async def stats_events():
    """SSE 스트림: 크롤링 완료 이벤트를 실시간으로 전달"""
    async def event_stream():
        try:
            r = await get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe("stats_updated")
            try:
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=30.0,
                    )
                    if message and message["type"] == "message":
                        yield f"data: {message['data']}\n\n"
                    else:
                        yield ": keepalive\n\n"
            finally:
                await pubsub.unsubscribe("stats_updated")
                await pubsub.aclose()
        except Exception as e:
            logger.warning(f"SSE stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

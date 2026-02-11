"""
# trends.py - Trends & Stats API Routes
# Version: 0.2.0
# Description: Hot Trends, 인기 검색어, 서비스 통계 (프론트엔드 타입 일치)
"""

import logging
from datetime import datetime, timedelta, timezone

from typing import Literal

from fastapi import APIRouter, Depends, Query
import sqlalchemy as sa
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.article import Article
from app.models.timeline import TrackingRequest
from app.models.search_log import SearchLog
from app.schemas.search import TrendItem, PopularSearch, StatsOverview
from app.services.cache import cache_get, cache_set, cache_delete

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
        await cache_set(cache_key, trends_dict, ttl=900)  # 15 minutes
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
        await cache_set(cache_key, popular_dict, ttl=3600)  # 1 hour
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

    stats = StatsOverview(
        total_trackings=tracking_count.scalar() or 0,
        total_articles=article_count.scalar() or 0,
        active_trackings=active_count.scalar() or 0,
    )

    # Cache the result
    try:
        stats_dict = stats.model_dump()
        await cache_set(cache_key, stats_dict, ttl=300)  # 5 minutes
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return stats

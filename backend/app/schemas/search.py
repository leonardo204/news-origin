"""
# search.py - Search & Trends Pydantic Schemas
# Version: 0.2.0
# Description: 검색, 트렌드, 통계 관련 스키마 (프론트엔드 타입과 일치)
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TrendItem(BaseModel):
    """Hot Trend 아이템"""
    title: str
    tracking_count: int
    latest_tracking_id: str | None = None
    last_tracked_at: datetime | None = None


class PopularSearch(BaseModel):
    """인기 검색어"""
    query: str
    count: int


class StatsOverview(BaseModel):
    """서비스 통계 개요"""
    total_trackings: int = 0
    total_articles: int = 0
    active_trackings: int = 0
    embedded_articles: int = 0
    recent_articles_24h: int = 0
    last_crawl_at: datetime | None = None
    category_counts: dict[str, int] = {}

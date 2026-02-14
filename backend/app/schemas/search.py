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


class ClusterArticle(BaseModel):
    """클러스터 내 개별 기사"""
    id: str
    title: str
    publisher: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    url: str
    category: str | None = None
    similarity_score: float = 1.0


class TopicCluster(BaseModel):
    """트렌딩 토픽 클러스터"""
    cluster_id: str
    title: str
    article_count: int
    publishers: list[str]
    categories: list[str]
    first_seen: datetime
    last_seen: datetime
    avg_similarity: float
    representative_article: ClusterArticle
    articles: list[ClusterArticle]
    growth_rate: float = 0.0


class ArticleTrendsResponse(BaseModel):
    """기사 기반 트렌드 응답"""
    clusters: list[TopicCluster]
    total_articles: int
    total_clusters: int
    period: str
    generated_at: datetime
    category_distribution: dict[str, int] = {}
    publisher_distribution: dict[str, int] = {}
    hourly_counts: list[dict] = []


class RecentArticleItem(BaseModel):
    """최근 수집 기사"""
    id: str
    title: str
    publisher: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    url: str
    category: str | None = None

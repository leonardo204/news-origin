"""
# timeline.py - Timeline Pydantic Schemas
# Version: 0.3.0
# Description: 타임라인 관련 요청/응답 스키마 (프론트엔드 타입과 일치)
# Changes:
#   - 0.3.0: 2단계 추적 (instant/live) 지원 - tracking_type 필드 추가
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.article import ArticleResponse


class TrackInput(BaseModel):
    """기사 추적 요청"""
    text: str = Field(..., min_length=2, max_length=2000)
    title: str | None = None       # RSS에서 가져온 제목 (폴백용)
    publisher: str | None = None   # RSS에서 가져온 언론사 (폴백용)
    published_at: str | None = None  # RSS에서 가져온 발행일 (폴백용, 문자열로 수신)


class TrackCandidate(BaseModel):
    """검색 후보 기사"""
    title: str
    url: str
    publisher: str | None = None
    published_at: datetime | None = None


class TrackResponse(BaseModel):
    """추적 요청 초기 응답"""
    input_type: str  # 'url' | 'title'
    article: ArticleResponse | None = None
    candidates: list[TrackCandidate] = []


class ConfirmInput(BaseModel):
    """기사 확인 요청"""
    article_id: UUID
    tracking_type: str = "instant"  # 'instant' | 'live'


class LiveTrackInput(BaseModel):
    """Live 추적 요청 (instant → live 전환)"""
    tracking_id: UUID


class ConfirmResponse(BaseModel):
    """추적 확인 응답"""
    tracking_id: UUID
    status: str
    tracking_type: str = "instant"
    message: str = ""


class TrackingStatus(BaseModel):
    """추적 진행 상태"""
    tracking_id: UUID
    status: str
    progress: int = 0
    total_articles: int = 0
    tracking_type: str = "instant"
    message: str = ""


# ── Graph View Data (AntV G6) ──

class GraphNode(BaseModel):
    """AntV G6 노드 데이터"""
    id: str
    title: str
    publisher: str | None = None
    published_at: datetime | None = None
    similarity_score: float = 0.0
    similarity_category: str | None = None
    lifecycle_stage: str | None = None
    is_origin: bool = False
    is_user_selected: bool = False
    url: str | None = None


class GraphEdge(BaseModel):
    """AntV G6 엣지 데이터"""
    source: str
    target: str
    similarity_score: float = 0.0
    similarity_category: str | None = None


class GraphData(BaseModel):
    """그래프 전체 데이터"""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


# ── Timeline View Data (ECharts) ──

class TimelineItem(BaseModel):
    """타임라인 아이템"""
    article_id: str
    title: str
    publisher: str | None = None
    published_at: datetime
    similarity_score: float = 0.0
    lifecycle_stage: str | None = None
    url: str | None = None
    is_origin: bool = False
    is_user_selected: bool = False


class DensityPoint(BaseModel):
    """ECharts 밀도 차트 데이터 포인트"""
    time: datetime
    count: int


class ExplosionPoint(BaseModel):
    """폭발 시점"""
    start_time: datetime
    end_time: datetime
    peak_count: int = 0
    article_count: int = 0


class LifecycleSummary(BaseModel):
    """기사 lifecycle 요약"""
    origin_time: datetime | None = None
    fadeout_time: datetime | None = None
    peak_hour: datetime | None = None
    total_duration_hours: float | None = None
    total_articles: int = 0
    stage_counts: dict[str, int] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """타임라인 전체 응답"""
    tracking_id: UUID
    tracking_type: str = "instant"  # 'instant' | 'live'
    origin_article: ArticleResponse
    input_article_id: str | None = None  # 사용자 원래 선택 기사 ID
    graph: GraphData = GraphData()
    timeline: list[TimelineItem] = []
    density: list[DensityPoint] = []
    explosions: list[ExplosionPoint] = []
    lifecycle: LifecycleSummary = LifecycleSummary()

"""
# timeline.py - Tracking & Timeline SQLAlchemy Models
# Version: 0.2.0
# Description: 추적 요청 및 타임라인 엔트리 ORM 모델
# Changes:
#   - 0.2.0: tracking_type 컬럼 추가 (instant/live 2단계 추적)
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class TrackingRequest(Base):
    __tablename__ = "tracking_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_text = Column(Text, nullable=False)
    input_type = Column(String(10), nullable=False)
    origin_article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True)
    input_article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True)  # 사용자 원래 선택 기사
    tracking_type = Column(String(10), server_default="instant")  # 'instant' | 'live'
    status = Column(String(20), server_default="pending")
    total_articles = Column(Integer, server_default="0")
    progress = Column(Integer, server_default="0")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TimelineEntry(Base):
    __tablename__ = "timeline_entries"

    __table_args__ = (
        UniqueConstraint("tracking_id", "article_id", name="uq_tracking_article"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_id = Column(UUID(as_uuid=True), ForeignKey("tracking_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    similarity_category = Column(String(20), nullable=True)
    lifecycle_stage = Column(String(20), nullable=True, index=True)
    parent_article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True)
    is_origin = Column(Boolean, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

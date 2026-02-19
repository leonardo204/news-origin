"""
# article.py - Article SQLAlchemy Model
# Description: 기사 테이블 ORM 모델
"""

import uuid

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    publisher = Column(String(255), nullable=True, index=True)
    publisher_domain = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    language = Column(String(10), server_default="ko")
    qdrant_point_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    metadata_ = Column("metadata", JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

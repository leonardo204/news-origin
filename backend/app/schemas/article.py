"""
# article.py - Article Pydantic Schemas
# Version: 0.1.0
# Description: 기사 관련 요청/응답 스키마
# Changes:
#   - 0.1.0: ArticleBase, ArticleResponse, ArticleDetail
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class ArticleBase(BaseModel):
    """기사 기본 정보"""
    url: str
    title: str
    publisher: str | None = None
    published_at: datetime | None = None


class ArticleResponse(ArticleBase):
    """API 응답용 기사 정보"""
    id: UUID
    author: str | None = None
    publisher_domain: str | None = None
    summary: str | None = None
    content: str | None = None
    language: str = "ko"
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleDetail(ArticleResponse):
    """기사 상세 정보 (본문 포함)"""
    content: str | None = None
    metadata_: dict | None = None

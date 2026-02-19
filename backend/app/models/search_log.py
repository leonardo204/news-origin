"""
# search_log.py - SearchLog SQLAlchemy Model
# Description: 검색 로그 ORM 모델
"""

import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(Text, nullable=False)
    input_type = Column(String(10), nullable=True)
    result_count = Column(Integer, server_default="0")
    tracking_id = Column(UUID(as_uuid=True), ForeignKey("tracking_requests.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

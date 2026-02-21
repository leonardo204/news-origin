"""
# request_log.py - HTTP Request Log Model
# Description: HTTP 요청 로그 테이블 ORM 모델
"""

import uuid

from sqlalchemy import Column, DateTime, Float, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    method = Column(String(10), nullable=False)
    path = Column(String(512), nullable=False)
    status_code = Column(SmallInteger, nullable=False)
    duration_ms = Column(Float, nullable=False)
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_request_logs_created_at", "created_at"),
        Index("ix_request_logs_status_code", "status_code"),
        Index("ix_request_logs_path_created", "path", "created_at"),
    )

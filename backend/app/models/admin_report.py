"""
# admin_report.py - Admin Report Model
# Version: 0.1.0
# Description: 관리자 리포트 게시판 모델 (정기/비정기 리포트 + 이메일 발송 이력)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminReport(Base):
    __tablename__ = "admin_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 리포트 유형: weekly / monthly / alert
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # 리포트 제목
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # 이메일 발송용 요약 (plain text / 간단 HTML)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # 상세 리포트 구조화 데이터 (JSON)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 카테고리: traffic / crawling / mlops / system / mixed
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="mixed")
    # 심각도: info / warning / critical (알림용)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    # 이메일 발송 상태
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 생성 시각
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

"""add admin_reports table

Revision ID: 010_admin_reports
Revises: 009_request_logs
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "010_admin_reports"
down_revision = "009_request_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_json", JSON(), nullable=False, server_default="{}"),
        sa.Column("category", sa.String(50), nullable=False, server_default="mixed"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_error", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_admin_reports_created_at", "admin_reports", ["created_at"]
    )
    op.create_index(
        "ix_admin_reports_report_type", "admin_reports", ["report_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_reports_report_type", table_name="admin_reports")
    op.drop_index("ix_admin_reports_created_at", table_name="admin_reports")
    op.drop_table("admin_reports")

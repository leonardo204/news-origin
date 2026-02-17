"""Add input_article_id to tracking_requests

Revision ID: 005_input_article
Revises: 004_metadata_idx
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005_input_article"
down_revision = "004_metadata_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracking_requests",
        sa.Column("input_article_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tracking_input_article",
        "tracking_requests",
        "articles",
        ["input_article_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tracking_input_article", "tracking_requests", type_="foreignkey")
    op.drop_column("tracking_requests", "input_article_id")

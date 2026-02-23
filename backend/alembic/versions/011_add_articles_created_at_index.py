"""add articles created_at index for trend clustering

Revision ID: 011_articles_created_at_idx
Revises: 010_admin_reports
Create Date: 2026-02-23
"""

from alembic import op

revision = "011_articles_created_at_idx"
down_revision = "010_admin_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_articles_created_at",
        "articles",
        ["created_at"],
    )


def downgrade():
    op.drop_index("ix_articles_created_at", table_name="articles")

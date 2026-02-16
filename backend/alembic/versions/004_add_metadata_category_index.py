"""Add metadata category index to articles

Revision ID: 004_metadata_idx
Revises: 003_tracking_type
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa

revision = "004_metadata_idx"
down_revision = "003_tracking_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_articles_metadata_category",
        "articles",
        [sa.text("((metadata->>'category'))")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_articles_metadata_category", table_name="articles")
